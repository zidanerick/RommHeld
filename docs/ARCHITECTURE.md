# RommHeld Architecture

RommHeld is a single-process PySide6 desktop application that presents one game library across multiple handheld targets. Device transport, package preparation, library access and UI presentation are intentionally separate concerns.

The current codebase is in a controlled migration away from its original Vita-first UI. The target architecture and the migration sequence are documented in `UX_REFACTOR_PLAN.md`; visual and interaction rules live in `DESIGN_SYSTEM.md`.

## Runtime entry path

The active application starts at:

```text
launcher.py
    |
    +--> PlatformSelectorDialog
    |       |
    |       +--> local library selection
    |       +--> RomM server selection / connection check
    |
    v
WorkspaceDashboardWindow
    |
    +--> ManagementShell
    |       +--> Library
    |       +--> Device
    |       +--> Setup
    |       +--> Queue
    |       +--> Tools
    |       +--> Settings
    |
    +--> target-specific widgets and dialogs
```

`WorkspaceDashboardWindow` currently resolves through `audited_workspace.py` and `workspace_dashboard.py`, which still inherit selected behavior from the original Vita UI in `app.py` / `ui.py`. That inheritance chain is transitional, not the desired final architecture. It must be collapsed only after the active library and device workflows have been extracted into standalone widgets.

## Major boundaries

### Library providers

RommHeld currently supports two library modes.

#### Local library

`romm.py` scans a configured local ROM root and produces `Game` records. Platform names are mapped through `mappings.py`.

#### RomM server

Remote library work is split across:

- `romm_api.py`: small authenticated API helpers and connection checks
- `romm_remote.py`: RomM game mapping, authenticated download and artwork URL handling
- `romm_remote_worker.py`: background paginated library work
- `romm_library_cache.py`: lightweight cached result pages
- `three_ds_library.py`: current progressive RomM browser for 3DS-compatible targets

Remote library queries are paginated and filtered rather than relying on one very large cross-platform response.

## Target and runtime selection

A library item is not itself a deployment decision. RommHeld keeps these concepts separate:

```text
Library item
    |
    v
Compatible target profiles
    |
    +--> native runtime
    +--> frontend/emulator route
    +--> package/container route
    |
    v
Chosen destination
    |
    v
Transport
```

Key modules include:

- `target_profiles.py`: shared target-profile concepts
- `three_ds_targets.py`: current 3DS destination and target mapping
- `preferences.py`: user runtime priorities such as native, compatibility or RetroAchievements
- `emulators.py`: emulator/frontend component definitions

Runtime preference is advisory. The final route must intersect user preference with actual platform and target capabilities.

## Device and transport layer

### PlayStation Vita

Relevant modules:

- `vita.py`: mount detection and storage information
- `transfers.py` / `file_transfer.py`: cancellable local file copies
- `vita_setup.py`: Vita setup and runtime preparation UI

Vita transfer destinations remain explicit. PSP and PS1 retain their Adrenaline locations, while other supported platforms can map to RetroFlow/runtime-specific destinations.

### Nintendo 3DS

Relevant modules:

- `three_ds_ftp.py`: FTP transport, remote-root enforcement, directory creation, skip/resume/cancellation and final size verification
- `three_ds_manager.py`: 3DS transfer/management UI
- `three_ds_setup.py`: 3DS setup workflow
- `three_ds_paths.py`: path helpers
- `storage_validation.py`: mounted-storage validation

FTP transport does not decide which runtime or package format a game should use.

### FBI Remote Install

`fbi_remote_install.py` implements FBI's URL-receive workflow:

1. RommHeld starts a temporary local HTTP server for the CIA.
2. RommHeld sends the CIA URL to FBI's network receiver.
3. FBI requests the file from the PC.
4. RommHeld observes the request/transfer lifecycle and then tears the server down.

`firewall.py` provides temporary host-firewall access where required. On supported Linux systems it can request a narrowly scoped rule through Polkit for the selected 3DS address and temporary TCP port, then remove that rule during cleanup.

