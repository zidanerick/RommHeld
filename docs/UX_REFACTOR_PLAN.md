# RommHeld UX and Repository Refactor Plan

Status: structural refactor complete; UX polish and hardware regression validation remain

Design authority: `docs/DESIGN_SYSTEM.md`

Baseline: `feature/ui-redesign` at `fddc07151d3105c6fee9a0217764973ecd200c4d`.

## Goal

RommHeld is moving from a Vita-first utility into a coherent multi-handheld desktop application. The refactor preserves working behavior while making the active architecture understandable, extensible and visually consistent.

Broad architecture restructuring is complete. Current UX work is a focused simplification/polish pass: reduce permanent navigation, keep primary actions beside the user's selection, make device readiness obvious, and progressively disclose setup/advanced controls. Transport, package-generation and runtime boundaries remain unchanged.

## Current active architecture

```text
launcher.py
    -> PlatformSelectorDialog only for first setup / invalid saved configuration
    -> otherwise reuse the saved active workspace directly
    -> WorkspaceDashboardWindow (QMainWindow)
        -> ManagementShell
            -> Library
                -> LocalLibraryWidget for Vita / DS local-library presentation
                -> ThreeDSLibraryWidget for RomM or local 3DS-compatible browsing
            -> Device
                -> connection/storage state
                -> contextual Vita / 3DS setup and advanced device actions
                -> service-driven DS / DSi runtime health and repair guidance
            -> Settings
                -> library source
                -> RomM connection verification
                -> runtime preference
```

Supporting focused modules include:

- `vita_library_support.py` for Vita destination/status/copy behavior
- `send_file_dialog.py` for explicit Vita single-file transfers
- `local_storage_ui.py` for removable-storage workflows
- `three_ds_manager.py` for 3DS browsing/deployment
- `three_ds_setup.py` for guided 3DS readiness
- `vita_setup.py` for Vita package/runtime preparation
- `ds_runtime.py` and `ds_repair.py` for DS/DSi health and repair semantics
- `ds_runtime_ui.py` for presentation of service-supplied DS/DSi health, evidence and actions

The old `ui.py`, `app.py`, `platform_selector.py`, `audited_workspace.py` and `device_dashboard.py` surfaces have been removed. The root `romm_vita_manager.py` script forwards to the current launcher rather than exposing a second application architecture.

## Refactor rules

- Preserve feature behavior before removing compatibility code.
- Keep platform branding in shared design tokens.
- Keep transport, packaging and runtime-selection logic separate even when presented on one screen.
- Prefer standalone widgets over inheritance from console-specific windows.
- Keep common workflows simple and expose advanced controls contextually.
- A normal deployment action should live beside the selected game rather than requiring navigation to another page.
- Every cleanup step must leave the branch compilable and testable.
- Do not add temporary files that are not actively used.
- Avoid structural rewrites unless runtime/hardware testing demonstrates a concrete need.

## Phase 1: design foundation

Status: complete.

Implemented:

- `romm_vita_manager/design_tokens.py`
- `romm_vita_manager/theme.py`
- `romm_vita_manager/ui_components.py`
- `docs/DESIGN_SYSTEM.md`

The UI uses a neutral graphite base with restrained manufacturer accents:

- Nintendo red
- PlayStation/Sony blue
- Xbox green
- Sega blue

Platform color is an orientation/accent tool, not a full-screen background.

Shared primary buttons now have distinct hover, pressed, disabled and keyboard-focus states rather than relying on a static accent fill. Shared status pills use restrained semantic tones so connected/ready, busy/action-needed and actual error states remain distinguishable without colouring every surface.

Shared device-health presentation now includes explicit health-state badges, overall summaries, component rows, progressive evidence disclosure, manual/system-sensitive notices, repair-plan review, inline operation status and workflow-readiness rows. These components render service-supplied states/actions and do not infer console health from text or filesystem markers.

## Phase 2: startup and handheld selection

Status: implemented; desktop-scale validation remains useful.

Implemented:

- responsive console cards
- canonical handheld artwork with bundled fallback assets
- manufacturer-colored selected state
- RomM/local source configuration
- asynchronous RomM verification
- thread-safe selector shutdown
- KDE/CachyOS-safe clickable-frame cards
- normal configured startup opens directly into the saved workspace
- selector remains available for first setup, invalid saved configuration, and explicit `Switch handheld`

