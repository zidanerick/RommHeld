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

## Artwork

The launcher uses original RommHeld SVG illustrations based on public-domain hardware references. The reference sources are documented in `docs/ASSET_SOURCES.md`.

RomM game artwork is fetched on demand from the configured RomM instance with bounded reads and IPv4-first transport. Bearer credentials are not forwarded to external artwork hosts.

## Native GBA CIA packaging

Native GBA deployment uses AGB_FIRM through the `agbcia` package. The ROM and artwork can come directly from RomM. The AGB_FIRM boot logo is extracted once from a GBA Virtual Console donor CIA and `boot9` dump supplied by the user, then cached locally for subsequent builds. RommHeld does not download proprietary Nintendo donor assets.
