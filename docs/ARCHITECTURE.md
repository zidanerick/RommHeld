# RommHeld Architecture

RommHeld is a single-process PySide6 desktop application that presents game libraries across multiple handheld targets. Library access, target/runtime selection, package preparation, transport and UI presentation are separate concerns.

Visual and interaction rules live in `DESIGN_SYSTEM.md`. Current refactor and validation status lives in `UX_REFACTOR_PLAN.md`.

## Runtime entry path

```text
launcher.py
    |
    +--> if first setup / invalid saved configuration:
    |       PlatformSelectorDialog
    |           +--> handheld workspace
    |           +--> local library source
    |           +--> RomM server source / connection check
    |
    +--> otherwise: reuse saved active workspace directly
    |
    v
WorkspaceDashboardWindow (QMainWindow)
    |
    v
ManagementShell
    |
    +--> Library
    +--> Device
    +--> Settings
            |
            +--> contextual setup / advanced device dialogs
```

`run.sh` executes `launcher.py`. The root `romm_vita_manager.py` script is only a compatibility entry point and forwards to the same launcher.

A valid completed setup opens directly into the saved workspace on normal launches. `PlatformSelectorDialog` remains the onboarding/reconfiguration surface and is also reachable through `Switch handheld` from the shell.

The former Vita-specific application modules `ui.py` and `app.py` have been removed. The active workspace has no legacy `MainWindow` inheritance or compatibility dependency.

For library presentation:

- `LocalLibraryWidget` handles the current Vita/DS local-library surface.
- `ThreeDSLibraryWidget` handles current 3DS-compatible browsing from either RomM or a configured local library.
- `vita_library_support.py` owns reusable Vita destination, mounted-filesystem install-state and local copy-worker behavior.
- `vita_ftp_library.py` reuses the same Vita destination mapping for VitaShell FTP batch deployment.

## Library providers

### Local library

`romm.py` scans a configured local ROM root and produces `Game` records. `mappings.py` supplies platform labels and existing Vita/RetroFlow mapping data.

`local_library.py` owns the active Vita/DS local library UI:

- search
- platform filtering with friendly mapped labels while retaining exact source keys internally
- Vita install-state filtering only when VitaShell USB storage is mounted
- single-list presentation
- selection summary
- Vita destination summary
- Vita copy/cancel workflow
- VitaShell USB or VitaShell FTP transport selection for normal Vita library deployment
- the normal Vita copy action beside the current library selection

DS can reuse the same presentation without claiming Vita-style install-state knowledge.

Mounted Vita storage supports cheap local install-state inspection, but the default `All games` browse path intentionally does not probe every destination while rendering rows. Status checks are performed when the user selects an install-state filter or when selected games are evaluated for copying, and results are cached for the current view. The cache is invalidated when device, configuration, transport or transfer state changes. If the USB mount disappears, install-state filtering is disabled and a stale status selection is reset so the library does not appear empty merely because the device disconnected.

VitaShell FTP does not expose an equivalent efficient bulk-status operation, so FTP mode checks individual remote destinations as transfers start rather than pretending the entire library has been pre-scanned remotely.

`vita_library_support.py` contains the reusable local Vita copy worker, destination resolution, status checks and size formatting. `vita_ftp_library.py` maps those same destinations to `ux0:/...` and owns the FTP batch worker. Neither helper has application-shell responsibility.

For the 3DS workspace, `three_ds_library.py` can consume the same local `Game` records through its target-specific master/detail surface. Local games are normalized to a platform slug, filtered to compatible direct targets, and presented through the same target/preference model used for RomM records. This keeps library-source choice separate from 3DS runtime/destination choice without forcing the 3DS workflow through the Vita/DS presentation widget.

### RomM server

Remote library work is split across:

- `romm_api.py`: authenticated API helpers and connection checks
- `romm_remote.py`: game mapping, downloads and artwork URL handling
- `romm_remote_worker.py`: background paginated library work
- `romm_library_cache.py`: lightweight cached result pages
- `three_ds_library.py`: progressive RomM browser for current 3DS-compatible targets and the shared 3DS master/detail presentation

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

`three_ds_targets.py` now distinguishes dedicated/native runtime routes from package-generation routes. In particular, direct `open_agb_firm` GBA deployment is separate from generated HOME Menu GBA CIAs using AGB_FIRM. NDS/TWiLight, Virtual Boy/Red Viper, and N64/DaedalusX64 are modelled as explicit targets rather than being forced through RetroArch.