Remaining validation:

- additional desktop scales/themes
- future-platform placeholder consistency
- first-run versus returning-user flow on a real desktop session

## Phase 3: library experience

### Vita / local library

Status: functional simplification complete; presentation polish remains desktop-driven.

`LocalLibraryWidget` owns:

- search over the in-memory library scan
- platform filtering with friendly display labels while preserving exact source keys internally
- Vita install-state filtering when mounted VitaShell USB storage is available
- cached mounted-Vita status checks for the current view
- a single list presentation rather than a nonfunctional artwork-free tile mode
- selection summary
- automatic Vita destination summary
- Vita copy workflow and cancellation
- primary `Copy to Vita` action beside the selected games
- inline routine transfer completion instead of a success-summary modal
- VitaShell USB or VitaShell FTP transport selection

The default `All games` browse path does not probe every mounted Vita destination merely to render rows. Exact install state is evaluated when the user selects a status filter or when selected games are evaluated for copying. The status cache is invalidated when device, configuration, transport or transfer state changes.

Install-state filters are disabled when VitaShell USB storage is not mounted and any stale status selection is reset to `All games`. This prevents a disconnected Vita from making the local library appear empty. FTP mode also keeps bulk status filtering disabled because VitaShell FTP does not expose an efficient bulk-status query.

DS and VitaShell FTP rows avoid claiming Vita-style pre-scanned destination state. DS destination choice remains in Device, while VitaShell FTP checks remote destinations when transfer work begins.

Vita destination/status/copy helpers remain isolated in `vita_library_support.py` rather than living in an application window.

Further local-library polish should be based on real desktop rendering with long names/paths and realistic library sizes. The 3DS master/detail library is the stronger visual reference pattern, but target-specific behavior should not be forced into a generic abstraction merely for consistency.

### Nintendo 3DS library

Status: complete for the structural refactor; deployment expansion remains hardware-driven.

`ThreeDSLibraryWidget` now presents compatible 3DS targets from either configured library source:

- progressive, paginated RomM-backed compatible library loading
- direct local-library scanning with compatible-target filtering
- shared friendly platform labels and search/platform filtering
- artwork inspector for RomM records with selection-race protection
- local-file inspector state without pretending remote artwork exists
- saved runtime preference applied through the shared normalized platform slug
- target selection
- GBA/native and VC handoff to package-generation workflows
- direct filesystem target handoff/deployment behavior where supported
- Nintendo-red deployment accents
- bounded worker shutdown

Local 3DS browsing deliberately filters out package-generation targets that require RomM metadata/package preparation where the direct local route does not support them safely. A local `.cia` can expose the native CIA route; arbitrary local 3DS files are not relabelled as installable CIA content.

The separate `ThreeDSManagerDialog` no longer holds its modal window open while an in-flight network request reaches its timeout. Close, window-manager close and Escape request interruption/cancellation and dismiss the dialog immediately. Any still-running `QThread` is retained by a detached-worker lifetime keeper until its `finished` signal arrives, avoiding both a frozen-looking modal and unsafe `QThread` destruction.

Further 3DS deployment changes should be coordinated with hardware/runtime work. Avoid reintroducing a second generic library UI merely because the source can now be local: the 3DS master/detail surface remains target-specific and owns its compatibility/runtime choices.

## Phase 4: device readiness and contextual setup

Status: simplified shell implemented; reusable health presentation and DS service integration implemented; target-specific dialogs retained.

The permanent `Setup`, `Queue` and `Tools` navigation destinations have been removed. The shell now exposes only:

1. Library
2. Device
3. Settings

`Queue` stays hidden until a real persistent queue exists. Advanced tools remain contextual rather than duplicating actions in permanent navigation.

Each Device page should answer:

1. Is the active target configured or connected?
2. Which endpoint/storage root is in use?
3. What is the next useful action?
4. Which setup or advanced action is available if needed?

The sidebar shows compact state for the active handheld only rather than unrelated disconnected devices.

