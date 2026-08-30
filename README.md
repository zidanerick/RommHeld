# RomM Vita Manager

A Linux desktop utility for managing game transfers from a local RomM library to a USB-mounted modded PlayStation Vita.

## Current status

Early development. The current prototype provides:

- first-run setup wizard
- configurable main RomM ROM directory
- persistent per-user platform mappings
- automatic Vita mount detection
- platform filtering and search
- installed-state detection
- automatic RetroFlow and Adrenaline destinations
- multi-selection for bulk transfers
- resumable batch behaviour by skipping same-size files
- transfer progress and cancellation
- post-copy file-size verification
- list and tile browsing modes
- Vita free-space display and pre-transfer capacity checks
- Vita Setup component detection
- official-source package download and staging for selected Vita components
- RetroAchievements-aware emulator roles

The UI implementation now lives in `romm_vita_manager/ui.py`. The root Python entry point remains as a compatibility launcher.

## First-run setup

The application does not assume the developer's local filesystem layout.

On first launch it asks for the main RomM ROM directory. It then discovers the top-level platform directories and presents a mapping table where each RomM platform can be mapped to a RetroFlow destination or disabled.

The configuration is stored locally at:

```text
~/.config/romm-vita-manager/config.json
```

This file is deliberately outside the Git repository so personal paths and settings are not published.

## Default paths

The initial suggested RomM path is:

```text
~/RomM/roms/roms/
```

RetroFlow ROMs on the Vita:

```text
ux0:/data/RetroFlow/ROMS/
```

PSP ISOs through Adrenaline:

```text
ux0:/pspemu/ISO/
```

PSP and PS1 EBOOT.PBP games through Adrenaline:

```text
ux0:/pspemu/PSP/GAME/<Game>/EBOOT.PBP
```

## Requirements

Designed for Arch-based Linux distributions such as CachyOS.

```fish
sudo pacman -S --needed python pyside6
```

## Run

```fish
./run.sh
```

or:

```fish
python romm_vita_manager.py
```

## Vita connection

Put the Vita into USB mode using VitaShell, connect it to Linux, and press **Refresh** in the application.

The manager detects the mounted filesystem rather than relying on a fixed mount point or storage UUID.

## Vita Setup

Open **Vita Setup** from the main window to inspect the connected Vita and the emulator/frontend components it contains.

Available package actions currently cover selected components from their upstream sources:

- RetroFlow Emu4Vita build
- Adrenaline
- DSVita
- DaedalusX64
- RetroArch
- RetroArch data package

Downloads are stored in the user cache under:

```text
~/.cache/romm-vita-manager/packages/
```

Packages with an upstream SHA-256 digest are verified before staging. VPKs are copied to the Vita root for explicit VitaShell installation. Data archives are staged separately and are not installed automatically.

RetroFlow is treated as a frontend. For systems supported by RetroAchievements, RetroArch plus the appropriate libretro core is the achievement-first route. N64 is deliberately presented as a choice between ordinary DaedalusX64 use and an achievement-oriented RetroArch setup.

## Transfer behaviour

The manager skips destination files when they already exist with the expected size. This makes interrupted bulk transfers safe to resume.

New copies are verified by comparing the resulting file size with the source. A full checksum is not calculated by default because that would require another complete read of every transferred file.

Before a transfer begins, the manager checks the mounted Vita's free space and blocks the operation when the selected files cannot fit.

## Project structure

- `romm_vita_manager/config.py` for local configuration
- `romm_vita_manager/models.py` for shared data structures
- `romm_vita_manager/mappings.py` for platform and RetroFlow mapping definitions
- `romm_vita_manager/romm.py` for RomM library discovery
- `romm_vita_manager/vita.py` for Vita filesystem discovery and storage information
- `romm_vita_manager/transfers.py` for reusable cancellable copy operations
- `romm_vita_manager/emulators.py` for emulator/component definitions, detection patterns, package references, and achievement roles
- `romm_vita_manager/package_manager.py` for upstream package resolution, downloading, digest verification, caching, and staging
- `romm_vita_manager/vita_setup.py` for the Vita Setup UI and component actions
- `romm_vita_manager/ui.py` for the main PySide6 application UI

## Safety

Unknown or disabled platform mappings are not copied automatically. Native Vita VPK files are staged separately rather than being silently written into `ux0:/app`.

The setup manager does not silently install VPKs or mutate Vita application configuration. Final VPK installation remains an explicit VitaShell action.

The repository is intended to remain free of personal paths, credentials, ROM files, Vita dumps, and other machine-specific data.

## Roadmap

Planned areas include:

- automatic RetroFlow directory discovery
- artwork and richer tile browsing
- a detailed transfer queue
- smarter duplicate/hash handling
- Vita free-space and transfer planning tools
- more complete emulator/component package coverage
- verified version/update comparison
- RetroAchievements-aware emulator/core recommendations
- improved native Vita VPK installation workflow
