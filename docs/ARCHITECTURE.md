# Architecture

The application is a small single-process PySide6 desktop application. Core filesystem and package-management logic lives in focused modules under `romm_vita_manager/`.

## Data flow

```text
RomM library
    |
    v
romm.py filesystem scanner
    |
    v
Game records + platform IDs
    |
    +----> installed-state check <---- vita.py mount detection
    |
    v
Destination mapping
    |
    v
Transfer queue
    |
    +----> package_manager.py
    |          |
    |          +----> official release/buildbot download
    |          |
    |          +----> SHA-256 verification when available
    |          |
    |          +----> local cache / staging
    |          |
    |          +----> archive inspection before extraction
    |
    v
USB-mounted Vita
```

## Package responsibilities

- `config.py`: local per-user configuration under `~/.config/romm-vita-manager/`.
- `models.py`: shared immutable data structures.
- `mappings.py`: RomM platform IDs, labels, and known RetroFlow destinations.
- `romm.py`: RomM filesystem scanning. The first directory below the configured root is the platform ID.
- `vita.py`: dynamic Vita mount detection and storage information.
- `transfers.py`: reusable cancellable chunked file copying.
- `emulators.py`: component definitions, detection patterns, package references, and RetroAchievements roles.
- `archive_utils.py`: safe archive listing and extraction helpers with path traversal checks.
- `package_manager.py`: official package metadata, release resolution, downloads, digest verification, and Vita staging.
- `vita_setup.py`: Vita Setup UI and package actions.
- `ui.py`: PySide6 setup, library, transfer, and settings UI.

## Vita package policy

1. Download sources must be upstream/reliable project releases or official build infrastructure.
2. A package with an upstream SHA-256 digest is verified before it is accepted into the local cache.
3. Package downloads are staged before installation.
4. VPK installation remains an explicit VitaShell action rather than being silently automated.
5. Data archives such as RetroArch's data package are treated separately from VPK installation.
6. Multi-platform archives are inspected before extraction. The manager must not assume that a ZIP belongs in `ux0:/data/`.
7. Archive extraction rejects absolute paths and `..` traversal entries.
8. Unsupported or unverified packages must remain unavailable rather than falling back to arbitrary mirrors.

## RetroAchievements

RetroFlow is treated as a frontend. Achievement compatibility belongs to the emulator/core actually running the game. For supported systems, RetroArch and an appropriate libretro core are the preferred achievement-first route. N64 remains an explicit choice between ordinary DaedalusX64 use and an achievement-oriented RetroArch setup. RetroFlow 8.2.0 also documents support for Emu4Vita++ 0.71 or newer, with global and per-game core selection, so Emu4Vita++ is represented as a separate emulator path rather than replacing RetroArch implicitly. citeturn733973search1turn733973search4

## Design rules

1. The Linux application is the source of truth for transfers. No Vita-side downloader is required.
2. Vita mount points are detected dynamically. Storage UUIDs and personal absolute paths are not hard-coded.
3. RetroFlow destinations are based on the directory structure present on the connected Vita.
4. PSP and PS1 retain their Adrenaline locations.
5. Unknown mappings must fail safely rather than silently copying to a guessed location.
6. Transfers must be cancellable.
7. Existing files with the expected size should not be recopied.
8. New transfers receive a post-copy size check.
9. Transfer operations check destination free space before starting.
10. Setup actions must not silently install executable software without an explicit user action.
