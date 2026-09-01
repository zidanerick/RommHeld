# RommHeld

A Linux desktop application for managing a local RomM library across supported handheld devices.

RommHeld handles the common library and transfer workflow while keeping device-specific transport and filesystem behaviour behind separate backends.

## Current status

Early development. The current implementation is focused on the PlayStation Vita and includes:

- first-run RomM library setup
- automatic discovery of top-level RomM platform directories
- persistent platform mappings
- VitaShell USB mount detection without hard-coded mount UUIDs
- platform filtering and game search
- installed-state detection
- list and tile views
- bulk selection
- cancellable transfers
- resume-friendly same-size file skipping
- post-transfer size verification
- Vita free-space checks
- Vita Setup information
- a generic **Send File** workflow for arbitrary files

Nintendo 3DS support is planned as an FTP-backed device using the same reusable library and transfer architecture.

## RomM library

RommHeld expects the local RomM ROM library to be organised by top-level RomM platform IDs, for example:

```text
~/RomM/roms/roms/
├── gba/
├── gbc/
├── n64/
├── nes/
└── psx/
```

Platform detection is based on the top-level directory. The application does not guess a platform from a ROM filename.

## PlayStation Vita

The current device backend uses a VitaShell USB-mounted filesystem.

Typical RetroFlow ROM storage is below:

```text
ux0:/data/RetroFlow/ROMS/
```

PSP ISO storage through Adrenaline:

```text
ux0:/pspemu/ISO/
```

PS1 EBOOT storage through Adrenaline:

```text
ux0:/pspemu/PSP/GAME/<Game>/EBOOT.PBP
```

Actual mount paths are detected dynamically and are never hard-coded.

## Send File

**Send File** is deliberately file-type agnostic. It can transfer an arbitrary local file to an explicit destination on a connected device.

The workflow does not infer a destination from the extension and does not automatically extract archives or install packages.

For Vita transfers it provides:

- explicit `ux0:/...` destination selection
- same-size skip
- explicit overwrite confirmation for different-size files
- cancellable transfer
- post-transfer size verification
- protection against escaping the Vita `ux0` filesystem

See `docs/SEND_FILE.md` for details.

## Software and emulator setup

RommHeld is not intended to become a package mirror for every emulator and homebrew project. Setup information should link to authoritative upstream projects/releases and explain requirements where useful.

Users can then download the appropriate release from the upstream project and use **Send File** to place the artifact on the device.

RetroAchievements is treated separately from frontend and transport support. Emulator routing should prefer the appropriate achievement-compatible route rather than assuming that a frontend or emulator automatically supports achievements.

## Device architecture

The application is structured around reusable device backends:

```text
RommHeld
├── RomM library
├── shared transfer planning
├── platform mappings
├── device backends
│   ├── PlayStation Vita
│   └── Nintendo 3DS (planned)
└── emulator/frontend metadata
```

See `docs/DEVICE_BACKENDS.md` for the architecture and `docs/3DS_AGENT_SCOPE.md` for the planned Nintendo 3DS implementation.

## Configuration

Local configuration is stored outside the repository at:

```text
~/.config/romm-vita-manager/config.json
```

The configuration contains user-specific paths and settings and should not be committed.

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

The internal Python package namespace remains `romm_vita_manager` for now to avoid an unnecessary namespace migration while the device architecture is stabilised.

## Roadmap

- complete the modular UI refactor
- finish generic device-aware transfer UI
- Nintendo 3DS FTP backend
- 3DS filesystem discovery and platform mappings
- upstream software/project links in Setup
- artwork and richer browsing
- proper transfer queue
- smarter duplicate/hash handling
- emulator and native execution routing
- RetroAchievements-aware route selection
- broader handheld/device support

## Safety

RommHeld should remain free of personal paths, credentials, ROM files, Vita/3DS dumps, and machine-specific configuration.

Unknown or unsupported platform mappings must remain explicitly unsupported rather than being guessed.
