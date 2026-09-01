# RommHeld UI Redesign

## Goal

RommHeld should feel like a game-management application rather than a conventional utility. Launching the application presents an original handheld selection screen, followed by a device-specific management environment.

The visual direction is inspired by console menu design and selection screens, not a reproduction of any proprietary interface, screenshot, font, or artwork.

## Launch screen

Supported handhelds:

- PlayStation Vita
- Nintendo 3DS
- Nintendo DS / Slot-1 flashcard

Coming soon:

- PSP
- Mobile

The launch screen also selects a library source:

- Local ROM directory: current implementation
- RomM server: URL + Client API Token, saved locally for the API-backed library provider

RomM's current developer documentation recommends Client API Tokens for companion applications. Tokens are bearer credentials and should never be committed to Git.

## Management shell

A shared management shell is themed from the selected console profile. Device-specific controls are provided by that profile, while global features such as the transfer queue, library source, settings, and format tools remain separate.

### Vita visual direction

Cool blue tones, dark neutral surfaces, thin rounded borders, clean typography, compact status indicators, and subtle LiveArea-era cues.

### 3DS visual direction

Red and white accents, compact icon-driven controls, soft depth, bright focus states, and playful selection geometry inspired by the HOME Menu era.

### DS / flashcard visual direction

Lighter handheld styling, slot-card cues, pixel-friendly control elements, and target profiles for TWiLight Menu++, nds-bootstrap, and flashcard kernels.

## Global navigation

The long-term management shell should expose:

- Library
- Device / target
- Setup
- Transfer queue
- Runtime preferences
- Tools
- Settings
- Return to handheld selection

## Runtime preferences

Runtime preferences are priorities, not hard-coded emulator selections:

- Prefer native runtime
- Prefer RetroAchievements
- Prefer compatibility

The effective route must always be intersected with actual detected capabilities for the selected platform and target profile.

## Asset policy

Generic interface artwork should use original RommHeld vectors or assets with clear redistribution rights. Kenney's Game Icons and UI Pack are CC0 and are suitable for generic interface symbols. Official console logos may be used on the launch screen where a source with clear redistribution terms has been identified, with trademark caveats documented in the repository.

Do not bundle proprietary console UI screenshots, commercial fonts, copyrighted game artwork, or manufacturer UI assets without explicit redistribution permission.

## Future tools

The management shell is intended to host optional format/container tools later, including ROM format conversion, package staging, official Virtual Console matching, and other target-specific preparation. Such tools should be implemented as target capabilities and should never be entangled with the base transport layer.
