# RommHeld Development Milestones

RommHeld is a cross-platform PySide6 desktop application for managing a local or RomM-backed game library across handheld targets. GitHub is the source of truth for product behavior and design decisions. Device paths, IP addresses, credentials, ROMs and removable-media contents remain local state.

Visual work must follow `DESIGN_SYSTEM.md`. Completed refactor work and remaining hardware validation are tracked in `UX_REFACTOR_PLAN.md`.

## 0. Foundation

- [x] Rename the product to RommHeld.
- [x] Protect `main` from force-push/deletion.
- [x] Keep the Vita implementation working while introducing new handheld targets.
- [x] Move user configuration outside the repository.
- [x] Add platform-aware config/cache/temp services.
- [x] Preserve migration from the original Linux config location.
- [x] Establish separate library, target, transport and runtime concepts.
- [ ] Complete the internal namespace migration from `romm_vita_manager` to a neutral RommHeld package name.

## 1. Library providers

### Local

- [x] Scan a configured local ROM root.
- [x] Identify source platform from the library layout.
- [x] Persist platform mappings.
- [x] Search/filter local library in the active standalone local-library workflow.

### RomM

- [x] Save a RomM server URL and Client API Token locally.
- [x] Verify RomM connectivity asynchronously at startup.
- [x] Map RomM API responses into RommHeld game records.
- [x] Page remote results instead of requiring one giant library request.
- [x] Support remote search/platform filtering in the 3DS library.
- [x] Cache a bounded first page for responsive reopening.
- [x] Download authenticated ROM content for supported deployment workflows.
- [x] Load RomM-hosted artwork on demand.
- [x] Avoid forwarding RomM bearer credentials to unrelated artwork hosts.
- [ ] Generalise the progressive RomM browser so Vita/DS/future targets share the same library presentation layer.
- [ ] Move stored credentials to an OS credential/keyring service.

## 2. Transfer integrity

- [x] Cancellable chunked local transfers.
- [x] Same-size file skipping.
- [x] Different-size overwrite protection.
- [x] Post-transfer size verification where supported.
- [x] Free-space preflight where reliable space information exists.
- [x] Generic Send File workflow.
- [ ] Persistent transfer queue.
- [ ] Retry policy and per-item error history.
- [ ] Optional hashing for stronger duplicate detection.
- [ ] Common transport interface used by every target workflow.

## 3. PlayStation Vita

- [x] Dynamic Vita mount detection.
- [x] USB/VitaShell-oriented transfer workflow.
- [x] RetroFlow destination mappings.
- [x] Adrenaline PSP destination handling.
- [x] Adrenaline PS1 destination handling.
- [x] Vita setup/package workflow.
- [x] Runtime preference model available to Vita workspace.
- [x] Extract the Vita library from the legacy `MainWindow` into a standalone shared library widget.
- [x] Extract Vita destination/status/copy helpers into a focused support module.
- [x] Redesign the standalone Vita Send File workflow.
- [ ] Improve emulator/frontend capability detection.
- [ ] Model device capability independently from transport.

## 4. Nintendo 3DS transport

### FTP

- [x] FTP connection and directory browsing.
- [x] Configurable endpoint and remote root.
- [x] Safe remote-root/path handling.
- [x] Remote directory creation.
- [x] Same-size skip.
- [x] Different-size overwrite protection.
- [x] Resume when the server supports REST.
- [x] Cancellation.
- [x] Final remote-size verification.
- [x] Best-effort remote free-space reporting.
- [x] Physical hardware upload test.

### FBI Remote Install

- [x] Implement FBI Receive URLs over network protocol.
- [x] Serve a selected/generated CIA from a temporary local HTTP server.
- [x] Distinguish FBI acceptance from the subsequent HTTP download.
- [x] Choose a reachable local interface for the selected 3DS address.
- [x] Fall back across usable local HTTP ports.
- [x] Integrate temporary Linux firewall access.
- [x] Detect active UFW without requiring an unprivileged `ufw status` command.
- [x] Request narrowly scoped UFW changes through Polkit.
- [x] Restrict temporary access to the selected 3DS source address and TCP port.
- [x] Remove temporary firewall access during cleanup.
- [x] Validate the complete FBI workflow on physical hardware.

