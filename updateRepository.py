import json
import os
import requests
import datetime
import hashlib
import tempfile
import zipfile
from typing import List, Dict, Optional

# Configuration
# Points at KRRISHVERMA's independent fork/rebuild of JLCPCB-Kicad-Library
# (which itself sources fresh component data from KRRISHVERMA's fork of
# jlcpcb-parts-database), rather than CDFER's original repo, since CDFER's
# upstream data pipeline has been stalled since April 2026.
GITHUB_RELEASES_URL = "https://api.github.com/repos/KRRISHVERMA/JLCPCB-Kicad-Library/releases"
DEFAULT_STATUS = "stable"
DEFAULT_KICAD_VERSION = "8.0"
PER_PAGE = 100
MAX_PAGES = 20  # safety cap: 20 * 100 = 2000 releases, far more than currently exist


def get_latest_releases(releases_url: str) -> List[Dict]:
    """Fetch ALL releases from GitHub, paginating through the results.

    NOTE: the GitHub REST API defaults to 30 releases per page. The
    upstream CDFER/cd_fer-kicad-repository script never paginated, so
    after its automation stalled for a year the backlog grew past 30
    releases and a single un-paginated call would silently miss most
    of them. This version pages through everything so a single run
    can catch up fully.
    """
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Krrish-Kicad-Repo-Updater"}

    # Optional: use GITHUB_TOKEN if available to raise the API rate limit
    # from 60/hr (unauthenticated) to 5000/hr. In GitHub Actions this is
    # populated automatically via the workflow's `env:` block.
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    all_releases: List[Dict] = []
    page = 1

    while page <= MAX_PAGES:
        try:
            response = requests.get(
                releases_url,
                headers=headers,
                params={"per_page": PER_PAGE, "page": page},
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch releases (page {page}): {e}")

        batch = response.json()
        if not batch:
            break

        all_releases.extend(batch)

        if len(batch) < PER_PAGE:
            break

        page += 1

    return all_releases


def calculate_sha256(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(4096):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_zip_contents_size(zip_path: str) -> int:
    """Calculate total size of all files in a ZIP archive."""
    total_size = 0
    with zipfile.ZipFile(zip_path, "r") as z:
        for file_info in z.infolist():
            total_size += file_info.file_size
    return total_size


def extract_metadata(zip_path: str, version: str) -> tuple:
    """Extract metadata from zip file's metadata.json."""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            with z.open("metadata.json") as meta_file:
                metadata = json.load(meta_file)

                for ver in metadata.get("versions", []):
                    if ver.get("version") == version:
                        return (ver.get("status", DEFAULT_STATUS), ver.get("kicad_version", DEFAULT_KICAD_VERSION))
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
        pass

    return DEFAULT_STATUS, DEFAULT_KICAD_VERSION


def process_asset(asset_url: str, version: str) -> Optional[tuple]:
    """Download and process asset to get required metadata."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            response = requests.get(asset_url, stream=True)
            response.raise_for_status()

            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

        sha256 = calculate_sha256(tmp_path)
        download_size = os.path.getsize(tmp_path)
        install_size = get_zip_contents_size(tmp_path)
        status, kicad_version = extract_metadata(tmp_path, version)

        return sha256, download_size, install_size, status, kicad_version
    except Exception as e:
        print(f"Failed to process asset {asset_url}: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def validate_packages_structure(packages: Dict) -> None:
    """Validate the structure of the packages.json data."""
    required_keys = ["packages"]
    if not all(key in packages for key in required_keys):
        raise KeyError(f"Missing required keys in packages.json: {required_keys}")


ASSET_CACHE_FILE = "asset_cache.json"


def load_asset_cache(cache_file: str) -> Dict[str, str]:
    """Load the version -> asset `updated_at` cache.

    This is bookkeeping-only, kept in a separate file so packages.json
    itself never carries any fields outside what PCM's schema expects.
    """
    try:
        with open(cache_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_asset_cache(cache_file: str, cache: Dict[str, str]) -> None:
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=4, sort_keys=True)


def update_packages_json(packages_json_file: str, releases: List[Dict], cache_file: str) -> None:
    """Update packages.json with new release information.

    IMPORTANT: version tags here are date-based (e.g. "2026.08.03") and can
    get their release *asset* overwritten multiple times in a single day --
    every run of the upstream library's build workflow re-uploads a fresh
    zip under the same tag rather than creating a new tag. A naive "skip if
    version already recorded" check (the original behavior here) locks in
    whatever sha256 happened to be computed on the FIRST run of that day,
    so any later same-day rebuild causes PCM's "Downloaded archive hash
    does not match repository entry" error -- the recorded hash is for an
    asset that no longer exists.

    Fix: track each asset's GitHub-reported `updated_at` timestamp in a
    separate cache file (not inside packages.json, to avoid adding any
    non-standard fields to what PCM actually parses). If we see the same
    version tag again but its asset's `updated_at` has moved forward,
    treat it as changed and recompute the hash/sizes in place, instead of
    skipping.
    """
    try:
        with open(packages_json_file, "r") as f:
            packages = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Error loading {packages_json_file}: {e}")

    validate_packages_structure(packages)

    existing_versions = {v["version"]: v for package in packages["packages"] for v in package.get("versions", [])}
    asset_cache = load_asset_cache(cache_file)

    # Process oldest-first so newest ends up inserted last (at index 0),
    # keeping packages[0]["versions"] sorted newest-first.
    for release in sorted(releases, key=lambda r: r.get("published_at", ""), reverse=False):
        version = release.get("tag_name")
        assets = release.get("assets", [])

        asset = next(
            (
                a
                for a in assets
                if a.get("name", "").startswith("JLCPCB-KiCad-Library-") and a.get("name", "").endswith(".zip")
            ),
            None,
        )

        if not asset or not version:
            continue

        asset_updated_at = asset.get("updated_at", "")
        existing_entry = existing_versions.get(version)

        if existing_entry is not None and asset_cache.get(version) == asset_updated_at:
            # Same tag, same asset upload -- genuinely nothing changed.
            continue

        download_url = asset.get("browser_download_url")
        result = process_asset(download_url, version)

        if not result:
            continue

        sha256, d_size, i_size, status, kicad_ver = result

        new_version = {
            "version": version,
            "status": status,
            "kicad_version": kicad_ver,
            "download_sha256": sha256,
            "download_size": d_size,
            "install_size": i_size,
            "download_url": download_url,
        }

        if existing_entry is not None:
            # Same tag, but the asset behind it changed since we last
            # recorded it (re-released same day) -- update in place rather
            # than inserting a duplicate.
            existing_entry.clear()
            existing_entry.update(new_version)
            print(f"Refreshed version {version} (asset was re-uploaded)")
        else:
            packages["packages"][0]["versions"].insert(0, new_version)
            existing_versions[version] = new_version
            print(f"Added version {version}")

        asset_cache[version] = asset_updated_at

    save_asset_cache(cache_file, asset_cache)

    try:
        with open(packages_json_file, "w") as f:
            json.dump(packages, f, indent=4)
    except IOError as e:
        raise RuntimeError(f"Error writing to {packages_json_file}: {e}")


def update_repository_json(repository_json_file: str) -> None:
    """Update repository.json with current timestamp."""
    try:
        with open(repository_json_file, "r") as f:
            repository = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Error loading {repository_json_file}: {e}")

    current_time = datetime.datetime.now(datetime.timezone.utc)
    repository["packages"]["update_time_utc"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
    repository["packages"]["update_timestamp"] = int(current_time.timestamp())

    try:
        with open(repository_json_file, "w") as f:
            json.dump(repository, f, indent=4)
    except IOError as e:
        raise RuntimeError(f"Error writing to {repository_json_file}: {e}")


def main() -> None:
    """Main function to update repository metadata."""
    try:
        releases = get_latest_releases(GITHUB_RELEASES_URL)
        print(f"Fetched {len(releases)} releases from GitHub")
        update_packages_json("packages.json", releases, ASSET_CACHE_FILE)
        update_repository_json("repository.json")
        print("Successfully updated repository metadata")
    except Exception as e:
        print(f"Error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
