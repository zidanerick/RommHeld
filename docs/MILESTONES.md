# RommHeld Development Milestones

RommHeld is a Linux desktop application for managing a local RomM library across multiple handheld targets. GitHub is the source of truth. Device-specific paths, IP addresses, credentials, ROMs, and removable-media contents belong only in local configuration or test environments.

## 0. Foundation

- [x] Rename the product to RommHeld.
- [x] Protect `main` from deletion and force-pushes.
- [x] Establish a device/backend architecture.
- [x] Keep the existing Vita implementation working while adding new device targets.
- [x] Move application configuration outside the repository.
- [ ] Complete the internal Python package namespace migration from `romm_vita_manager` to a neutral RommHeld namespace.

## 1. Core transfer system

- [x] RomM library scanning by top-level platform directory.
- [x] Persistent platform mappings.
- [x] Vita mount detection.
- [x] Safe file transfer with progress and cancellation.
- [x] Same-size transfer skipping.
- [x] Post-transfer size verification.
- [x] Free-space preflight where supported.
- [x] Generic Send File workflow for arbitrary files.
- [ ] Generalise all transfer operations behind a common device transport interface.
- [ ] Build a persistent transfer queue.
- [ ] Add retries and per-item error state.
- [ ] Add optional hashing for stronger duplicate detection.

## 2. Nintendo 3DS transport

- [x] FTP connection and directory browsing.
- [x] Configurable FTP endpoint stored locally.
- [x] Safe remote-root enforcement.
- [x] Same-size skip, resume, cancellation and size verification.
- [x] Manual physical FTP connection test.
- [x] Manual physical file-upload test.
- [x] Removable-storage transport design.
- [x] Gather real 3DS SD-card signatures from a mounted test card.
- [ ] Implement automatic 3DS SD-card signature validation.
- [ ] Automatic 3DS SD-card detection.
- [ ] Automatic platform directory discovery.
- [ ] Confirm ROM targets and build mappings from observed layouts.
- [ ] Test real ROM transfers.

## 3. 3DS target profiles

The 3DS should support multiple target profiles rather than treating every file as the same kind of installation.

- [ ] 3DS SD Card profile.
- [ ] RetroArch profile.
- [ ] TWiLight Menu++ / nds-bootstrap profile.
- [ ] DS / R4 flashcart SD profile.
- [ ] Native GBA route/profile.
- [ ] Virtual Boy / Red Viper profile.
- [ ] Official Virtual Console match/link workflow where an official title exists.
- [ ] Explicit user-configurable target overrides.
- [ ] Read-only storage validation with confidence levels.
- [x] Record observed R4/flashcart signatures without claiming a specific hardware model.
- [x] Research 3DS/DS runtime and RetroAchievements capabilities.

## 4. Vita target profiles

- [x] USB/VitaShell device handling.
- [x] RetroFlow mappings.
- [x] Adrenaline PSP target handling.
- [x] Adrenaline PS1 target handling.
- [ ] Removable-storage profile where Linux can safely mount the user's Vita storage.
- [ ] Better Vita emulator/frontend detection.
- [ ] Device capability model independent of transport.

## 5. UI and device management

- [x] Persistent Devices area.
- [x] Separate Vita and 3DS management sections.
- [x] Independent 3DS FTP window.
- [x] Persistent device status bar design and implementation.
- [x] Device-specific iconography.
- [x] Console-inspired but original device card styling.
- [x] Non-modal 3DS management so Vita controls remain available.
- [ ] Device selection for transfer destinations.
- [ ] Storage/target profile selector.
- [ ] Polish responsive layout and accessibility across larger/smaller desktop sizes.

## 6. Emulator and frontend awareness

- [ ] Detect installed frontends and emulators.
- [ ] Show missing components without automatically downloading them.
- [ ] Link to official upstream release/project pages.
- [ ] Generic file staging for user-downloaded packages.
- [ ] Installation guidance where final Vita/3DS installation still requires VitaShell or equivalent manual action.
- [ ] Separate frontend, emulator, core, and transport concepts.

## 7. RetroAchievements

RetroAchievements must remain a capability rather than an assumption about a frontend.

- [ ] Represent RA support separately from emulator/frontend support.
- [ ] Identify RetroArch/core routes where appropriate.
- [ ] Research native 3DS DS/GBA achievement integrations.
- [ ] Evaluate existing native DS + `rcheevos` work.
- [ ] Preserve native runtimes where they provide materially better compatibility/performance.
- [ ] Model Hardcore compatibility explicitly.
- [ ] Provide route recommendations without silently replacing the user's preferred runtime.

## 8. Library intelligence

- [ ] Automatic platform-directory discovery.
- [ ] Better duplicate detection.
- [ ] Optional hashes.
- [ ] Artwork and metadata.
- [ ] Per-game destination preview.
- [ ] Device-specific installed-state detection.
- [ ] Transfer planning against available storage.
- [ ] Multi-device comparison and recommended target.

## 9. Future devices

New consoles should be added as device/transport/target-profile implementations rather than separate applications.

Potential future targets include other handhelds or consoles supported by RomM and accessible through a safe local transport.

## Current development rule

Do not make a milestone depend on assumptions about a user's filesystem. Discover the device or let the user select its root, validate it using safe signatures, and keep all machine-specific state outside Git.

## Current research references

The current capability matrix is maintained in `docs/3DS_CAPABILITY_MATRIX.md`. It records conclusions from upstream project documentation and current RetroAchievements support information. When implementation choices change, update the matrix first and then update the corresponding code/milestone.