Runtime preference is advisory. `preferred_target_key()` can recommend compatibility, native, or RetroAchievements-oriented routes only from targets the platform actually exposes. Per-title selection remains authoritative. `ThreeDSLibraryWidget` applies that preference using a normalized platform slug for both RomM and local records.

## Device and transport layer

### PlayStation Vita

- `vita.py`: VitaShell USB mount detection and storage information
- `transfers.py` / `file_transfer.py`: cancellable, destination-preserving local copying
- `vita_paths.py`: canonical mapping from `ux0:/...` to the mounted ux0 root
- `vita_library_support.py`: Vita destination/status/local-copy helpers
- `vita_ftp.py`: protocol-specific VitaShell FTP transport
- `vita_ftp_library.py`: VitaShell FTP batch deployment using the same destination mappings as USB
- `local_library.py`: active library/deployment presentation and USB/FTP selection
- `send_file_dialog.py`: explicit single-file transfer workflow over USB or FTP
- `vita_setup.py`: Vita setup/runtime preparation

VitaShell USB is the preferred default on handheld Vita systems because the mounted filesystem provides reliable capacity checks, cheap install-state inspection and direct local filesystem semantics. RommHeld treats the detected mount root as `ux0:` itself rather than adding another `ux0` directory.

VitaShell FTP is the secondary wireless transport and the practical transport for PlayStation TV. The current VitaShell/ftpvitalib protocol uses port `1337` by default and exposes mountpoints with paths such as `/ux0:/data/...`. Its command set differs materially from the 3DS `ftpd` server: VitaShell does not provide `REST` resume, `MLSD` or usable `ABOR` semantics, and some replies are non-standard. For that reason `vita_ftp.py` is intentionally separate from `three_ds_ftp.py` instead of forcing both devices through one generic FTP implementation.

Vita FTP uploads are confined to the configured `/ux0:` root. They stage into a temporary remote file, verify size, then replace the destination. Existing different-size destinations are first moved to a temporary backup and restored if the final swap or verification fails. Cancellation drops the VitaShell control connection when necessary and cleans the temporary upload through a fresh FTP session because the server does not implement `ABOR`.

PSP and PS1 retain their Adrenaline paths. Other supported systems can map to RetroFlow/runtime-specific destinations. The chosen Vita transport changes only how bytes reach the device, not the destination/runtime decision.

### Nintendo 3DS

- `three_ds_ftp.py`: FTP transport, remote-root enforcement, creation, skip/resume/cancellation and size verification
- `three_ds_storage.py`: mounted 3DS SD-card root/configuration backend
- `three_ds_manager.py`: direct 3DS transfer/management UI
- `three_ds_setup.py`: guided storage/transport/FBI-readiness setup workflow
- `three_ds_paths.py`: path helpers
- `storage_validation.py`: mounted-storage validation
- `three_ds_apps.py`: declarative 3DS runtime/homebrew inventory and conservative SD-marker detection
- `three_ds_readiness.py`: required/recommended/optional workflow-readiness evaluation
- `three_ds_packages.py`: narrow, verified mounted-SD staging for explicitly supported simple 3DSX packages
- `three_ds_readiness_ui.py`: focused readiness/runtime-management dialog built on the non-UI services above

The Device page treats a validated mounted SD/microSD card as a direct offline filesystem route and configured mtheall `ftpd` as the wireless live-console route. A card-reader mount is not labelled as USB because Nintendo 3DS systems do not expose a standard USB mass-storage mode. Either a validated mounted SD route or configured ftpd endpoint makes the filesystem route ready for Device-page emphasis.

The recommended live filesystem server is mtheall `ftpd`. RommHeld defaults to port `5000`, tells users to open `ftpd` and leave it running, and translates common timeout/refusal/authentication errors into console-side remediation. The 3DS backend can use `MLSD` with fallback listing, `REST` resume where supported, `ABOR` cancellation, `SIZE` verification and the configured remote-root boundary. Failed connection setup closes partially opened FTP sockets.

FTP transport does not choose runtime or package format. Setup keeps FTP connectivity and FBI Remote Install readiness explicit rather than treating them as one state. For installable CIA packages, FBI Remote Install remains the direct installation route; FTP is the filesystem-copy route.

3DS readiness also does not equate “not visible in the SD filesystem” with “not installed”. Applications that may exist only as installed CIA titles are reported as needing on-console confirmation when required.