The firewall layer is transport support. It must not be embedded into package-generation logic.

## Package preparation

### Native GBA / AGB_FIRM

Relevant modules:

- `gba_vc.py`: GBA input preparation and native CIA build request
- `gba_assets.py`: GBA packaging artwork helpers
- `gba_boot_logo.py`: neutral fallback / donor-asset handling boundary
- `gba_vc_deploy.py`: user-facing package-and-deploy workflow
- `three_ds_vc.py`: shared 3DS Virtual Console/package concepts

Generated native GBA CIAs target Nintendo's AGB_FIRM runtime. Packaging may use ROM and artwork obtained from the configured RomM instance.

RommHeld does not automatically download proprietary Nintendo donor assets or copyrighted official CIAs. User-supplied, lawfully obtained donor/official files remain explicit inputs where required.

## Storage detection and validation

Storage discovery and validation are separate operations:

- `storage_detection.py`: discover candidate mounted storage
- `storage_validation.py`: inspect a selected root using known safe signatures and return a confidence/result type
- `local_storage.py` / `local_storage_ui.py`: local/removable-storage workflows

Machine-specific paths, removable-media roots, IP addresses and credentials must remain outside Git.

## Configuration

`config.py` owns local per-user configuration. `library_sources.py` provides the library-source abstraction and persistence helpers.

Current configuration can include:

- selected handheld workspace
- local library path or RomM connection data
- device connection settings
- mounted-storage roots
- platform mappings
- runtime preferences

Credentials are local application state and must never be committed. Secure credential-store migration remains separate from UI styling work.

## UI architecture

### Design system

Shared visual values live in:

- `design_tokens.py`: palette, spacing, radii and manufacturer-family accents
- `theme.py`: application-wide neutral Qt styling
- `ui_components.py`: reusable presentation widgets
- `platform_assets.py`: console artwork/logo registry

Manufacturer-family colour is a navigation/orientation accent only:

- Nintendo: red
- Sony / PlayStation: blue
- Xbox: green
- Sega: blue

Large content surfaces remain neutral.

### Management shell

`management_shell.py` provides the shared left-sidebar shell. The shell owns navigation and presentation state but not transfer, storage or package logic.

The active pages are currently built by `workspace_dashboard.py`, with correctness/specialized 3DS behavior in `audited_workspace.py`. The long-term goal is to fold that behavior into one final workspace implementation and remove the transitional inheritance layers.

## Worker and thread rules

Network, artwork, library and transfer work must not block the UI thread.

Every worker has an ownership rule:

1. the owning widget keeps a reference while the worker is active;
2. cancellation is used where the backend supports it;
3. bounded operations are allowed to finish during shutdown when interruption is not possible;
4. the owner must not be destroyed while a `QThread` is still running.

A clean shutdown is more important than forcing a one-second timeout that can leave a live thread behind.

## Safety and integrity rules

1. Unknown destination mappings fail safely rather than copying to a guessed path.
2. Existing same-size files may be skipped instead of recopied.
3. Transfers support cancellation where practical.
4. Completed transfers receive a final size check when the transport exposes remote size.
5. Available storage is checked before transfers where reliable free-space information exists.
6. Archive extraction rejects absolute paths and traversal outside the intended root.
7. Network credentials are sent only to their intended configured service.
8. RomM bearer credentials are not forwarded to unrelated external artwork hosts.
9. Optional remote artwork must never be required for core functionality.
10. Transport code does not silently choose a runtime, emulator or package format.
11. Package preparation does not silently install proprietary or executable components from untrusted mirrors.
12. UI refactors must preserve transfer overwrite, verification, cancellation and credential semantics.

## Desired end state

The UI migration is complete when the active path is effectively:

```text
launcher.py
    -> WorkspaceDashboardWindow
        -> ManagementShell
        -> standalone library widget
        -> standalone device/setup pages
        -> target-specific deployment dialogs
```

At that point the original Vita-oriented `MainWindow` inheritance can be retired without losing features, and compatibility modules can be removed deliberately rather than guessed to be unused.
