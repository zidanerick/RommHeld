# RommHeld

RommHeld is a PySide6 desktop application for managing a local RomM game library and transferring games/files to supported handhelds.

The project is currently transitioning from a PlayStation Vita-focused application into a multi-device manager. The `main` branch remains the conservative Vita baseline while the active development branches contain the larger device, transfer, Nintendo 3DS, and UI work described below.

## Project status

### Stable baseline on `main`

The current `main` branch provides a working Vita-oriented foundation:

- first-run RomM library setup
- discovery of top-level RomM platform directories
- persistent platform mappings
- VitaShell USB mount detection
- platform filtering and game search
- installed-state detection
- list and tile browsing
- bulk selection and transfers
- transfer progress and cancellation
- same-size skipping for resume-friendly transfers
- post-transfer size verification
- Vita free-space checks
- Vita Setup information
- modular configuration, RomM scanning, mapping, Vita, transfer, and UI modules

The internal Python package namespace is still `romm_vita_manager` for compatibility during the refactor.

### Active development

The current feature stack extends the Vita baseline with:

- a generic, file-type-agnostic **Send File** workflow
- a reusable device/backend model
- a Nintendo 3DS FTP backend with browsing, upload, cancellation, resume where supported, and size verification
- a new handheld-selection and workspace UI
- local-directory and RomM-server source selection
- bundled handheld artwork and device-aware UI structure
- research and target-profile documentation for Nintendo 3DS and Nintendo DS

These changes are currently under review in the open pull requests rather than all being part of `main` yet.

## Devices

| Device | Status | Transport / storage |
| --- | --- | --- |
| PlayStation Vita | Current supported baseline | USB / VitaShell mounted filesystem |
| Nintendo 3DS | Active development | FTP backend |
| Nintendo DS / compatible flashcards | UI and target research | Flashcard / SD workflows planned |
| PlayStation Portable | Planned | Not implemented |
| Mobile | Planned | Not implemented |

The UI work may show a device as selectable before its complete management backend is finished. A selectable workspace must not be interpreted as proof that every transfer or runtime workflow for that device is implemented.

## RomM library

RommHeld treats the first directory below the configured RomM ROM root as the RomM platform ID. Platform identity is determined from directory structure, not individual filenames.

Example:

```text
~/RomM/roms/roms/
├── gba/
├── gbc/
├── n64/
├── nes/
├── psx/
└── snes/
```

## PlayStation Vita

The Vita implementation uses the filesystem exposed by VitaShell USB mode. Mount discovery is dynamic and does not depend on a hard-coded username or storage UUID.

Known Vita destinations include RetroFlow and Adrenaline layouts where the platform mapping is verified. Unknown mappings remain unsupported rather than being guessed.

## Nintendo 3DS

The active 3DS implementation is an FTP transport. It is deliberately separate from the Vita filesystem implementation and does not assume a universal ROM directory.

The development backend supports:

- configurable host, port, username, password, timeout, and passive mode
- connection and filesystem browsing
- configurable remote root
- remote path traversal protection
- same-size skipping
- resumable uploads where supported by the FTP server
- cancellation
- best-effort free-space reporting
- post-transfer size verification

Real-device testing and verified platform mappings are still separate work from implementing the transport itself.

## Send File

RommHeld is moving toward a first-class **Send File** workflow shared by device backends.

The intended behaviour is deliberately file-type agnostic:

1. choose a local file
2. choose the target device
3. choose an explicit destination
4. transfer with progress and cancellation
5. skip an existing same-size file where safe
6. require explicit confirmation before overwriting a different-size file
7. verify the resulting file after transfer

File extensions must not silently determine destinations. Known installation layouts may eventually be exposed as explicit, verified presets.

## Software and emulator setup

RommHeld is not intended to become a package mirror for every emulator and homebrew project. The preferred approach is to provide authoritative upstream project/release links and concise setup guidance, then let the user transfer downloaded artifacts with Send File.

This avoids brittle download URLs and avoids assuming that every archive has the same installation layout.

## RetroAchievements

RetroAchievements is modelled as a capability of the actual runtime rather than of a frontend or transport.

The long-term routing model distinguishes between native execution, ordinary emulation, RetroAchievements-compatible execution, experimental support, and Hardcore compatibility where verified. Runtime preferences should influence recommendations without silently replacing an available native path.

## Architecture

The application is being split into reusable layers:

```text
RomM / local library
        │
        ▼
 library + game metadata
        │
        ▼
 transfer planning / platform mapping
        │
        ▼
 device backend
    ┌───┴───────────────┐
    │                   │
   Vita                3DS
 USB/VitaShell          FTP
```

Device-specific transport and filesystem behaviour should remain behind backend boundaries. Emulator/frontend logic should remain separate from transport logic.

See:

- `docs/ARCHITECTURE.md` for the current architecture rules
- `docs/DEVICE_BACKENDS.md` for backend boundaries
- `docs/3DS_AGENT_SCOPE.md` for the original 3DS implementation scope

## Configuration

User configuration is stored outside the repository:

```text
~/.config/romm-vita-manager/config.json
```

The application is expected to keep personal filesystem paths, credentials, ROM files, device dumps, mount UUIDs, and other machine-specific information out of Git.

## Requirements

The current application uses Python and PySide6. On Arch-based Linux distributions such as CachyOS:

```fish
sudo pacman -S --needed python pyside6
```

Run:

```fish
./run.sh
```

or:

```fish
python romm_vita_manager.py
```

The active UI development branch also contains a `requirements.txt` for Python dependencies used by that branch.

## Development priorities

The immediate priority is not adding more device targets. It is consolidating the current work into a tested, coherent application:

1. establish one integration branch and merge the modular foundation
2. consolidate the duplicate Send File work
3. integrate and test the 3DS FTP backend against the common transfer model
4. finish the device-aware UI without overstating backend support
5. add verified 3DS filesystem signatures, target profiles, and platform mappings
6. add a persistent transfer queue with retries and clear per-item state
7. complete emulator/frontend detection and upstream software links
8. implement explicit runtime and RetroAchievements-aware routing
9. improve library metadata, artwork, duplicate detection, and optional hashing
10. package and verify the application across supported desktop platforms

## Safety and design rules

- Unknown or unsupported platform mappings must remain explicitly unsupported.
- Remote destinations must be explicit or backed by verified device-specific presets.
- Destructive remote operations must require explicit user action.
- FTP should be treated as a trusted local-network transport, not exposed directly to the Internet.
- Transport code must not make emulator or frontend decisions.
- Personal paths, credentials, ROMs, dumps, and device-specific state must not be committed.
- Tests must not require physical handheld hardware unless they are explicitly documented as manual integration tests.
