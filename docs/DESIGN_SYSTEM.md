# RommHeld Design System

This document is the visual and interaction contract for RommHeld. New UI work should follow it unless a platform limitation requires an explicit exception.

## Product character

RommHeld should feel calm, obvious and dependable. It is a desktop game-library manager, not a collection of disconnected utilities.

The visual direction borrows general ideas from modern desktop system applications: strong hierarchy, restrained surfaces, generous spacing, clear primary actions and progressive disclosure. It must not reproduce proprietary Apple, Nintendo, Sony, Microsoft or Sega interfaces.

## Core principles

### One shell, many workflows

Library browsing, device management, setup, deployment, tools and settings belong in one stable application shell. Avoid opening a new top-level window when an in-place page or focused dialog is sufficient.

### Neutral first, brand second

Most of the interface is neutral graphite. Platform colour is an orientation cue, not a background theme.

Use platform colour for:

- selected navigation
- the current-workspace indicator
- primary deployment actions
- small badges and highlights
- focus/selection accents where useful

Do not fill large content regions with manufacturer colours.

### One obvious primary action

A page should have one visually dominant next action. Secondary actions should be quieter.

Examples:

- Connect device
- Deploy selected game
- Install with FBI
- Send with FTP
- Save settings

### Progressive disclosure

Show the common path first. Advanced packaging, runtime overrides, remote paths and troubleshooting controls should appear only when relevant.

### Status is part of the workflow

The user should be able to determine quickly:

- active handheld
- library source
- device state
- selected deployment target
- current operation
- whether intervention is required

### Failures must be actionable

Avoid generic messages such as `Failed` or `Timed out` when the subsystem is known.

Prefer:

> FBI accepted the request, but the 3DS could not reach the temporary HTTP server on this PC.

Then expose the next useful action.

## Colour system

The canonical values live in `romm_vita_manager/design_tokens.py`.

### Neutral palette

| Token | Value | Purpose |
| --- | --- | --- |
| Background | `#0B0B0D` | App/content background |
| Sidebar | `#141416` | Persistent navigation |
| Surface | `#1C1C1E` | Cards, lists, fields |
| Raised surface | `#242426` | Controls and elevated areas |
| Hover surface | `#2C2C2E` | Hover/selection support |
| Separator | `#38383A` | Borders and dividers |
| Primary text | `#F5F5F7` | Titles and body text |
| Secondary text | `#A1A1A6` | Supporting copy |
| Tertiary text | `#727277` | Low-priority metadata |
| Success | `#30D158` | Successful/connected states |
| Warning | `#FF9F0A` | Recoverable warning states |
| Error | `#FF453A` | Errors and destructive actions |

### Manufacturer-family accents

| Family | Accent | Current RommHeld targets |
| --- | --- | --- |
| Nintendo | `#E60012` | Nintendo 3DS, Nintendo DS, Game Boy family |
| Sony / PlayStation | `#0070D1` | PlayStation Vita, PSP |
| Xbox | `#107C10` | Future Xbox-family targets |
| Sega | `#0089CF` | Future Sega-family targets |
| Neutral | `#6E6E73` | Generic/unknown targets |

Use manufacturer-family colours consistently across consoles. Do not invent a separate accent for every model unless the design document is intentionally revised.

## Application structure

### Startup selector

The startup experience selects two things:

1. handheld workspace
2. library source

Handheld cards should be visual and immediately recognisable. Configuration controls should remain secondary to handheld selection.

### Main shell

The main shell uses a persistent left sidebar and a single content area.

Sidebar responsibilities:

- RommHeld identity
- active handheld identity
- page navigation
- compact device state
- change-handheld action

Content responsibilities:

- page title
- brief context subtitle
- page-specific controls and data

### Navigation order

Preferred order for current workspaces:

1. Library
2. Device
3. Setup
4. Queue
5. Tools
6. Settings

Do not add pages for functionality that is merely planned. A disabled placeholder page is acceptable only when it materially explains the current product state and is temporary.

## Typography

Use the operating system's general UI font through Qt. Do not bundle commercial system fonts.

Hierarchy should come mostly from size, weight and spacing rather than many colours or typefaces.

Recommended hierarchy:

- Page title: 24–26 px, bold
- Section title: 20–22 px, bold
- Card title: 13–15 px, semibold
- Body: system default
- Metadata/caption: 9–11 px, secondary or tertiary colour

Avoid all-caps body copy. All-caps is reserved for very small structural labels such as `WORKSPACE` or `DEVICES`.

## Spacing and geometry

