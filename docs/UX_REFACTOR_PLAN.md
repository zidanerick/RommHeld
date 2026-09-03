# RommHeld UX and Repository Refactor Plan

Status: active

Design authority: `docs/DESIGN_SYSTEM.md`

Baseline: `feature/ui-redesign` at `fddc07151d3105c6fee9a0217764973ecd200c4d`.

## Goal

RommHeld is moving from a Vita-first utility into a coherent multi-handheld desktop application. The refactor must preserve working behavior while making the active architecture understandable, extensible and visually consistent.

## Current active architecture

The launcher path is now:

```text
launcher.py
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

`WorkspaceDashboardWindow` no longer subclasses the original Vita `MainWindow`. The previous `audited_workspace.py` correctness layer and the obsolete `device_dashboard.py` have already been removed.

The old `ui.py` and `app.py` modules remain compatibility/service sources for behavior that has not yet been fully extracted, but they are no longer the main application shell.

## Refactor rules

- Preserve feature behavior before removing compatibility code.
- Remove dead code only after active references are gone.
- Keep platform branding in shared design tokens.
- Keep transport, packaging and runtime-selection logic separate even when presented on one screen.
- Prefer standalone widgets over inheritance from console-specific windows.
- Every cleanup step must leave the branch compilable and testable.
- Do not add temporary files that are not actively used.

## Phase 1: design foundation

Status: complete for the active branch.

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

Status: implemented, hardware validation ongoing.

Implemented:

- responsive console cards
- real hardware artwork where available with bundled fallback assets
- manufacturer-colored selected state
- RomM/local source configuration
- asynchronous RomM verification
- thread-safe selector shutdown
- KDE/CachyOS-safe card implementation using clickable frames rather than nested push-button layouts

Remaining polish:

- validate selector sizing on additional desktop scales/themes
- keep placeholder artwork consistent for future platforms

## Phase 3: library experience

### Vita / local library

Status: extracted.

`LocalLibraryWidget` now owns the local-library presentation that previously lived inside the Vita `MainWindow`.

Responsibilities:

- search
- platform filter
- Vita install-state filter
- list/tile mode
- selection summary
- automatic Vita destination summary
- Vita copy workflow and cancellation

The same local library surface can be reused for DS presentation without pretending DS install-state detection exists.

### Nintendo 3DS / RomM library

Status: implemented and progressively loaded.

Current behavior:

- RomM-backed compatible library loading
- artwork inspector
- target selection
- GBA native/VC handoff to the real CIA deployment workflow
- Nintendo-red deployment accents
- bounded worker shutdown

Remaining work:

- continue consolidating common library presentation patterns where useful
- do not force target-specific deployment logic into a generic library model

## Phase 4: device and setup pages

Status: active shell implemented, dialogs still need final visual cleanup.

Each device page should answer:

1. Is the target configured or connected?
2. Which endpoint/storage root is in use?
3. What is the next useful action?
4. Which advanced actions are available?

Current pages:

### Vita

- mount state
- free storage
- Send File
- Copy selected games
- Vita Setup

### Nintendo 3DS

- FTP configuration state
- endpoint
- Setup
- 3DS manager
- FBI Remote Install through package deployment flows

### Nintendo DS

- SD root
- storage validation
- setup validation

Remaining visual pass:

- `three_ds_manager.py`
- `vita_setup.py`
- `three_ds_setup.py`
- removable-storage dialogs
- Send File dialog

## Phase 5: deployment dialogs

Status: partly complete.

Implemented/polished:

- `gba_vc_deploy.py`
- FBI Remote Install lifecycle/firewall handling
- 3DS deployment routing

Remaining:

- apply the same hierarchy and card/action language to older form-heavy dialogs
- expose meaningful transfer stages instead of generic progress text

## Phase 6: collapse the legacy inheritance ladder

Status: major milestone complete.

Completed:

- `WorkspaceDashboardWindow` is a direct `QMainWindow`
- `ManagementShell` is the actual central application shell
- Vita/local library UI is a standalone widget
- `audited_workspace.py` removed
- `device_dashboard.py` removed
- launcher points directly at the unified workspace
- architecture regression tests verify the workspace does not reintroduce legacy `MainWindow` inheritance

Remaining compatibility cleanup:

- migrate remaining reusable helpers/dialogs out of `ui.py` and `app.py`
- retire those legacy entry-point surfaces only after their remaining callers are moved
- remove `platform_selector.py` once all compatibility callers are gone
- retire the root `romm_vita_manager.py` entry point only when backward compatibility is intentionally dropped

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

Status: active.

Authoritative documents:

- architecture: `docs/ARCHITECTURE.md`
- visual/interaction contract: `docs/DESIGN_SYSTEM.md`
- active migration plan: `docs/UX_REFACTOR_PLAN.md`

`docs/UI_REDESIGN.md` is a compatibility pointer only and should not become a second design authority.

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

CI is headless and does not provide `libEGL.so.1`, so architecture tests must not import Qt GUI modules merely to inspect inheritance. Runtime Qt validation remains a hardware/desktop test responsibility.

Manual lifecycle checks:

- close startup selector during RomM verification
- close deployment dialogs during transfer/cleanup
- switch handheld workspaces repeatedly
- quit while artwork/library workers are active
- Vita copy cancellation
- 3DS FTP/FBI deployment on real hardware

No widget should be destroyed with a live `QThread` child.

## Repository cleanliness policy

Keep a file when it is:

- active production code
- an intentional compatibility surface
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

The refactor is complete when:

- one coherent sidebar shell is the only active application architecture
- visible pages follow `DESIGN_SYSTEM.md`
- manufacturer accents come only from shared tokens
- no active workspace depends on a console-specific main-window inheritance chain
- remaining useful helpers are extracted from legacy `ui.py` / `app.py`
- transitional shims are removed after callers migrate
- no current feature is lost
- worker shutdown is reliable
- tests pass
- Vita and 3DS hardware workflows pass manual validation