Existing Device actions use state-aware primary emphasis rather than permanently highlighting the same control. A missing Vita route emphasizes connection/configuration first. A 3DS route is considered ready when either ftpd is configured or a validated mounted SD root is available. Once a usable route exists, the manager becomes the emphasized action. DS emphasizes storage selection only until a root exists; `Refresh readiness` remains secondary and the runtime-health summary presents the primary service-supplied next action. This is presentation only: DS environment detection, health classification, repair scope and repair planning remain in DS services.

### Vita

- mount state and free storage
- `Vita setup` launched contextually from Device
- Send File retained as an advanced one-off transfer action and FTP configuration surface
- normal selected-game copy moved to Library
- redesigned Vita Setup with PlayStation-blue primary actions
- explicit RetroArch/RetroAchievements route messaging
- richer Vita health states remain owned by `vita_health.py` / hardware adapters rather than by Qt widgets

### Nintendo 3DS

- mounted SD state plus FTP configuration state and endpoint
- mounted SD file workflow available contextually from Device
- 3DS Setup launched contextually from Device
- Runtime readiness available contextually from Device
- 3DS Manager remains available for direct filesystem/deployment management
- FTP connectivity kept separate from FBI Remote Install readiness
- FBI Remote Install retained through package deployment flows
- readiness gives one primary preparation action for the selected homebrew/runtime component rather than exposing installation mechanics at the same visual level
- verified direct SD preparation is available for ftpd, Universal-Updater, Red Viper, FBI and Checkpoint 3DSX builds
- direct FBI/Checkpoint preparation is explicitly the Homebrew Launcher `.3dsx` build and never claims that the corresponding CIA title is installed
- complex packages such as DaedalusX64, TWiLight Menu++ and RetroArch use an assisted Universal-Updater flow: prepare the verified updater if missing, otherwise show the exact on-console search step
- system-sensitive boot-chain components remain guide-only, while DSP firmware is explicitly generated on-console rather than downloaded
- richer app/runtime evidence states remain owned by the 3DS health/readiness services and can use the shared semantic presentation vocabulary without moving their rules into Qt

The readiness primary action therefore adapts to the selected component: **Prepare <app>** for a verified direct package, **Prepare Universal-Updater** or **Show updater steps** for complex updater-owned packages, an upstream/install-guide action for system-sensitive components, and no misleading automatic-install claim where RommHeld cannot verify the operation safely.

### Nintendo DS / removable storage

- removable-storage root selection remains contextual on Device
- runtime inspection is supplied by `inspect_ds_runtime()` and rendered by `DsRuntimeHealthPanel`
- explicit environment presentation for DSi homebrew/CFW, DS/DS Lite flashcart, 3DS-hosted TWiLight and generic removable storage
- overall readiness summary plus component rows for TWiLight Menu++, nds-bootstrap, launcher/bootstrap, environment/kernel evidence, ROM/save directories and configuration
- service-supplied paths/version markers are progressively disclosed as evidence rather than collapsed into status text
- repair-plan review occurs before the only currently safe automatic change, creation of `/roms/nds/` and `/roms/nds/saves/`
- guided/manual repair steps are presented without automatic writes; DSi NAND/Unlaunch and unknown flashcart-specific work remain manual-only
- 3DS-hosted TWiLight media exposes the DS service handoff/deferral rather than duplicating the 3DS runtime owner
- removable-storage transfer destinations remain constrained to the selected storage root

## Phase 5: settings and service configuration

Status: simplification implemented.

Settings owns the library source and runtime preference configuration. When RomM is selected, the same asynchronous `RomMConnectionWorker` used by onboarding can test the URL/token directly from Settings.

RomM credentials that are new or changed emphasize `Test connection` as the next useful action. A successful test shifts primary emphasis to `Save library settings`. Verification is advisory rather than a save gate: users can still save after a failed or skipped test.

The workspace cannot switch handhelds while that bounded test is active, and shutdown waits for it to finish, preserving Qt worker lifetime rules.

Credentials remain in local application configuration until a separate secure credential-store migration is implemented.

## Phase 6: deployment dialogs

Status: complete for the structural refactor; defect-driven polish only.

Implemented/polished:

