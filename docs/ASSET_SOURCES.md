# RommHeld Asset Sources

## Generic UI assets

Kenney Game Icons and UI Pack are CC0 and may be redistributed and modified.

- https://kenney.nl/assets/game-icons
- https://kenney.nl/assets/ui-pack

## Platform logos

The repository keeps platform logos separate from device illustrations. The selected launch-screen logo files are based on sources whose individual pages identify the logo artwork as public domain for copyright purposes, while noting that trademark rights remain separate.

- PlayStation Vita: https://commons.wikimedia.org/wiki/File:PlayStation_Vita_logo.svg
- Nintendo 3DS: https://commons.wikimedia.org/wiki/File:Nintendo_3DS_logo.svg
- Nintendo DS: https://commons.wikimedia.org/wiki/File:Nintendo_DS_Logo.svg

The PlayStation Vita wordmark path was cross-checked against the Simple Icons PlayStation Vita asset: https://github.com/simple-icons/simple-icons/blob/develop/icons/playstationvita.svg

## Device illustrations

The handheld illustrations in `assets/handhelds/` are original RommHeld SVG artwork. They use the user's selected Icons8 Color handheld set as a visual reference for a clean, modern flat-icon treatment, but they are not copied Icons8 files.

- PlayStation Vita: simplified black-hardware illustration.
- Nintendo 3DS: simplified Aqua Blue clamshell illustration.
- Nintendo DS: simplified light-gray clamshell illustration.
- PlayStation Portable: simplified light-gray handheld illustration for the coming-soon target.

These illustrations are decorative and have no effect on compatibility, routing, or transfer logic.

## Asset policy

Platform/device definitions should reference artwork through the data-driven asset registry in `romm_vita_manager/platform_assets.py`. Do not scatter asset paths through device or transfer code.

All assets required by the normal UI must be present in the repository or packaged application. A user should never need to run a separate asset-download script for the application to render correctly.

Missing artwork must fall back gracefully. UI functionality must never depend on an external artwork server being reachable.

Do not bundle screenshots of proprietary console interfaces, commercial fonts, game box art, copyrighted game artwork, or manufacturer UI assets unless a clear redistribution license or permission is documented.
