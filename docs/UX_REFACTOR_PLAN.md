# RommHeld UX and Repository Refactor Plan

Status: implementation complete; hardware regression validation remains

Design authority: `docs/DESIGN_SYSTEM.md`

Baseline: `feature/ui-redesign` at `fddc07151d3105c6fee9a0217764973ecd200c4d`.

## Goal

RommHeld is moving from a Vita-first utility into a coherent multi-handheld desktop application. The refactor preserves working behavior while making the active architecture understandable, extensible and visually consistent.

The branch has reached the point where broad restructuring should stop. Remaining work before merge should be driven by real-device defects, not by additional architectural churn.

## Current active architecture

```text
launcher.py
    -> PlatformSelectorDialog
    -> WorkspaceDashboardWindow (QMainWindow)
        -> ManagementShell
            -> LocalLibraryWidget for Vita / DS local-library presentation
            -> ThreeDSLibraryWidget for RomM-backed 3DS browsing
            -> Device page
            -> Setup page
            -> Queue page
            -> Tools page
            -> Settings page
```

Supporting focused modules now include:

- `vita_library_support.py` for Vita destination/status/copy behavior
- `send_file_dialog.py` for explicit Vita single-file transfers
- `local_storage_ui.py` for removable-storage workflows
- `three_ds_manager.py` for 3DS browsing/deployment
- `three_ds_setup.py` for guided 3DS readiness
- `vita_setup.py` for Vita package/runtime preparation

The old `ui.py`, `app.py`, `platform_selector.py`, `audited_workspace.py` and `device_dashboard.py` surfaces have been removed. The root `romm_vita_manager.py` script now forwards to the current launcher rather than exposing a second application architecture.

## Refactor rules

- Preserve feature behavior before removing compatibility code.
- Keep platform branding in shared design tokens.
- Keep transport, packaging and runtime-selection logic separate even when presented on one screen.
- Prefer standalone widgets over inheritance from console-specific windows.
- Every cleanup step must leave the branch compilable and testable.
- Do not add temporary files that are not actively used.
- From this point onward, avoid structural rewrites unless hardware/runtime testing demonstrates a concrete need.

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

## Phase 2: startup selector

Status: implemented; desktop-scale validation remains useful.

Implemented:

- responsive console cards
- canonical handheld artwork with bundled fallback assets
- manufacturer-colored selected state
- RomM/local source configuration
- asynchronous RomM verification
- thread-safe selector shutdown
- KDE/CachyOS-safe clickable-frame cards

Remaining validation:

- additional desktop scales/themes
- future-platform placeholder consistency

## Phase 3: library experience

### Vita / local library

Status: complete for the refactor.

`LocalLibraryWidget` owns:

- search
- platform filter
- Vita install-state filter
- list/tile mode
- selection summary
- automatic Vita destination summary
- Vita copy workflow and cancellation

Vita destination/status/copy helpers are now isolated in `vita_library_support.py` rather than living in a legacy application window.

### Nintendo 3DS / RomM library

Status: complete for the refactor.

Implemented:

- progressive RomM-backed compatible library loading
- artwork inspector with selection-race protection
- target selection
- GBA native/VC handoff to the CIA deployment workflow
- Nintendo-red deployment accents
- bounded worker shutdown

Further changes should be driven by hardware/runtime findings rather than forcing more generic abstraction into target-specific deployment logic.

## Phase 4: device and setup pages

Status: visual refactor complete.

Each device page answers:

1. Is the target configured or connected?
2. Which endpoint/storage root is in use?
3. What is the next useful action?
4. Which advanced actions are available?

Completed dialog/workflow passes:

### Vita

- mount state and free storage
- redesigned Send File workflow
- Copy selected games
- redesigned Vita Setup with PlayStation-blue primary actions
- explicit RetroArch/RetroAchievements route messaging

### Nintendo 3DS

- FTP configuration state and endpoint
- redesigned 3DS Manager master/detail workflow
- redesigned guided 3DS Setup
- FTP connectivity kept separate from FBI Remote Install readiness
- FBI Remote Install retained through package deployment flows

### Nintendo DS / removable storage

- SD root and storage validation
- redesigned removable-storage dialog
- explicit destination path constrained to the selected storage root

## Phase 5: deployment dialogs

Status: complete for the refactor.

Implemented/polished:

- `gba_vc_deploy.py`
- FBI Remote Install lifecycle/firewall handling
- 3DS deployment routing
- 3DS transfer stages
- Vita Send File stages
- removable-storage transfer stages
- transfer controls shown only when relevant

Any further deployment UI work should follow actual device-test findings.

## Phase 6: collapse the legacy inheritance ladder

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

## Phase 7: asset cleanup

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

Keep `docs/ASSET_SOURCES.md` aligned with future asset additions/removals.

## Phase 8: documentation cleanup

Status: complete for the refactor.

Authoritative documents:

- architecture: `docs/ARCHITECTURE.md`
- visual/interaction contract: `docs/DESIGN_SYSTEM.md`
- refactor and validation status: `docs/UX_REFACTOR_PLAN.md`

Superseded transitional UI documentation should not be retained once it has no active purpose.

## Phase 9: tests and lifecycle quality

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

CI is headless and does not provide `libEGL.so.1`, so architecture tests must not import Qt GUI modules merely to inspect inheritance. Runtime Qt validation remains a hardware/desktop responsibility.

## Remaining pre-merge validation

### Desktop lifecycle

- close startup selector during RomM verification
- close deployment dialogs during transfer/cleanup
- switch handheld workspaces repeatedly
- quit while artwork/library workers are active
- confirm redesigned dialogs render correctly at the target desktop scale

### PlayStation Vita hardware

- mount detection through VitaShell USB mode
- local-library copy and cancellation
- same-size skip behavior
- storage-space failure path
- redesigned Send File transfer and overwrite path
- Vita Setup package download/stage flow

### Nintendo 3DS hardware

- FTP connect/disconnect/error state
- remote browsing and destination selection
- local file upload
- RomM download followed by 3DS upload
- cancellation and close behavior
- GBA CIA deployment
- FBI Remote Install completion and cleanup
- 3DS Setup SD detection/validation and FTP-manager handoff

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
- visible pages follow `DESIGN_SYSTEM.md`
- manufacturer accents come from shared tokens
- no active workspace depends on a console-specific main-window inheritance chain
- useful helpers have been extracted from removed legacy modules
- transitional shims have been removed after callers migrated
- no current feature is intentionally lost
- worker shutdown is reliable under CI-covered paths
- tests pass

Those implementation conditions are now substantially met. PR #21 should move to real Vita and 3DS regression testing, with only defect-driven fixes before merge.
