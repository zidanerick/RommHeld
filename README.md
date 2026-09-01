# RommHeld

A Linux desktop application for managing a local RomM library across supported handheld devices.

## Current status

RommHeld is transitioning from a Vita-focused prototype into a multi-device handheld manager.

Current capabilities on the modular Vita implementation include:

- first-run setup and configurable RomM library root
- automatic top-level platform discovery
- persistent platform mappings
- PlayStation Vita detection through VitaShell USB mounts
- RetroFlow and Adrenaline destination handling
- platform filtering, search, and installed-state detection
- list and tile browsing
- bulk selection and cancellable transfers
- resume-friendly same-size skipping
- post-transfer size verification
- Vita free-space reporting and pre-transfer capacity checks
- Vita component detection and setup information
- RetroAchievements-aware emulator role information
- generic Send File support for arbitrary files on the Vita

The application architecture is being separated into device backends so additional handhelds can share the same RomM library and transfer machinery.

## Devices

### PlayStation Vita

Current supported device.

Transport:

```text
USB / VitaShell mounted filesystem
```

Typical destinations include RetroFlow, Adrenaline PSP/PS1 locations, and other explicitly configured paths.

### Nintendo 3DS

Next device backend.

Transport:

```text
FTP
```

The planned 3DS backend will provide configurable FTP connection details, remote filesystem browsing, explicit destination selection, arbitrary file transfer, verification, and resume where the server supports it.

## RomM library

RommHeld treats the first directory below the configured RomM root as the RomM platform ID.

For example:

```text
~/RomM/roms/roms/gbc/
~/RomM/roms/roms/gba/
~/RomM/roms/roms/n64/
```

Platform detection is based on the directory structure, not ROM filenames.

## Configuration

User configuration is stored outside the repository:

```text
~/.config/romm-vita-manager/config.json
```

Personal paths, credentials, ROM files, device dumps, mount UUIDs, and other machine-specific data must never be committed.

## Installation

Designed for Arch-based Linux distributions such as CachyOS.

```fish
sudo pacman -S --needed python pyside6
```

Run the application with:

```fish
./run.sh
```

or:

```fish
python romm_vita_manager.py
```

## Vita connection

Put the Vita into USB mode using VitaShell, connect it to Linux, and press **Refresh**.

RommHeld discovers the mounted filesystem dynamically. It does not require a fixed mount point or storage UUID.

## Send File

RommHeld provides a generic **Send File** workflow for arbitrary files.

The user explicitly chooses:

1. the local file
2. the destination device
3. the remote file path

The file extension does not determine its destination automatically.

This is intended to make it easy to stage homebrew artifacts downloaded from their upstream projects without RommHeld becoming a package mirror.

## Software and emulator setup

RommHeld should prefer authoritative upstream project and release links rather than maintaining fragile package-download logic for every emulator and homebrew project.

For Vita and 3DS software, the user can obtain the appropriate upstream artifact and then transfer it with **Send File**.

Final VPK installation on the Vita remains an explicit VitaShell action.

## RetroAchievements

RetroFlow is treated as a launcher/frontend rather than an emulator.

Achievement compatibility belongs to the emulator/core actually running the game. RommHeld therefore models RetroAchievements as a separate capability instead of assuming that a frontend or transport supports achievements.

The same principle will apply to 3DS native execution, emulator execution, and experimental achievement integrations.

## Project structure

The implementation is being split into focused modules under `romm_vita_manager/`:

- `config.py` for local configuration
- `devices.py` for device metadata and backend boundaries
- `models.py` for shared data structures
- `mappings.py` for platform mappings
- `romm.py` for RomM library discovery
- `vita.py` for Vita filesystem detection and storage information
- `transfers.py` for cancellable local/device-mounted transfers
- `emulators.py` for emulator/frontend metadata and achievement roles
- `archive_utils.py` for safe archive inspection and extraction helpers
- `package_manager.py` for existing Vita package handling during the transition
- `vita_setup.py` for Vita setup information
- `ui.py` for the main PySide6 application UI

The internal Python package name remains `romm_vita_manager` during the transition to avoid a needless namespace migration.

## Safety

Unknown or unsupported platform mappings are not copied automatically.

Archive extraction rejects unsafe paths and multi-platform archives are not blindly extracted into a Vita data directory.

The Linux application performs file transfers. No Vita-side downloader is required.

## Roadmap

- complete the modular GUI transition
- generic Send File across device backends
- Nintendo 3DS FTP backend
- 3DS filesystem discovery and explicit platform mappings
- upstream software/project links in Setup
- frontend/homebrew detection
- emulator and native execution routing
- RetroAchievements-aware routing
- artwork and richer library browsing
- detailed transfer queue
- duplicate detection and optional hashing
- smarter free-space and transfer planning
