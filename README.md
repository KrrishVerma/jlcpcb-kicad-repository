# JLCPCB KiCad Library — PCM Repository

The KiCad Plugin & Content Manager (PCM) feed for [KrrishVerma/JLCPCB-Kicad-Library](https://github.com/KrrishVerma/JLCPCB-Kicad-Library) — an independently maintained KiCad library built from its own [jlcpcb-parts-database](https://github.com/KrrishVerma/jlcpcb-parts-database) fork.

This repo, the library, and the parts database are three separate repositories that update themselves in sequence every day, so `packages.json`/`repository.json` here always point at the latest release automatically.

## Installation

1. Open KiCad → **Plugin and Content Manager** → **Manage**.
2. Add this repository URL:

   ```
   https://raw.githubusercontent.com/KrrishVerma/jlcpcb-kicad-repository/main/repository.json
   ```

3. Select it from the dropdown, find "JLCPCB KiCad Library", and install as normal.

New versions show up in PCM's update notification automatically — there's no need to manually sync anything.

## License

MIT — see [LICENSE](LICENSE). Original automation design by Chris Dirks (CDFER); independent maintenance and pipeline by Krrish Verma.
