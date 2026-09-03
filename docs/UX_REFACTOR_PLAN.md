# RommHeld UX and Repository Refactor Plan

Status: active

Design authority: `docs/DESIGN_SYSTEM.md`

Baseline for this plan: `feature/ui-redesign` at `fddc07151d3105c6fee9a0217764973ecd200c4d`.

## Why this refactor exists

RommHeld has grown from a Vita-focused utility into a multi-handheld manager. Feature work is functional, but the UI layer contains several generations of implementation at once. The goal is to preserve working features while making the repository and interface easier to understand and extend.

## Current UI architecture audit

The active launcher path currently resolves through this inheritance stack:

1. `romm_vita_manager/ui.py` provides the original Vita-oriented `MainWindow` and setup UI.
2. `romm_vita_manager/app.py` extends that window and adds generic file transfer / 3DS utilities.
3. `romm_vita_manager/workspace_dashboard.py` wraps the legacy central widget in the multi-workspace shell.
4. `romm_vita_manager/audited_workspace.py` applies correctness fixes and substitutes the dedicated 3DS library.
5. `launcher.py` starts `audited_workspace.WorkspaceDashboardWindow`.

This arrangement preserved features during rapid development, but it also explains several current problems:

- presentation code is spread across multiple generations
- the active window depends on legacy widgets that are then hidden or rearranged
- console-specific styling is hardcoded in multiple modules
- some transitional modules remain in the repository even though they are not part of the launcher path
- changes to the shared shell are harder to reason about because legacy and current UI concepts coexist

## Refactor rules

- Preserve feature behaviour before removing compatibility code.
- Move styling before moving business logic.
- Remove dead/transitional code only after its active references are eliminated or verified absent.
- Keep backend modules independent of PySide where practical.
- Do not combine transport, packaging and runtime selection merely because they are shown on the same screen.
- Each cleanup step should leave the branch runnable and testable.

## Phase 1: design foundation

Status: in progress on `refactor/apple-like-ui`.

### Added

- `romm_vita_manager/design_tokens.py`
  - neutral palette
  - Nintendo/Sony/Xbox/Sega family accents
  - shared spacing/radius values
- `romm_vita_manager/theme.py`
  - application-wide neutral widget styling
- `romm_vita_manager/ui_components.py`
  - reusable section header, surface card, status pill and accent button
- `docs/DESIGN_SYSTEM.md`
  - canonical design and interaction contract

### Shell redesign

Replace tab-first navigation with a persistent left sidebar while retaining the existing `clear_sections()`, `add_section()` and `select_section()` integration surface. This allows existing library/device pages to survive the visual refactor without changing their backend behaviour.

## Phase 2: startup selector

Refactor `console_selector.py` to use the shared design tokens instead of its private colour system.

Target layout:

- concise RommHeld header
- large, recognisable handheld choices
- manufacturer-family accent on selected card only
- library source in a secondary configuration surface
- connection status as a compact inline state
- one primary Continue action

Thread requirement:

- selector and startup RomM verification workers must not outlive the widgets that own them

## Phase 3: library experience

### Vita / local library

Extract the library portion of `ui.MainWindow` into a standalone widget so `workspace_dashboard.py` no longer has to instantiate a full Vita window and hide pieces of it.

Target responsibilities for the new library widget:

- search
- platform filter
- install-state filter where supported
- list/tile mode if retained
- selection summary
- destination/deployment action

### 3DS / RomM library

Keep the existing progressive-loading model in `three_ds_library.py`.

Polish goals:

- artwork/details inspector should read as one coherent selection panel
- target selector and deploy button should be adjacent to the selected game details
- empty and error states should be actionable
- selection/deploy controls should use Nintendo red through shared tokens

### Shared library direction

Long term, Vita, 3DS, DS and future targets should share a common library presentation model where the data permits it. Target-specific deployment actions belong in target adapters rather than duplicated library browsers.

## Phase 4: device and setup pages

Replace form-heavy utility layouts with concise state cards.

Each device page should answer, in order:

1. Is the device/target configured or connected?
2. What target is RommHeld going to use?
3. What is the next useful action?
4. What advanced details are available if needed?

