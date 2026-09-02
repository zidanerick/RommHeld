# RommHeld Asset Sources

## Generic UI assets

Kenney Game Icons and UI Pack are CC0 and may be redistributed and modified.

- https://kenney.nl/assets/game-icons
- https://kenney.nl/assets/ui-pack

## Platform logos

The repository keeps platform logos separate from device illustrations. Launch-screen identity marks use verified platform sources where practical; trademarks remain the property of their respective owners.

- PlayStation Vita: https://commons.wikimedia.org/wiki/File:PlayStation_Vita_logo.svg
- Nintendo 3DS: https://commons.wikimedia.org/wiki/File:Nintendo_3DS_logo.svg
- Nintendo DS: https://commons.wikimedia.org/wiki/File:Nintendo_DS_Logo.svg

## Handheld illustrations

RommHeld uses original local SVG illustrations for the selector and future library/status indicators. They are intentionally simplified for UI use but are based on the physical front layouts of the actual hardware.

Reference sources used for geometry and visual accuracy:

- PlayStation Vita PCH-1101-FL: https://commons.wikimedia.org/wiki/File:PlayStation-Vita-1101-FL.png
- Nintendo 3DS Aqua Blue: https://commons.wikimedia.org/wiki/File:Nintendo-3DS-AquaOpen.png
- Nintendo DS Fat Blue: https://commons.wikimedia.org/wiki/File:Nintendo-DS-Fat-Blue.png

The Evan-Amos references above are public-domain photographs; they are not required at runtime and are not bundled by RommHeld.

## Asset policy

Platform/device definitions reference artwork through `romm_vita_manager/platform_assets.py`. Do not scatter asset paths through device or transfer code.

Missing artwork must fall back gracefully. UI functionality must never depend on an asset being present or on an external CDN.

Do not bundle screenshots of proprietary console interfaces, commercial fonts, game box art, copyrighted game artwork, or third-party licensed assets unless a clear redistribution license or permission is documented.
