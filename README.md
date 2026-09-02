# RommHeld

RommHeld is a cross-platform desktop manager for moving a local or RomM-managed game library to supported handheld targets.

Current target workspaces:

- PlayStation Vita
- Nintendo 3DS
- Nintendo DS / compatible flashcards

PlayStation Portable and Mobile are planned targets and are shown as coming soon in the selector.

The application uses bundled local artwork only. Normal operation never requires an artwork download or asset-preparation script.

## Development

The project targets Linux/Unix, Windows, and macOS using PySide6. Platform-specific filesystem, storage, and application-path behaviour is isolated from device and library logic.

## Artwork

The launcher uses original RommHeld SVG illustrations based on public-domain hardware references. The reference sources are documented in `docs/ASSET_SOURCES.md`.
