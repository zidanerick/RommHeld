# RommHeld Architecture

RommHeld is a single-process PySide6 desktop application that presents game libraries across multiple handheld targets. Library access, target/runtime selection, package preparation, transport and UI presentation are separate concerns.

Visual and interaction rules live in `DESIGN_SYSTEM.md`. Current refactor and validation status lives in `UX_REFACTOR_PLAN.md`.

## Runtime entry path

```text
launcher.py
    |
    +--> PlatformSelectorDialog
    |       +--> local library source
    |       +--> RomM server source / connection check
    |
    v
WorkspaceDashboardWindow (QMainWindow)
    |
    v
ManagementShell
    |
    +--> Library
    +--> Device
    +--> Setup
    +--> Queue
    +--> Tools
    +--> Settings
```

`run.sh` executes `launcher.py`. The root `romm_vita_manager.py` script is only a compatibility entry point and forwards to the same launcher.

The former Vita-specific application modules `ui.py` and `app.py` have been removed. The active workspace has no legacy `MainWindow` inheritance or compatibility dependency.

For library presentation:

- `LocalLibraryWidget` handles the current Vita/DS local-library surface.
- `ThreeDSLibraryWidget` handles the current progressive RomM-backed 3DS surface.
- `vita_library_support.py` owns reusable Vita destination, install-state and copy-worker behavior that was previously embedded in the old window module.

## Library providers

### Local library

`romm.py` scans a configured local ROM root and produces `Game` records. `mappings.py` supplies platform labels and existing Vita/RetroFlow mapping data.

`local_library.py` owns the active local library UI:

- search
- platform filtering
- Vita install-state filtering
- list/tile presentation
- selection summary
- Vita destination summary
- Vita copy/cancel workflow

DS can reuse the same presentation without claiming Vita-style install-state knowledge.

`vita_library_support.py` contains the reusable Vita copy worker, destination resolution, status checks and size formatting. These helpers have no application-shell responsibility.

### RomM server

Remote library work is split across:

- `romm_api.py`: authenticated API helpers and connection checks
- `romm_remote.py`: game mapping, downloads and artwork URL handling
- `romm_remote_worker.py`: background paginated library work
- `romm_library_cache.py`: lightweight cached result pages
- `three_ds_library.py`: progressive RomM browser for current 3DS-compatible targets

Remote queries are paginated and filtered. Artwork authentication is restricted to the configured RomM host.

## Target and runtime selection

A library item is not a deployment decision:

```text
Library item
    -> compatible target profiles
    -> chosen runtime/package route
    -> destination
    -> transport
```

Relevant modules:

- `target_profiles.py`
- `three_ds_targets.py`
- `preferences.py`
- `emulators.py`

Runtime preference is advisory. The selected route must still be supported by the platform and target.

## Device and transport layer

### PlayStation Vita

- `vita.py`: mount detection and storage information
- `transfers.py` / `file_transfer.py`: cancellable local copying
- `vita_library_support.py`: Vita destination/status/copy helpers
- `local_library.py`: active library/deployment presentation
- `send_file_dialog.py`: explicit single-file transfer workflow
- `vita_setup.py`: Vita setup/runtime preparation

PSP and PS1 retain their Adrenaline paths. Other supported systems can map to RetroFlow/runtime-specific destinations.

### Nintendo 3DS

- `three_ds_ftp.py`: FTP transport, remote-root enforcement, creation, skip/resume/cancellation and size verification
- `three_ds_manager.py`: direct 3DS transfer/management UI
- `three_ds_setup.py`: guided storage/transport/FBI-readiness setup workflow
- `three_ds_paths.py`: path helpers
- `storage_validation.py`: mounted-storage validation

FTP transport does not choose runtime or package format. Setup keeps FTP connectivity and FBI Remote Install readiness explicit rather than treating them as one state.

### FBI Remote Install

`fbi_remote_install.py` implements FBI's URL-receive workflow:

1. start a temporary HTTP server for the CIA;
2. send the URL to FBI's network receiver;
3. FBI requests the file from the PC;
4. RommHeld tracks successful transfer completion;
5. temporary HTTP/firewall resources are cleaned up.

