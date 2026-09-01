# RommHeld

A Linux desktop application for managing a local RomM library across supported handheld devices.

## Current status

RommHeld is transitioning from a Vita-focused prototype into a multi-device handheld manager.

Current work includes the modular Vita implementation and the first Nintendo 3DS FTP transport.

## Devices

### PlayStation Vita

Current supported device.

Transport:

```text
USB / VitaShell mounted filesystem
```

The existing Vita workflow supports RomM platform mappings, RetroFlow/Adrenaline destinations, installed-state detection, bulk transfers, cancellation, resume-friendly same-size skipping, verification, free-space checks, and setup information.

### Nintendo 3DS

The first 3DS backend is being developed as an FTP device.

The current feature branch provides:

- configurable FTP host and port
- username/password configuration
- remote directory browsing
- arbitrary file uploads
- same-size skipping
- resumable uploads when supported by the server
- cancellation handling
- post-upload size verification
- explicit remote destination selection

The 3DS backend does not assume a single ROM directory. Destination mappings will be added only after their actual frontend/homebrew layouts are verified.

## RomM library

RommHeld treats the first directory below the configured RomM root as the RomM platform ID.

For example:

```text
~/RomM/roms/roms/gbc/
~/RomM/roms/roms/gba/
~/RomM/roms/roms/n64/
```

Platform detection is based on directory structure, not ROM filenames.

## Configuration

User configuration remains outside the repository:

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

## Send File

RommHeld provides a generic **Send File** workflow for arbitrary files.

The user explicitly chooses the local file, device, and remote destination. File extensions are not used to silently determine an installation path.

This makes the workflow useful for staging emulator VPKs, data archives, configuration files, homebrew artifacts, or other files obtained from their authoritative upstream projects.

## Software and emulator setup

RommHeld is not intended to become a package mirror for every emulator and homebrew project. Setup information should prefer authoritative upstream project and release links, with concise installation guidance.

Known package layouts may eventually expose explicit transfer presets, but arbitrary files remain under user control.

## RetroAchievements

RetroFlow is treated as a launcher/frontend rather than an emulator.

RetroAchievements compatibility belongs to the emulator/core that actually runs the game. RommHeld therefore treats achievement support as a separate capability from the frontend and transport.

The eventual routing model should distinguish native execution, emulator execution, RetroAchievements-compatible execution, experimental achievement support, and hardcore compatibility where verified.

## Project structure

The implementation is being split into focused modules under `romm_vita_manager/`:

- `config.py` for local configuration
- `devices.py` for device metadata and backend boundaries
- `models.py` for shared data structures
- `mappings.py` for platform mappings
- `romm.py` for RomM library discovery
- `vita.py` for Vita filesystem detection and storage information
- `transfers.py` for cancellable local/device-mounted transfers
- `three_ds_ftp.py` for the Nintendo 3DS FTP transport
- `emulators.py` for emulator/frontend metadata and achievement roles
- `archive_utils.py` for safe archive inspection and extraction helpers
- `package_manager.py` for existing Vita package handling during the transition
- `vita_setup.py` for Vita setup information
- `ui.py` for the main PySide6 application UI

The internal Python package name remains `romm_vita_manager` during the transition to avoid a needless namespace migration.

## Safety

Unknown or unsupported platform mappings are not copied automatically.

Remote path handling rejects traversal attempts and keeps 3DS destinations explicit.

FTP is intended for trusted local networks. It should not be exposed directly to the Internet.

The Linux application performs file transfers. No Vita-side downloader is required.

## Roadmap

- complete the modular GUI transition
- finish generic Send File integration across device backends
- complete Nintendo 3DS FTP transfer testing
- add verified 3DS platform mappings
- detect 3DS frontends/homebrew
- add upstream software/project links in Setup
- emulator and native execution routing
- RetroAchievements-aware routing
- artwork and richer library browsing
- detailed transfer queue
- duplicate detection and optional hashing
- smarter free-space and transfer planning