- `gba_vc_deploy.py`
- FBI Remote Install lifecycle/firewall handling
- 3DS deployment routing
- 3DS transfer stages
- Vita Send File stages
- removable-storage transfer stages
- transfer controls shown only when relevant

Any further deployment UI work should follow actual device-test findings or remove demonstrable workflow duplication without changing transport/package semantics.

## Phase 7: collapse the legacy inheritance ladder

Status: complete.

Completed:

- `WorkspaceDashboardWindow` is a direct `QMainWindow`
- `ManagementShell` is the central application shell
- Vita/local library UI is a standalone widget
- reusable Vita helpers moved to `vita_library_support.py`
- launcher points directly at the unified workspace
- root compatibility script forwards to the launcher
- `audited_workspace.py` removed
- `device_dashboard.py` removed
- `app.py` removed
- `ui.py` removed
- `platform_selector.py` removed
- architecture regression tests reject reintroduction of removed legacy-module imports

This phase should not be reopened without a concrete functional requirement.

## Phase 8: asset cleanup and visual identity

Status: mostly complete.

Canonical assets live under:

```text
assets/handhelds/...
```

through `platform_assets.py`.

Completed:

- duplicate generic 3DS/DS/Vita icon assets removed
- startup selector uses canonical handheld assets
- Mobile has a neutral built-in placeholder rather than a blank card

Remaining polish can strengthen RommHeld's own identity and game-content presentation without adding heavy per-widget branding. Keep `docs/ASSET_SOURCES.md` aligned with future asset additions/removals.

## Phase 9: documentation cleanup

Status: current.

Authoritative documents:

- architecture: `docs/ARCHITECTURE.md`
- visual/interaction contract: `docs/DESIGN_SYSTEM.md`
- refactor and validation status: `docs/UX_REFACTOR_PLAN.md`

Superseded transitional UI documentation should not be retained once it has no active purpose.

## Phase 10: tests and lifecycle quality

Current regression areas include:

- brand/manufacturer mapping
- 3DS target mapping
- RomM remote mapping
- FTP overwrite/resume/cancellation
- firewall rule construction/cleanup
- GBA packaging input handling
- storage validation
- FBI HTTP completion/cancellation semantics
- direct `QMainWindow` workspace architecture
- removal of legacy UI-module callers
- absence of placeholder Queue/Tools navigation
- core Library/Device/Settings navigation
- contextual page subtitles
- Vita copy action remaining in Library
- local-library in-memory filtering, friendly platform labels and removal of the false tile mode
- mounted-Vita status-filter availability plus lazy/cached status inspection and contextual DS/FTP metadata
- staged VPK planning not requeueing already complete USB destinations
- local and RomM-backed 3DS library source handling
- Device primary-action emphasis following usable route/state without competing DS refresh emphasis
- RomM connection verification and test/save emphasis in Settings
- direct configured startup bypassing onboarding
- shared keyboard-focus styling
- reusable explicit health-state semantics for current and future service state keys
- health summary/component/evidence/manual-warning/repair-review/progress/failure/workflow-readiness offscreen rendering
- DS service-to-Device integration, component evidence, repair-plan acceptance/cancellation, manual-action non-emission and 3DS handoff presentation
- Vita Library transfer lifecycle guards across workspace-changing actions
- offscreen Qt runtime construction/navigation for the real shell and local-library widgets
- offscreen 3DS Manager dismissal while a background worker is still active, including detached QThread lifetime until safe completion
- offscreen 3DS readiness installer actions for direct packages, Universal-Updater-assisted complex packages, guide-only system components and console-generated data
- explicit direct-staging allowlist tests preventing complex/system-sensitive packages from being accidentally promoted
- compact-layout bounds with long Vita library content and USB status-filter transitions
- stable RommHeld `QStandardPaths` identity before and after `QApplication` creation
- guarded migration of recognizable pre-identity RommHeld configuration