`firewall.py` can request narrowly scoped temporary Linux firewall access through Polkit and remove it during cleanup.

## Package preparation

### Native GBA / AGB_FIRM

- `gba_vc.py`: GBA input preparation and native CIA build request
- `gba_assets.py`: packaging artwork helpers
- `gba_boot_logo.py`: neutral fallback/donor boundary
- `gba_vc_deploy.py`: package-and-deploy workflow
- `three_ds_vc.py`: shared 3DS VC/package concepts

Generated GBA CIAs target Nintendo's native AGB_FIRM runtime.

RommHeld does not automatically download proprietary Nintendo donor assets or copyrighted official CIAs. User-supplied, lawfully obtained files remain explicit inputs where required.

## Storage detection and validation

- `storage_detection.py`: candidate mounted storage discovery
- `storage_validation.py`: conservative selected-root validation
- `local_storage.py`: removable-storage path and capacity helpers
- `local_storage_ui.py`: card-based removable-storage selection and transfer workflow

Machine-specific paths, removable-media roots, IP addresses and credentials stay outside Git.

## Configuration

`config.py` owns per-user configuration. `library_sources.py` owns library-source selection/persistence.

Configuration may include:

- active handheld workspace
- local library or RomM source
- device connection settings
- removable-storage roots
- platform mappings
- runtime preferences

Credentials must never be committed. Secure credential-store migration remains a separate task.

## UI architecture

### Design system

- `design_tokens.py`: palette, spacing, radii and manufacturer-family accents
- `theme.py`: application-wide Qt styling
- `ui_components.py`: reusable surfaces/actions/status components
- `platform_assets.py`: console artwork/logo registry

Manufacturer-family color is an orientation accent:

- Nintendo: red
- Sony / PlayStation: blue
- Xbox: green
- Sega: blue

Large content surfaces remain neutral.

### Management shell

`management_shell.py` owns:

- persistent sidebar
- active-console branding
- section navigation
- device summary labels
- content stack

It does not own transport, storage or package logic.

`workspace_dashboard.py` is the composition root for the active desktop window. It constructs target pages and delegates library behavior to standalone widgets rather than inheriting a console-specific application window.

The obsolete `platform_selector.py` compatibility shim has been removed. All current callers use `console_selector.py` directly.

## Worker and thread rules

Network, artwork, library and transfer work must not block the UI thread.

Every worker follows these rules:

1. the owning widget keeps a reference while active;
2. cancellation/interruption is used where supported;
3. bounded operations may finish during shutdown when immediate interruption is impossible;
4. an owning widget must not be destroyed while a `QThread` is still running.

A clean shutdown is preferred over arbitrary short waits that can leave live Qt threads behind.

## Safety and integrity rules

1. Unknown destinations fail safely rather than guessing.
2. Existing same-size files may be skipped.
3. Transfers support cancellation where practical.
4. Completed transfers receive final size verification when supported.
5. Available storage is checked before transfers where reliable.
6. Archive extraction rejects traversal and absolute-path escape.
7. Credentials are sent only to their intended configured service.
8. RomM bearer tokens are not forwarded to unrelated artwork hosts.
9. Optional remote artwork is never required for core operation.
10. Transport code does not silently choose runtime/package format.
11. Package preparation does not silently install proprietary executable content from untrusted mirrors.
12. UI refactors preserve overwrite, verification, cancellation and credential semantics.

## Architecture status

The structural refactor is complete enough that further broad restructuring should stop before merge:

- the unified workspace is a direct `QMainWindow`;
- Vita/local library behavior is standalone;
- the useful Vita copy/status helpers are in a focused module;
- legacy `ui.py`, `app.py` and `platform_selector.py` surfaces are removed;
- Send File, removable-storage, Vita Setup, 3DS Setup and 3DS Manager use the shared design language;
- AST regression tests prevent the removed legacy module dependencies from returning.

The remaining pre-merge work is primarily runtime regression testing on real Vita and Nintendo 3DS hardware, plus fixes for defects found by those tests. New architecture work should require a concrete functional reason rather than continuing the refactor for its own sake.
