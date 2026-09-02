# Nintendo 3DS Virtual Console packaging

RommHeld treats Nintendo-style Virtual Console packaging as a separate capability from ordinary ROM transfer and from homebrew emulators.

## Current implementation target

The first supported packaging profile is Game Boy Advance native mode using the 3DS `AGB_FIRM` runtime. The open-source `agbcia` project can build an installable CIA around a GBA ROM and custom Home Menu artwork, while native mode reuses the 3DS's built-in GBA firmware path.

RommHeld does not bundle Nintendo firmware, donor material, or bootROM data. Native packaging requires user-supplied assets that they are legally entitled to use, including an extracted AGB_FIRM boot logo and a compatible ARM9 `boot9` dump.

The current profile definition lives in `romm_vita_manager/three_ds_vc.py`. It deliberately contains no Qt code or packaging dependency so the capability can be tested independently of the UI.

## Artwork

The intended flow is:

`RomM metadata -> title metadata + cover art -> derived icon/banner assets -> CIA`

Artwork should come from the user's RomM metadata where available. The package builder should never silently fetch or bundle Nintendo-owned artwork or donor content.

## Title IDs

Native GBA titles must use the AGB_FIRM-compatible title ID range `0004000000F???00`. RommHeld validates that range before invoking the packager.

## Runtime separation

A native GBA title and a homebrew emulator forwarder are not treated as equivalent. A future homebrew profile may be useful, but it will remain explicitly labelled as emulator/homebrew rather than Nintendo Virtual Console.

Other historical 3DS Virtual Console platforms such as Game Boy, Game Boy Color, NES, SNES, Game Gear, and Mega Drive remain research profiles until their exact runtime and packaging requirements are validated. No unsupported platform is exposed as a working Virtual Console option.

## Planned user flow

1. Select a game from the configured RomM library.
2. Choose **Raw ROM** or a supported **Virtual Console-style** package mode.
3. Resolve title metadata and artwork from RomM.
4. Validate the user's locally configured packaging assets.
5. Build the CIA in a temporary workspace.
6. Transfer the CIA over the existing 3DS FTP backend.
7. Optionally keep the generated CIA locally for testing or reuse.