The active Device page exposes guided Connection setup, Mounted SD files, and contextual Runtime readiness. The readiness dialog remains a focused secondary surface rather than another permanent navigation destination.

### 3DS runtime configuration

Runtime configuration remains separate from transport and package installation.

- `open_agb_config.py`: current-format open_agb_firm configuration parser/editor, validation, backup and atomic replacement
- `open_agb_settings.py`: focused Qt settings dialog over that adapter

The adapter edits only a documented subset of current open_agb_firm settings, preserves unknown keys/comments, and refuses legacy or unknown configuration formats. TWiLight Menu++, Red Viper, RetroArch, and DaedalusX64 settings remain owned by those applications until a concrete RommHeld workflow justifies a similarly narrow adapter.

### 3DS homebrew staging boundary

RommHeld is not a general homebrew package manager. `three_ds_packages.py` permits automatic mounted-SD staging only for explicitly whitelisted simple single-file packages whose upstream release asset can be resolved and audited predictably.

The current direct-staging allowlist is:

- ftpd 3DSX
- Universal-Updater 3DSX
- Red Viper 3DSX
- FBI Homebrew Launcher 3DSX
- Checkpoint Homebrew Launcher 3DSX

The FBI and Checkpoint entries prepare their `.3dsx` Homebrew Launcher builds on the mounted SD card. This is not evidence that their CIA titles are installed on the console and is not presented as such in readiness state.

The staging service:

1. resolves an exact asset from the latest stable upstream GitHub release;
2. rejects unexpected download hosts and unreasonable package sizes;
3. verifies published asset size;
4. verifies SHA-256 when upstream publishes a digest;
5. requires a high-confidence 3DS SD-card root before writing;
6. backs up an existing target;
7. stages through a temporary file and atomically replaces the target;
8. supports cancellation during download.

`three_ds_readiness_ui.py` adds an assisted tier for applications whose installation policy delegates complex or multi-file work to Universal-Updater. If Universal-Updater is absent, RommHeld can prepare its verified 3DSX bootstrap using the same direct-staging service. If it is already detected, the primary action shows the exact on-console next step: launch Universal-Updater and search for the selected application. RommHeld does not duplicate Universal-Updater's maintained archive extraction, CIA installation, updater scripts or system-sensitive file handling.

Complex packages such as TWiLight Menu++, RetroArch and DaedalusX64 remain updater-assisted rather than being partially installed from a convenient but incomplete standalone asset. `open_agb_firm` remains updater/manual because its bundle and configuration format require version-aware handling. GodMode9 remains updater/guide driven. Luma3DS, the Homebrew Launcher exploit/bootstrap foundation and other boot-chain components remain guide-only and are never automatically replaced by RommHeld. Console-specific DSP firmware is never downloaded and must be generated from the user's own console.

### FBI Remote Install

`fbi_remote_install.py` implements FBI's URL-receive workflow:

1. start a temporary HTTP server for the CIA;
2. send the URL to FBI's network receiver;
3. FBI requests the file from the PC;
4. RommHeld tracks successful transfer completion;
5. temporary HTTP/firewall resources are cleaned up.

`firewall.py` can request narrowly scoped temporary Linux firewall access through Polkit and remove it during cleanup.

### Nintendo DS

Nintendo DS deployment remains removable-storage first. RommHeld validates the selected SD/flashcard root and copies to that storage rather than assuming an FTP server or one particular flashcard model. Optional DS-side FTP software is not a core transport dependency.

## Package preparation

### Native GBA / AGB_FIRM

- `gba_vc.py`: GBA input preparation and native CIA build request
- `gba_assets.py`: packaging artwork helpers
- `gba_boot_logo.py`: neutral fallback/donor boundary
- `gba_vc_deploy.py`: package-and-deploy workflow
- `three_ds_vc.py`: shared 3DS VC/package concepts

Generated GBA CIAs target Nintendo's native AGB_FIRM runtime. This package-generation workflow is distinct from copying a `.gba` ROM for direct launch through open_agb_firm.

RommHeld does not automatically download proprietary Nintendo donor assets or copyrighted official CIAs. User-supplied, lawfully obtained files remain explicit inputs where required.

## Storage detection and validation

- `storage_detection.py`: candidate mounted storage discovery
- `storage_validation.py`: conservative selected-root validation
- `local_storage.py`: removable-storage path and capacity helpers
- `local_storage_ui.py`: card-based removable-storage selection and transfer workflow

