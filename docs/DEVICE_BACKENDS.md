# Device backends

RomM Vita Manager is being prepared for multiple handheld targets. The current Vita workflow remains the reference implementation, while device-specific transport and filesystem behaviour should live behind backend interfaces.

## Current targets

- PlayStation Vita: USB / VitaShell mounted filesystem.
- Nintendo 3DS: FTP filesystem. The 3DS implementation is a separate development scope and must not assume the Vita paths or transport.

## Design rules

- Keep RomM scanning, platform mappings, game metadata, transfer planning, duplicate detection, and verification device-agnostic where practical.
- Put USB/VitaShell and FTP-specific behaviour in device backends.
- Do not hard-code mount UUIDs, usernames, ROM roots, FTP credentials, or machine-specific paths.
- A backend should expose discovery, connection state, filesystem operations, free-space information, and safe transfer primitives.
- Platform destinations belong to device-specific mappings. A RomM platform ID must never be routed to an arbitrary destination simply because a similarly named emulator exists.
- Emulator and frontend setup is also device-specific. RetroAchievements capability should be represented separately from the frontend or transport.

## 3DS direction

The planned 3DS backend uses FTP rather than USB. It should initially support discovery/configuration, filesystem browsing, safe file transfers, resumable transfers where the FTP server supports them, post-transfer verification, and detection of known frontends/homebrew. Emulator installation and native RetroAchievements integrations are later phases and must be based on verified upstream projects.
