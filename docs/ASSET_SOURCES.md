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

The current handheld illustrations in `assets/handhelds/` are original RommHeld SVG artwork created for the application. They are not copies of console manufacturer interface artwork or product photography.

- PlayStation Vita: original simplified black-hardware illustration.
- Nintendo 3DS: original simplified Aqua Blue clamshell illustration.
- Nintendo DS: original simplified light-gray clamshell illustration.

These illustrations are decorative and have no effect on compatibility, routing, or transfer logic.

## Asset policy

Platform/device definitions should reference artwork through the data-driven asset registry in `romm_vita_manager/platform_assets.py`. Do not scatter asset paths through device or transfer code.

Missing artwork must fall back gracefully. UI functionality must never depend on an asset being present.

Do not bundle screenshots of proprietary console interfaces, commercial fonts, game box art, copyrighted game artwork, or manufacturer UI assets unless a clear redistribution license or permission is documented.
