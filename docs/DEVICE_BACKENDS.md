# Device backends

RommHeld is a Linux desktop application for managing a local RomM library across supported handheld devices.

The current device implementation is the PlayStation Vita. Nintendo 3DS support is planned as an FTP-backed device. Device-specific transport and filesystem behaviour belongs behind backend interfaces so the main library and transfer workflow remain reusable.

## Current targets

- **PlayStation Vita**: USB / VitaShell mounted filesystem. Current implementation.
- **Nintendo 3DS**: FTP filesystem. Planned backend.

## Design rules

- Keep RomM scanning, game metadata, transfer planning, duplicate detection, and verification device-agnostic where practical.
- Put USB/VitaShell and FTP-specific behaviour in device backends.
- Do not hard-code mount UUIDs, usernames, ROM roots, FTP credentials, or machine-specific paths.
- A backend should expose discovery, connection state, filesystem operations, free-space information, and safe transfer primitives.
- Platform destinations belong to device-specific mappings. A RomM platform ID must never be routed to an arbitrary destination simply because a similarly named emulator exists.
- Emulator and frontend setup is device-specific. RetroAchievements capability should be represented separately from the frontend or transport.

## Generic file transfer

RommHeld should provide a first-class **Send File** workflow that can transfer arbitrary user-selected files to a connected device. File extensions must not determine the destination automatically. Known software layouts may provide optional explicit presets, but the user remains in control of the remote destination.

The generic file transfer workflow should reuse the same queue, progress, cancellation, resume, and verification mechanisms as ROM transfers.

## Software and emulator setup

RommHeld is not intended to become a package mirror for every emulator and homebrew project. Setup pages should prefer links to authoritative upstream projects/releases and concise installation guidance. User-downloaded artifacts can then be transferred with Send File.

This keeps upstream distribution responsibility with the project authors and avoids brittle assumptions about archive layouts and release assets.

## Nintendo 3DS direction

The planned 3DS backend uses FTP rather than USB. The initial implementation should support connection configuration, filesystem browsing, safe arbitrary-file transfers, ROM destination mapping, resume where supported, and post-transfer verification.

Later stages can add detection of TwilightMenu++ / nds-bootstrap, native GBA paths, RetroArch, Red Viper, and other verified 3DS software. Emulator routing and RetroAchievements support must remain separate capabilities rather than assumptions tied to the FTP transport.
