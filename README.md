# RommHeld

A Linux desktop application for managing a local RomM library and transferring games and files to supported handhelds.

RommHeld is becoming device-aware rather than being tied to a single console. The first supported device is the modded PlayStation Vita, with Nintendo 3DS FTP support planned as the next device backend.

## Current status

Early development. The current working implementation focuses on PlayStation Vita support and provides:

- first-run setup wizard
- configurable RomM ROM directory
- automatic discovery of top-level RomM platform directories
- persistent platform mappings
- automatic Vita mount detection
- platform filtering and search
- installed-state detection
- list and tile browsing
- multi-selection for bulk transfers
- transfer progress and cancellation
- resume-friendly transfers by skipping same-size destination files
- post-transfer size verification
- Vita free-space display and pre-transfer capacity checks
- Vita Setup information for emulator/frontend components

The application is being refactored toward reusable device backends so the same library and transfer concepts can work with different handhelds and transport methods.

## Supported devices

### PlayStation Vita

Current implementation uses a VitaShell USB-mounted filesystem on Linux.

The manager detects the mounted filesystem dynamically. Mount UUIDs and usernames are not hard-coded.

Current Vita destinations include RetroFlow and Adrenaline-specific handling where the platform mapping is known.

### Nintendo 3DS

Planned next. The 3DS backend will use FTP rather than requiring a custom networking application on the console.

The intended architecture is:

```text
RomM library
    ↓
RommHeld
    ↓
Nintendo 3DS FTP backend
    ↓
configured remote destination
    ↓
transfer + verification
```

## Library layout

RommHeld expects a local RomM library whose platform directories are identified by their top-level RomM platform IDs.

A typical library looks like:

```text
~/RomM/roms/roms/
├── amiga/
├── gb/
├── gbc/
├── gba/
├── n64/
├── nes/
├── psx/
├── psp/
└── snes/
```

Platform detection is based on the top-level directory. The application does not infer platform identity from individual filenames.

## Configuration

User-specific configuration is stored outside the repository:

```text
~/.config/romm-vita-manager/config.json
```

The current filename is retained for compatibility while the internal application name transitions to RommHeld.

Personal paths, credentials, ROM files, Vita dumps, device UUIDs, and other machine-specific data must not be committed to Git.

## Run

On Arch-based Linux distributions such as CachyOS:

```fish
sudo pacman -S --needed python pyside6
```

Then:

```fish
./run.sh
```

or:

```fish
python romm_vita_manager.py
```

The internal Python package namespace is still `romm_vita_manager` during the transition.

## Transfer model

Transfers are intended to be reusable across device backends.

The general model is:

```text
source file
    ↓
device backend
    ↓
remote/local destination
    ↓
progress + cancellation
    ↓
verification
```

Existing destination files with the expected size can be skipped to make interrupted batches easier to resume.

A full checksum is not calculated for ordinary transfers by default because it requires another complete read of the file. Size verification is used after copying.

## Sending arbitrary files

RommHeld is intended to support a generic **Send File** workflow in addition to ROM transfers.

The user should be able to choose a local file, a supported handheld, and a destination path without the application needing to understand the file type.

This is useful for homebrew and emulator files such as:

```text
.vpk
.nds
.gba
.3ds
.cia
.zip
.7z
.suprx
.cfg
```

RommHeld should not infer a destination merely from a file extension. Known installation layouts may be offered as explicit presets, while arbitrary files can always be sent to a user-selected destination.

## Software and emulator setup

RommHeld does not need to redistribute every emulator or homebrew package itself.

The preferred model is to provide links to the authoritative upstream project or release page, explain what the software is for, and let the user download the appropriate artifact directly.

The generic file-transfer workflow can then be used to copy that downloaded artifact to the handheld.

This avoids hard-coding fragile download URLs and avoids assuming that every ZIP or archive has the same installation layout.

## RetroAchievements

RetroAchievements is treated as a capability rather than a property of the frontend alone.

RetroFlow is a launcher/frontend. The actual emulator or core used for a game determines compatibility and achievement support.

The long-term goal is to make emulator routing explicit so that RommHeld can distinguish between:

- native execution
- ordinary emulation
- RetroAchievements-compatible execution
- experimental achievement support
- achievement-first emulator/core choices

This is particularly important for systems where a native handheld execution path may offer better performance while an emulator provides mature RetroAchievements support.

## Project structure

The codebase is being migrated toward focused modules:

- `romm_vita_manager/config.py` for local configuration
- `romm_vita_manager/models.py` for shared data structures
- `romm_vita_manager/mappings.py` for platform and destination mappings
- `romm_vita_manager/romm.py` for RomM library discovery
- `romm_vita_manager/vita.py` for Vita filesystem discovery and storage information
- `romm_vita_manager/transfers.py` for reusable transfer operations
- `romm_vita_manager/emulators.py` for emulator/frontend metadata and detection
- `romm_vita_manager/devices.py` for the emerging device/backend abstraction

The legacy `romm_vita_manager.py` entry point remains during the transition.

## Development direction

The project is deliberately moving toward a multi-device architecture:

```text
                    RomM
                     │
                  RommHeld
                     │
          ┌──────────┴──────────┐
          │                     │
     PlayStation Vita      Nintendo 3DS
          │                     │
     USB / VitaShell           FTP
```

Near-term work includes:

- complete the modular refactor
- add generic Send File support
- generalize the transfer queue across device backends
- improve automatic platform and destination discovery
- add Nintendo 3DS FTP support
- add 3DS frontend/homebrew detection
- provide upstream software/project links from Setup
- add emulator and capability-aware routing
- improve duplicate detection and optional hashing
- add artwork and richer browsing
- make RetroAchievements-aware routing a first-class feature

## Safety and scope

RommHeld is a Linux desktop manager. It deliberately does not revive the abandoned Vita-native HTTP/SSL downloader approach from the unrelated historical `romm-vita` experiment.

Unknown or unsupported platform mappings should remain explicitly unsupported rather than being guessed.

The repository should remain free of personal filesystem paths, credentials, ROM files, Vita dumps, and other machine-specific data.