Canonical spacing and radius values live in `design_tokens.py`.

- 4 px: tiny internal adjustment
- 8 px: compact control spacing
- 12 px: normal related-item spacing
- 16 px: card padding
- 20–24 px: section/page spacing
- 32 px: major separation

Corner radii:

- 8 px: compact controls
- 12 px: navigation/standard surfaces
- 16 px: larger feature cards

Avoid excessive nesting of bordered rounded rectangles.

## Controls

### Buttons

Primary actions may use the active platform accent with white text.

Secondary actions use neutral raised surfaces.

Tertiary actions use quiet/transparent buttons where appropriate.

Destructive actions must use error semantics and should not be the most visually dominant control by default.

### Inputs

Fields should use neutral surfaces with a visible but understated border. Focus must be clearly visible.

Do not use disabled inputs as labels. Use actual labels or read-only text when a value is informational.

### Lists

Large libraries should use list/model views with incremental loading rather than rendering a large hierarchy of cards.

Selection must remain obvious without overwhelming the artwork or metadata.

### Cards

Use cards for grouped state and choices, not for every row. A screen made entirely of nested cards is a design failure.

## Empty, loading and error states

### Empty

Every meaningful empty state needs:

- a reason
- a next action when one exists

Example:

> No compatible GBA titles were found in the current RomM source.

Action: `Refresh library` or `Change source filter`.

### Loading

Name the operation:

- Connecting to RomM…
- Loading Nintendo 3DS titles…
- Packaging CIA…
- Waiting for FBI to request the file…

Avoid a bare `Loading…` when the operation is known.

### Error

State the failing boundary and likely correction. Network, authentication, packaging, storage and device errors should not be collapsed into one generic message.

## Platform-specific behaviour

### Nintendo

Use Nintendo red for orientation and primary Nintendo actions. Keep content backgrounds neutral.

For 3DS deployment, distinguish clearly between:

- native/SD deployment
- FTP transfer
- FBI Remote Install
- Virtual Console packaging

### Sony / PlayStation

Use PlayStation blue for Vita and PSP orientation and primary actions.

Do not imply that RetroFlow, Adrenaline, VitaShell or RetroArch are the same runtime or transport layer.

### Xbox and Sega

Future support should use the existing family tokens rather than introducing new ad hoc colours.

## Asset policy

- Prefer bundled original RommHeld vectors for guaranteed offline UI.
- Remote hardware imagery is optional enhancement only.
- A remote image failure must never break selection or navigation.
- Do not bundle proprietary console UI screenshots, commercial fonts or copyrighted game artwork without explicit redistribution rights.
- Do not download proprietary Nintendo packaging assets automatically.

See `docs/ASSET_SOURCES.md` for current asset provenance.

## Implementation contract

### Centralise styling

Shared neutral styling belongs in `romm_vita_manager/theme.py`.

Shared colour, spacing and brand values belong in `romm_vita_manager/design_tokens.py`.

Reusable PySide widgets belong in `romm_vita_manager/ui_components.py` until the legacy `ui.py` module is retired and a dedicated UI package can be introduced without a module/package naming collision.

### Do not hardcode brand colours in pages

New code should use `brand_for_platform()` or a `WorkspaceProfile` rather than copying hex values into widgets.

### Keep business logic out of presentation code

Network, storage, packaging and transfer logic should remain in service/backend modules. UI code should orchestrate and present state.

### Preserve feature behaviour during visual refactors

A visual refactor must not silently change:

- transfer overwrite policy
- credential semantics
- target selection
- packaging behaviour
- verification logic
- cancellation behaviour

### Threads must have explicit lifetimes

Any `QThread` or worker launched by a widget must be cancelled or allowed to finish before its owner is destroyed. A bounded wait during application shutdown is preferable to a `QThread: Destroyed while thread is still running` abort.

## Review checklist

Before merging UI work, check:

- Does the active platform use the correct manufacturer-family accent?
- Is there one obvious primary action?
- Is important state visible without opening another dialog?
- Are empty/loading/error states specific and actionable?
- Did the change add another hardcoded colour or spacing system?
- Did it duplicate an existing widget or workflow?
- Does closing the window leave any active worker thread behind?
- Does the workflow still function without optional remote artwork?

## Future AI/development conversations

Treat this file as the source of truth for RommHeld visual and interaction decisions.

A future development prompt can simply state:

> Follow `docs/DESIGN_SYSTEM.md` and preserve existing feature behaviour.

Any intentional departure should update this document in the same change so the repository, rather than chat history, remains authoritative.
