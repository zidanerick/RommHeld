# RommHeld Development Milestones

RommHeld is a cross-platform desktop application for managing a local or RomM-backed game library across multiple handheld targets. GitHub is the source of truth. Device-specific paths, IP addresses, credentials, ROMs, and removable-media contents belong only in local configuration or test environments.

## 0. Foundation

- [x] Rename the product to RommHeld.
- [x] Protect `main` from deletion and force-pushes.
- [x] Establish a device/backend architecture.
- [x] Keep the existing Vita implementation working while adding new device targets.
- [x] Move application configuration outside the repository.
- [x] Add platform-aware config/cache/temp path services.
- [x] Preserve migration from the old Linux config path.
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
- [x] Add user runtime preference model: prefer native, prefer RetroAchievements, or prefer compatibility.
- [ ] Apply runtime preferences per platform/target when making route recommendations.

## 4. Vita target profiles

- [x] USB/VitaShell device handling.
- [x] RetroFlow mappings.
- [x] Adrenaline PSP target handling.
- [x] Adrenaline PS1 target handling.
- [ ] Removable-storage profile where the host can safely mount the user's Vita storage.
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
- [x] Handheld selection launch screen.
- [x] Library source selection shell.
- [x] Active handheld workspace context.
- [x] Data-driven platform artwork registry.
- [x] Local bundled handheld illustrations and logo variants.
- [x] RommHeld application branding asset.
- [x] Single-window console-aware workspace with real sections.
- [x] Remove device-specific controls from unrelated console workspaces.
- [x] Console-specific runtime preference presentation.
- [x] Global settings page separated from Vita-only setup UI.
- [ ] Embed Vita / 3DS / DS setup and transfer panels directly into tabs.
- [ ] Device selection for transfer destinations.
- [ ] Storage/target profile selector.
- [ ] Polish responsive layout and accessibility across desktop sizes.

## 6. Cross-platform desktop support

- [x] Keep UI based on PySide6/Qt.
- [x] Abstract application config/cache/temp locations.
- [x] Remove Linux-specific Vita mount discovery from the core detector.
- [x] Add cross-platform volume enumeration through Qt storage services.
- [ ] Add Windows packaging/build definition.
- [ ] Add macOS packaging/build definition.
- [ ] Add Linux packaging/build definition.
- [ ] Verify removable-volume detection on Windows and macOS.
- [ ] Verify file open/browser behaviour on Windows and macOS.
- [ ] Avoid platform-specific shell commands in application code.
- [ ] Add a common application-services abstraction for future Unix-like platforms.

## 7. Emulator and frontend awareness

- [ ] Detect installed frontends and emulators.
- [ ] Show missing components without automatically downloading them.
- [ ] Link to official upstream release/project pages.
- [ ] Generic file staging for user-downloaded packages.
- [ ] Installation guidance where final Vita/3DS installation still requires VitaShell or equivalent manual action.
- [ ] Separate frontend, emulator, core, and transport concepts.

## 8. RetroAchievements

RetroAchievements must remain a capability rather than an assumption about a frontend.

- [ ] Represent RA support separately from emulator/frontend support.
- [ ] Identify RetroArch/core routes where appropriate.
- [x] Verify current 3DS libretro/Citra achievement status before exposing an achievement-first route.
- [x] Verify current DS melonDS/melonDS DS achievement-capable routes.
- [ ] Research native 3DS DS/GBA achievement integrations.
- [ ] Evaluate existing native DS + `rcheevos` work.
- [ ] Preserve native runtimes where they provide materially better compatibility/performance.
- [ ] Model Hardcore compatibility explicitly.
- [ ] Provide route recommendations without silently replacing the user's preferred runtime.

## 9. Library intelligence

- [ ] Automatic platform-directory discovery.
- [ ] Remote RomM library provider.
- [ ] Authenticated ROM download pipeline from RomM.
- [ ] Better duplicate detection.
- [ ] Optional hashes.
- [ ] Artwork and metadata.
- [ ] Per-game destination preview.
- [ ] Device-specific installed-state detection.
- [ ] Transfer planning against available storage.
- [ ] Multi-device comparison and recommended target.

## 10. Future devices

New consoles should be added as device/transport/target-profile implementations rather than separate applications.

Potential future targets currently shown in the selector include PSP and Mobile. Additional platforms can be added later without changing the core library/transport architecture.

## Current development rules

Do not make a milestone depend on assumptions about a user's filesystem. Discover the device or let the user select its root, validate it using safe signatures, and keep all machine-specific state outside Git.

Do not assume one emulator is best for a platform. Runtime selection should be based on detected capabilities and explicit user preference.

Do not make transport logic responsible for emulator, frontend, or format-conversion decisions.

Keep platform artwork data-driven and independent from backend logic. Missing artwork must never break functionality.

## Current research references

The current capability matrix is maintained in `docs/3DS_CAPABILITY_MATRIX.md`. It records conclusions from upstream project documentation and current RetroAchievements support information. When implementation choices change, update the matrix first and then update the corresponding code/milestone.

## Runtime preference rule

Runtime preference expresses what the user values most. It must never force an unavailable or incompatible runtime. Platform routing should intersect the user's preference with the target's detected capabilities and present the resulting recommendation transparently.

## UI redesign rule

The launch selector establishes the active handheld context and library provider. The selected management workspace may still expose cross-device status and global tools, but device-specific controls, target profiles, transports, and runtime preferences should remain compartmentalized behind their device profile.
