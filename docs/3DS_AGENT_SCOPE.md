# 3DS Agent Scope

## Mission

Extend RomM Vita Manager with a Nintendo 3DS backend using FTP, while preserving the existing Vita functionality. Do not rewrite the application around the 3DS and do not remove Vita support.

## Repository rules

- GitHub is the source of truth.
- Inspect the current repository before changing anything.
- Do not reconstruct code from old chats or ZIPs.
- Do not introduce personal paths, usernames, ROM data, credentials, mount UUIDs, or device dumps into the repository.
- Prefer small, coherent commits.
- Keep the project suitable for public GitHub.
- Run syntax/tests/checks before declaring work complete.

## Current architecture

The project is a Linux PySide6 application. The current code has modular components for configuration, RomM scanning, platform mappings, Vita detection, transfers, emulator/setup logic, plus a UI entry point. A device backend foundation now exists in `romm_vita_manager/devices.py`, and `docs/DEVICE_BACKENDS.md` describes the intended boundary.

Do not make the 3DS implementation depend on Vita-only paths such as `ux0:/` or `/run/media/<user>/<mount>`.

## 3DS transport

The initial 3DS transport is FTP.

Implement a dedicated 3DS backend that can:

1. discover/configure an FTP endpoint without hard-coding an IP address
2. support user-configurable host, port, username and password where required
3. provide a connection test
4. browse the remote filesystem safely
5. report free space when the FTP server exposes enough information, otherwise clearly report that it is unavailable
6. upload files/directories
7. support progress reporting
8. support cancellation
9. support resumable transfers where the server supports REST/STOR or equivalent
10. verify remote file size after transfer
11. optionally verify hashes later when a practical remote hashing mechanism exists
12. avoid destructive operations by default

Use a maintained Python FTP implementation or the standard library if it meets the required behaviour. Do not shell out to anonymous FTP clients merely to get basic functionality.

## 3DS filesystem discovery

Do not guess ROM destinations from filenames.

First discover the 3DS filesystem and identify which frontend/homebrew environments are present. Make the destination mapping explicit and editable.

Likely areas to investigate include, depending on the installed software:

- `sdmc:/roms/`
- `sdmc:/roms/<platform>/`
- TwilightMenu++ / nds-bootstrap locations
- Universal-Updater or other homebrew locations
- RetroArch locations
- Red Viper locations

Do not assume these paths are identical across installations. The app should detect where practical and otherwise let the user choose/configure the destination.

## Device model

Introduce a backend abstraction rather than scattering `if vita` / `if 3ds` throughout the GUI.

A backend should expose concepts similar to:

- connection state
- device identity
- filesystem root
- directory listing
- file metadata
- free space
- upload/copy
- optional resume
- verification

Keep transfer planning as device-agnostic as possible.

## 3DS platform mapping

Add a separate 3DS mapping layer.

Start only with platforms for which the destination and execution path can be established confidently.

Do not route unsupported platforms into arbitrary directories.

The mapping should be based on RomM's top-level platform IDs, not filenames.

## Emulator/frontend awareness

The 3DS is not just another transport target. The setup layer should eventually understand:

- TwilightMenu++ / nds-bootstrap
- native GBA execution paths
- RetroArch
- Red Viper
- other verified 3DS emulators/frontends

However, the first 3DS milestone is transport and library transfer. Do not block that milestone on emulator installation research.

Represent emulator/frontend capability separately from transport capability.

## RetroAchievements requirement

RetroAchievements is a first-class concern.

Do not equate:

`frontend installed` = `RetroAchievements supported`

Do not replace native execution paths with RetroArch merely because RetroArch supports achievements.

Instead, model game/emulator routes explicitly, for example:

- native execution
- emulator execution
- RetroAchievements-compatible execution
- experimental achievement support

A later agent can investigate native DS/GBA achievement integrations. The current transport implementation must be designed so those routes can be added later without rewriting FTP or ROM scanning.

## UI requirements

Add a device selector or device-aware section to the existing UI without breaking the current Vita workflow.

A 3DS setup/device view should eventually show:

- device name
- connection method: FTP
- connection status
- detected frontend/homebrew
- SD/free space when available
- configured ROM roots
- platform mappings
- transfer status

Keep the UI understandable for a novice user.

## Safety

Do not perform destructive remote operations without an explicit user action.

Before large transfers, calculate the planned size and compare against available remote space when possible.

Do not overwrite different-size files silently.

Retain the existing resume-friendly philosophy used by the Vita transfer path.

Protect against path traversal and malformed remote paths.

## Testing

Add unit tests for:

- FTP connection configuration
- path normalization
- remote path safety
- directory listing parsing
- transfer progress/cancellation
- resume behaviour where supported
- post-transfer size verification
- device/backend selection
- platform mapping isolation between Vita and 3DS

Tests should not require an actual 3DS. Add mocked FTP tests.

When practical, include an optional manual test procedure for a real 3DS running a known FTP homebrew server.

## Milestones

### Milestone 1: Backend

Create the 3DS backend and device abstraction.

### Milestone 2: FTP

Connect, browse, report basic metadata, and upload safely.

### Milestone 3: Library transfer

Transfer selected RomM games to configured 3DS destinations with progress, cancellation, size verification, and resume support.

### Milestone 4: Detection/setup

Detect known frontend/homebrew components and present their status.

### Milestone 5: Emulator routing

Add explicit native/emulator routing metadata.

### Milestone 6: RetroAchievements-aware routing

Investigate verified RA-capable native or emulator paths and expose them as route choices.

## Out of scope for the first 3DS milestone

- automatic CFW installation
- exploit deployment
- modifying protected firmware
- automatic installation of arbitrary CIA/3DSX packages
- replacing existing frontend configurations without backup/consent
- copying BIOS or proprietary firmware dumps from unknown sources
- guessing emulator/core choices

## Completion criteria

The first 3DS milestone is complete when:

1. the application can configure and test an FTP connection
2. the 3DS filesystem can be browsed
3. a ROM can be transferred from RomM to a configured destination
4. cancellation works
5. re-running the transfer does not unnecessarily resend identical files
6. remote size verification works
7. Vita behaviour remains intact
8. tests pass
9. documentation explains setup and limitations
10. no machine-specific data has been committed
