# RomM Vita Manager

A Linux desktop utility for managing game transfers from a local RomM library to a USB-mounted modded PlayStation Vita.

## Current status

Early development. The current prototype provides:

- automatic Vita mount detection
- configurable RomM library location
- platform filtering and search
- installed-state detection
- automatic RetroFlow and Adrenaline destinations
- multi-selection for bulk transfers
- resumable batch behaviour by skipping same-size files
- transfer progress and cancellation
- post-copy file-size verification
- list and tile browsing modes
- Vita free-space display
- pre-transfer capacity checks

## Default paths

RomM library:

```text
~/RomM/roms/roms/
```

RetroFlow ROMs on the Vita:

```text
ux0:/data/RetroFlow/ROMS/
```

PSP ISOs through Adrenaline:

```text
ux0:/pspemu/ISO/
```

PSP and PS1 EBOOT.PBP games through Adrenaline:

```text
ux0:/pspemu/PSP/GAME/<Game>/EBOOT.PBP
```

## RomM platform mapping

RomM commonly uses short platform IDs while RetroFlow uses descriptive folder names. The manager maps supported IDs to the actual RetroFlow folder names discovered on the target Vita.

Examples:

```text
roms/gb/   -> Nintendo - Game Boy
roms/gbc/  -> Nintendo - Game Boy Color
roms/gba/  -> Nintendo - Game Boy Advance
roms/n64/  -> Nintendo - Nintendo 64
roms/nes/  -> Nintendo - Nintendo Entertainment System
roms/snes/ -> Nintendo - Super Nintendo Entertainment System
roms/amiga/ -> Commodore - Amiga
roms/c64/  -> Commodore - 64
roms/msx/  -> Microsoft - MSX
roms/sms/  -> Sega - Master System - Mark III
roms/md/   -> Sega - Mega Drive - Genesis
roms/dc/   -> Sega - Dreamcast
```

Platforms for which the current Vita does not have a matching RetroFlow directory are deliberately marked as unsupported instead of being copied into a guessed location.

## Requirements

Designed for Arch-based Linux distributions such as CachyOS.

Install the required packages with:

```fish
sudo pacman -S --needed python pyside6
```

## Run

```fish
./run.sh
```

or:

```fish
python romm_vita_manager.py
```

## Vita connection

Put the Vita into USB mode using VitaShell, connect it to Linux, and press **Refresh** in the application.

The manager detects the mounted filesystem rather than relying on a fixed mount point or storage UUID.

## Transfer behaviour

The manager skips a destination file when it already exists with the expected size. This makes interrupted bulk transfers safe to resume.

New copies are verified by comparing the resulting file size with the source. A full checksum is not calculated by default because that would require another complete read of every transferred file.

Before a transfer begins, the manager checks the mounted Vita's free space and blocks the operation when the selected files cannot fit.

## Safety

Unknown platform mappings are not copied automatically. Native Vita VPK files are treated separately from ordinary ROM files and are not silently written to `ux0:/app`.

The repository is intended to remain free of personal paths, credentials, ROM files, Vita dumps, and other machine-specific data.

## Roadmap

Planned areas include:

- better RomM platform matching and automatic discovery
- artwork from RomM metadata
- a richer transfer queue with per-file state
- smarter duplicate detection
- free-space-aware bulk selection
- automated discovery of the installed RetroFlow configuration
- cleaner separation between GUI, mapping, filesystem, and transfer logic
- proper native Vita VPK handling
