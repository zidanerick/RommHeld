# RommHeld

RommHeld is a cross-platform desktop manager for moving a local or RomM-managed game library to supported handheld targets.

Current target workspaces:

- PlayStation Vita
- Nintendo 3DS
- Nintendo DS / compatible flashcards

PlayStation Portable and Mobile are planned targets and are shown as coming soon in the selector.

The application can load artwork from the configured RomM server for library presentation and CIA packaging. Nintendo-derived packaging assets are never downloaded automatically. User-supplied donor assets can be extracted locally and cached for reuse.

## Development

The project targets Linux/Unix, Windows, and macOS using PySide6. Platform-specific filesystem, storage, and application-path behaviour is isolated from device and library logic.

UI work follows [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md). Architecture is documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), while [`docs/UX_REFACTOR_PLAN.md`](docs/UX_REFACTOR_PLAN.md) records completed refactor work and the remaining real-device regression checks. New interface work should use the shared tokens in `romm_vita_manager/design_tokens.py` rather than adding per-widget brand colours.

The active application path is `launcher.py -> WorkspaceDashboardWindow -> ManagementShell`. The former Vita-specific `ui.py` / `app.py` application surfaces have been removed; focused library, setup, transfer and device modules now own their respective behavior.

Manufacturer-family accents are intentionally consistent across targets: Nintendo red, PlayStation blue, Xbox green and Sega blue. The rest of the interface remains neutral so the accent identifies the active platform without dominating the content.

## Artwork

The launcher uses original RommHeld SVG illustrations based on public-domain hardware references. The reference sources are documented in `docs/ASSET_SOURCES.md`.

RomM game artwork is fetched on demand from the configured RomM instance with bounded reads and IPv4-first transport. Bearer credentials are not forwarded to external artwork hosts.

## Native GBA CIA packaging

Native GBA deployment uses AGB_FIRM through the `agbcia` package. The ROM and artwork can come directly from RomM. The AGB_FIRM boot logo is extracted once from a GBA Virtual Console donor CIA and `boot9` dump supplied by the user, then cached locally for subsequent builds. RommHeld does not download proprietary Nintendo donor assets.