CI remains headless, but it installs the minimal EGL runtime needed for PySide6 and runs an offscreen Qt smoke layer. That layer constructs the real `ManagementShell`, `LocalLibraryWidget`, the shared health components, the DS runtime-health presentation and targeted 3DS dialogs; applies the shared application theme; exercises navigation, compact layout bounds with long content, evidence disclosure, selection/action state, USB status-filter transitions, DS repair-review boundaries, 3DS readiness installer-state transitions, and verifies that the 3DS Manager can dismiss while a worker remains alive safely in the background. This catches runtime widget-construction and state/layout regressions that source-contract tests cannot. It still does not validate native desktop compositor/theme/font rendering, DPI behavior, platform-specific window management or real-device interaction; those remain desktop and hardware responsibilities.

## Remaining validation

### Desktop lifecycle and usability

- first launch shows onboarding; configured restart opens the saved workspace directly
- explicit `Switch handheld` returns to the selector and rebuilds the workspace safely
- close selector during RomM verification
- close the main window during a Settings RomM verification
- close deployment dialogs during transfer/cleanup
- close the 3DS Manager during an active RomM library scan and confirm the native dialog disappears immediately without a crash or `QThread` destruction warning
- switch handheld workspaces repeatedly
- quit while artwork/library workers are active
- confirm Library, Device and Settings render correctly at target desktop scales/themes
- verify local-library action/footer layout with long game names and paths under a native desktop session
- verify friendly platform labels and the reduced library filter row at realistic widths
- verify semantic status tones and keyboard focus remain readable in the target desktop theme
- verify Device and Settings primary-action emphasis changes are visually obvious but not excessive
- verify the DS Device page at normal and reduced widths with service-driven overall health, component rows, long evidence, manual warnings and exactly one primary next action
- verify DS evidence disclosure and action controls remain keyboard reachable with visible focus
- verify DS repair-plan review clearly separates safe automatic changes from guided/manual actions before confirmation
- verify a generic unknown state remains visually muted/neutral and is not automatically rewritten to `Not checked` unless that wording is supplied for the specific context
- verify 3DS local and RomM library sources render consistently without hiding valid target differences
- verify 3DS readiness changes its primary action cleanly between direct preparation, Universal-Updater assistance, guide-only and console-generated states

### PlayStation Vita hardware

- mount detection through VitaShell USB mode
- local-library copy and cancellation from the in-library action
- same-size/staged skip behavior
- storage-space failure path
- redesigned Send File transfer and overwrite path
- Vita Setup package download/stage flow

### Nintendo 3DS hardware

- mounted SD detection/validation and direct-file route
- FTP connect/disconnect/error state
- remote browsing and destination selection
- local file upload
- RomM download followed by 3DS upload
- cancellation and close behavior
- VC/native deployment paths under current hardware-validation work
- FBI Remote Install completion and cleanup
- 3DS Setup SD detection/validation and FTP-manager handoff
- prepare ftpd, Universal-Updater, Red Viper, FBI and Checkpoint 3DSX packages to a validated mounted SD and confirm they appear/launch through Homebrew Launcher as expected
- verify assisted complex-app flow by preparing Universal-Updater when absent, launching it on-console and completing at least one maintained complex package recipe such as DaedalusX64
- confirm readiness still distinguishes a staged FBI/Checkpoint 3DSX from an installed CIA title

No widget should be destroyed with a live `QThread` child.

## Repository cleanliness policy

Keep a file when it is:

- active production code
- an intentional current entry point
- test coverage
- a documented asset
- current documentation

Remove a file when it is:

- an abandoned implementation
- an unused temporary extraction
- a duplicate asset
- a compatibility shim with no callers
- stale documentation superseded by an authoritative document
- generated/cache output that belongs in `.gitignore`

## Definition of done

The structural/UI refactor is considered complete when:

- one coherent sidebar shell is the only active application architecture
- normal navigation exposes only useful current destinations
- visible pages follow `DESIGN_SYSTEM.md`
- manufacturer accents come from shared tokens
- normal primary actions live beside the relevant selection/state
- no active workspace depends on a console-specific main-window inheritance chain
- useful helpers have been extracted from removed legacy modules
- transitional shims have been removed after callers migrated
- no current feature is intentionally lost
- worker shutdown is reliable under CI-covered paths
- tests pass

The architecture conditions are substantially met. Remaining UI work should be targeted usability/presentation polish and fixes found through desktop or real-device regression testing, not another broad architectural rewrite.