Examples:

### 3DS

- Connection: configured / connected
- Endpoint
- FBI Remote Install readiness
- FTP action
- setup action

### Vita

- Mount / connection state
- free storage
- copy/deploy action
- setup action

### DS

- selected SD root
- validation result
- target profile
- validate/browse action

## Phase 5: deployment dialogs

Apply the shared theme and platform accent to:

- `gba_vc_deploy.py`
- `three_ds_manager.py`
- `local_storage_ui.py`
- Vita send-file flow in `app.py`
- setup dialogs

Do not redesign the backend logic while styling these dialogs unless a correctness problem is encountered.

For long-running actions, expose stages rather than a generic progress label.

## Phase 6: collapse the legacy inheritance ladder

This is the main architecture cleanup and should happen after the visible pages have standalone widgets.

Target end state:

```text
launcher.py
    -> WorkspaceDashboardWindow
        -> ManagementShell
        -> library widget
        -> device page
        -> setup page
        -> tools/settings pages
```

The main workspace should no longer need to inherit from a Vita-specific `MainWindow` purely to reuse its widgets.

### Intended removals after migration

These are cleanup candidates, not files to delete before their behaviour is migrated:

- `audited_workspace.py`: correctness layer should be merged into the final workspace implementation
- `device_dashboard.py`: transitional dashboard implementation outside the current launcher path
- `platform_selector.py`: compatibility export once all internal imports use `console_selector.py`
- root `romm_vita_manager.py`: legacy Vita-named entry point once backward compatibility is intentionally retired

`ui.py` and `app.py` should become smaller service/dialog modules or be retired only after the active features they contain are extracted.

## Phase 7: asset cleanup

The current asset hierarchy contains both `assets/handhelds/...` and older generic files under `assets/icons/...`.

The preferred canonical path is `assets/handhelds/...` through `platform_assets.py`.

After transitional code no longer references `assets/icons`, remove the duplicate icon directory rather than maintaining two console-asset systems.

Keep `docs/ASSET_SOURCES.md` aligned with any asset removal or addition.

## Phase 8: documentation cleanup

`docs/UI_REDESIGN.md` predates the canonical design system. Retain it temporarily as a redirect/compatibility document, then remove it once references have been updated.

Documentation should separate:

- architecture: `ARCHITECTURE.md`
- visual/interaction rules: `DESIGN_SYSTEM.md`
- active migration work: `UX_REFACTOR_PLAN.md`
- platform capability/storage/testing documents

Avoid multiple documents making conflicting claims about the current UI.

## Phase 9: tests and lifecycle quality

Add/maintain tests for pure logic where possible.

Required regression areas:

- platform -> manufacturer-family brand mapping
- target mapping
- RomM remote mapping
- FTP overwrite/resume/cancellation semantics
- temporary firewall rule construction and cleanup
- GBA packaging input handling
- storage validation

Qt lifecycle checks should cover manually or in an appropriate GUI test environment:

- closing startup selector during RomM verification
- closing deployment dialogs during transfer/cleanup
- switching handheld workspaces repeatedly
- quitting while artwork/library workers are active

No widget should be destroyed with a live `QThread` child.

## Repository cleanliness policy

A file should remain when it is one of:

- active production code
- intentional compatibility surface
- test coverage
- documented asset
- current documentation

A file should be removed when it is:

- an abandoned alternative implementation
- a duplicate asset with no active reference
- a compatibility shim whose callers have all migrated
- stale documentation superseded by an authoritative document
- generated/cache output that belongs in `.gitignore`

Do not remove a file merely because it is small or old. Redundancy must be demonstrated by the active architecture.

## Definition of done

The refactor is complete when:

- the application uses one coherent sidebar shell
- current pages follow `DESIGN_SYSTEM.md`
- Nintendo, PlayStation, Xbox and Sega family accents come only from shared tokens
- the active window no longer subclasses the legacy Vita UI
- transitional dashboards/shims are removed after migration
- no current feature is lost
- worker shutdown is reliable
- tests pass
- the repository has one authoritative design document and one current architecture path