## 5. Nintendo 3DS library and targets

- [x] Dedicated progressive RomM library widget.
- [x] Search and platform filtering.
- [x] Artwork/details presentation.
- [x] Per-game compatible target selection.
- [x] Destination preview.
- [x] Local/remote deployment hand-off to 3DS manager.
- [x] Mounted-storage validation framework.
- [x] Record observed 3DS/DS storage signatures conservatively.
- [x] Runtime preference model: native, RetroAchievements, compatibility.
- [x] Redesign the 3DS Manager around connection, library and deployment cards.
- [x] Redesign 3DS Setup as a guided readiness workflow.
- [ ] Automatic removable-media detection with confidence reporting across supported desktop platforms.
- [ ] Complete target mappings from observed real layouts.
- [ ] Device-specific installed-state comparison for all 3DS targets.
- [ ] Apply runtime preferences automatically when recommending a target route.

## 6. Native GBA / Virtual Console preparation

- [x] Accept raw `.gba` input.
- [x] Extract `.gba` content from ZIP input.
- [x] Enforce supported raw ROM size limits.
- [x] Build native GBA CIA requests targeting AGB_FIRM.
- [x] Deterministic title-ID generation in the configured GBA VC range.
- [x] Provide a neutral non-Nintendo boot-logo fallback.
- [x] Use RomM artwork as package artwork input where available.
- [x] Offer FTP deployment for generated CIAs.
- [x] Offer FBI Remote Install for generated CIAs.
- [x] Validate generated CIA installation on physical hardware.
- [ ] Improve generated Home Menu icon/banner presentation while retaining original/non-proprietary assets.
- [ ] Official Virtual Console catalogue/matching workflow.
- [ ] Prefer a user-supplied/lawfully obtained official CIA when an official release is matched.

### Asset/legal boundary

RommHeld must not automatically download copyrighted Nintendo CIAs or proprietary donor/package assets. Official-release knowledge can inform a match, but acquisition remains user-controlled and lawful.

## 7. Nintendo DS / flashcard workspace

- [x] DS workspace exists in the shared shell.
- [x] User-selectable mounted SD root.
- [x] DS/flashcard storage validation support.
- [x] TWiLight Menu++ / nds-bootstrap / flashcard concepts represented in target research and UI.
- [x] DS runtime preference presentation.
- [x] Redesign the generic removable-storage transfer dialog.
- [ ] Automatic DS removable-media discovery.
- [ ] Complete DS target profiles and destination mappings.
- [ ] Standalone DS library/deployment workflow.
- [ ] Real-device transfer validation across representative flashcard layouts.

## 8. UI and design system

- [x] Handheld selection launch screen.
- [x] Library source selection.
- [x] Active handheld workspace context.
- [x] Data-driven handheld artwork registry.
- [x] Bundled offline device/logo assets.
- [x] Single-window management shell.
- [x] Canonical `DESIGN_SYSTEM.md` checked into the repository.
- [x] Central palette/spacing/brand tokens.
- [x] Manufacturer-family accents: Nintendo red, PlayStation blue, Xbox green, Sega blue.
- [x] Shared application stylesheet.
- [x] Persistent left-sidebar navigation replacing tab-first shell navigation.
- [x] Modernised handheld selector using shared tokens.
- [x] Remove abandoned transitional `device_dashboard.py`.
- [x] Remove its duplicate legacy `assets/icons` console asset set.
- [x] Replace selector hardware-photo `QThread` workers with asynchronous Qt networking.
- [x] Extract legacy Vita library/device UI into standalone widgets/modules.
- [x] Fold `audited_workspace.py` correctness behavior into the final workspace implementation and remove it.
- [x] Retire legacy `ui.py`, `app.py`, and `platform_selector.py` after callers migrated.
- [x] Apply shared components/primary-action styling to the remaining setup and deployment dialogs.
- [ ] Complete responsive/accessibility review across supported desktop sizes.