Machine-specific paths, removable-media roots, IP addresses and credentials stay outside Git.

Storage validation remains distinct from application detection. A ROM directory is content evidence, not proof that a matching runtime is installed.

## Configuration

`config.py` owns per-user configuration. `library_sources.py` owns library-source selection/persistence.

Configuration may include:

- active handheld workspace
- local library or RomM source
- device connection settings, including 3DS ftpd, mounted 3DS storage and VitaShell FTP endpoints
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
- core section navigation
- compact active-device summary
- content stack

It does not own transport, storage or package logic.

`workspace_dashboard.py` is the composition root for the active desktop window. It exposes only Library, Device and Settings as permanent destinations. Console-specific setup and advanced device tools are launched contextually from those pages. Library behavior remains delegated to standalone widgets rather than inheriting a console-specific application window.

Primary button emphasis can change with readiness state without changing handlers: Device highlights configuration before a usable route exists and the relevant next action afterward. For 3DS, either configured ftpd or a validated mounted SD route counts as usable. Settings similarly emphasizes RomM connection testing when credentials are unverified or changed, then shifts emphasis to saving after a successful test. Verification remains advisory rather than a save gate.

RomM credentials can be tested asynchronously from Settings using the same `RomMConnectionWorker` used by onboarding. Workspace switching is blocked while that bounded test is active so its Qt worker is not orphaned.

The obsolete `platform_selector.py` compatibility shim has been removed. All current callers use `console_selector.py` directly.

## Worker and thread rules

Network, artwork, library and transfer work must not block the UI thread.

Every worker follows these rules:

1. the owning widget keeps a reference while active;
2. cancellation/interruption is used where supported;
3. bounded operations may finish during shutdown when immediate interruption is impossible;
4. an owning widget must not be destroyed while a `QThread` is still running.

The 3DS package-staging worker follows the same lifecycle. Package resolution is a bounded network operation and package download is cancellation-aware. Closing the readiness dialog requests cancellation and keeps the dialog alive until its worker finishes.

VitaShell FTP workers use the same ownership rules. Since VitaShell does not support FTP `ABOR`, cancellation may require closing the current FTP control connection and using a short cleanup connection rather than waiting for a protocol-level abort response.

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
13. Runtime/homebrew detection is evidence-based and does not claim installed-title certainty from missing SD markers.
14. Device-side configuration adapters must be narrow, version-aware, backed up before replacement, and preserve unrelated settings.
15. Automatic homebrew staging must use an explicit allowlist and upstream release verification; it must not expand into CFW/bootstrap management.
16. Device-specific FTP capabilities are not assumed to be interchangeable. Resume, listing, cancellation and reply handling follow the actual server used by that console.

## Architecture status

The structural refactor is complete enough that further broad restructuring should stop before merge:

- the unified workspace is a direct `QMainWindow`;
- configured startup enters the saved workspace directly instead of replaying onboarding;
- Vita/DS local library behavior is standalone and exposes its primary Vita copy action in-context;
- the 3DS master/detail library can use either RomM or a configured local library without collapsing runtime/target logic into the source provider;
- Vita library and explicit-file transfers support VitaShell USB as the preferred handheld path and VitaShell FTP as the wireless/PSTV path;
- the useful Vita destination/status/local-copy helpers remain focused, while VitaShell FTP lives in its own protocol-specific transport module;
- the permanent shell is reduced to Library, Device and Settings;
- setup and advanced tools are contextual rather than placeholder navigation destinations;
- legacy `ui.py`, `app.py` and `platform_selector.py` surfaces are removed;
- Send File, removable-storage, Vita Setup, 3DS Setup and 3DS Manager use the shared design language;
- 3DS runtime/readiness/configuration/package-staging responsibilities are isolated from transport and package-generation code;
- 3DS readiness and mounted-storage management are reachable contextually from Device without becoming permanent pages;
- AST/source regression tests prevent removed legacy dependencies and placeholder navigation from returning.

The remaining pre-merge UI work is primarily desktop rendering/lifecycle validation and defect-driven polish, while device-dependent behavior still requires real Vita and Nintendo 3DS regression testing. VitaShell FTP and the newer 3DS runtime/deployment routes cannot be considered hardware-validated from CI alone. New architecture work should require a concrete functional reason rather than continuing the refactor for its own sake.
