# JLCPCB KiCad Library Mirror

An automatically-maintained KiCad Plugin & Content Manager (PCM) repository
that serves up-to-date releases of [CDFER/JLCPCB-Kicad-Library](https://github.com/CDFER/JLCPCB-Kicad-Library).

## Why this exists

The official PCM feed (`CDFER/cd_fer-kicad-repository`) stopped syncing new
releases in July 2025 because its GitHub Actions schedule trigger was
commented out. As a result, KiCad's Plugin and Content Manager shows
`2025.07.18` as the latest available version no matter how many new releases
CDFER ships. See [issue #47](https://github.com/CDFER/JLCPCB-Kicad-Library/issues/47)
for details.

This repo runs the same sync logic, but:

- keeps its `schedule:` trigger enabled, and
- paginates through **all** GitHub releases instead of only the default
  30 most recent, so it can catch up on the backlog in one run.

All credit for the library content itself goes to Chris Dirks (CDFER). This
is just a community mirror of the distribution feed while the upstream one is
stalled.

## Installation

1. Open KiCad → **Plugin and Content Manager** → **Manage**.
2. Add this repository URL:

   ```
   https://raw.githubusercontent.com/KRRISHVERMA/jlcpcb-kicad-repository/main/repository.json
   ```

3. Select it from the dropdown, find "JLCPCB KiCad Library", and install /
   update as normal.

If you already have CDFER's repository added, you can leave it in place and
just add this one alongside it, or remove the stale one to avoid confusion.

## Automated maintenance

A GitHub Actions workflow (`.github/workflows/update-repo.yml`):

- Runs daily at 06:15 UTC (15 minutes after JLCPCB-Kicad-Library's own daily
  build), and on manual `workflow_dispatch`.
- Fetches all releases from `CDFER/JLCPCB-Kicad-Library` (paginated).
- Downloads each new release's zip, computes its SHA256/size, and appends it
  to `packages.json`.
- Bumps the timestamp in `repository.json`.
- Commits the changes back to `main`.

### First run / catch-up

Because the upstream feed hasn't synced in over a year, the **first** run of
this workflow will need to download and hash several hundred release zips.
That's slow but only happens once. To run it immediately instead of waiting
for the next scheduled run:

Actions tab → **Update Repository** → **Run workflow**.

### Setup checklist for a fresh repo

- [ ] Repo Settings → Actions → General → **Workflow permissions** set to
      "Read and write permissions" (needed for the auto-commit step to push).
- [ ] If this repo was created via **fork**, enable Actions under the
      Actions tab first — GitHub disables Actions on forks by default.
- [ ] Trigger `workflow_dispatch` once manually and confirm `packages.json`
      / `repository.json` get committed with the current release before
      relying on the daily schedule.

## License

MIT — see [LICENSE](LICENSE). Original automation design by Chris Dirks
(CDFER); fork/mirror maintenance by Krrish Verma.