## 9. Worker and lifecycle reliability

- [x] RomM library work occurs off the UI thread.
- [x] Artwork/network enhancement is asynchronous.
- [x] Startup verifier no longer uses a fixed one-second shutdown wait that can destroy a live thread.
- [x] Selector hardware imagery no longer creates per-card `QThread` workers.
- [x] Harden the active 3DS/Vita/setup/transfer dialogs against unsafe close-during-worker destruction.
- [x] Add headless AST lifecycle/architecture regression coverage where Qt GUI instantiation is unavailable.
- [ ] Continue real-device close/cancel regression testing for every transport path.

## 10. Cross-platform desktop support

- [x] PySide6/Qt desktop UI.
- [x] Platform-aware config/cache/temp locations.
- [x] Qt-oriented removable-volume discovery groundwork.
- [ ] Windows packaging/build definition.
- [ ] macOS packaging/build definition.
- [ ] Linux distributable packaging/build definition.
- [ ] Validate removable-volume detection on Windows and macOS.
- [ ] Validate file/browser integration on Windows and macOS.
- [ ] Eliminate remaining Linux-specific shell assumptions from cross-platform paths.

## 11. Runtime and RetroAchievements awareness

RetroAchievements is a runtime/core capability, not a property of a frontend or transport.

- [x] Separate user runtime preference from transport selection.
- [x] Represent native/compatibility/achievement priority choices.
- [x] Keep 3DS native and achievement-capable routes conceptually separate.
- [x] Record DS achievement-capable emulator/core research separately from TWiLight/flashcard transport.
- [ ] Detect actual installed runtime/frontend capabilities.
- [ ] Intersect preference with detected capabilities when recommending routes.
- [ ] Model Hardcore compatibility explicitly where relevant.

## 12. Repository cleanup and architecture migration

- [x] Establish `ARCHITECTURE.md` as the current multi-handheld architecture description.
- [x] Establish `UX_REFACTOR_PLAN.md` as the refactor/validation status document.
- [x] Remove superseded `UI_REDESIGN.md` after folding its useful direction into canonical docs.
- [x] Remove abandoned dashboard implementations rather than maintaining parallel shells.
- [x] Remove duplicate legacy console icon files tied to abandoned UI paths.
- [x] Extract standalone library/device/transfer behavior from `ui.py` and `app.py`.
- [x] Collapse the active inheritance ladder into one final `WorkspaceDashboardWindow`.
- [x] Remove `audited_workspace.py` after its behavior was merged.
- [x] Remove `platform_selector.py` after compatibility imports were no longer required.
- [x] Convert root `romm_vita_manager.py` into a compatibility forwarder to `launcher.py`.
- [x] Add regression tests rejecting callers of removed legacy UI modules.
- [ ] Complete package namespace rename without breaking user configuration migration.

## Development rules

1. Do not hard-code a user's filesystem, device address or credentials.
2. Discover a device/storage target or let the user select it, then validate it conservatively.
3. Do not assume one emulator/runtime is universally best.
4. Keep transport separate from runtime and format conversion decisions.
5. Missing optional artwork must never break functionality.
6. Do not remove compatibility code until active callers have migrated.
7. Do not trade transfer verification/cancellation safety for visual cleanup.
8. New interface work follows `DESIGN_SYSTEM.md` and uses centralized tokens rather than ad hoc colours.
9. When a worker owns external resources such as FTP, HTTP servers or firewall rules, cleanup must complete before its owning thread/widget is destroyed.
10. After the current UI/refactor branch, prefer defect-driven changes from desktop/hardware regression testing over further structural churn.
