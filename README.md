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

## Safety

Unknown platform mappings are not copied automatically. Native Vita VPK files are treated separately from ordinary ROM files and are not silently written to `ux0:/app`.

The repository is intended to remain free of personal paths, credentials, ROM files, Vita dumps, and other machine-specific data.

## Roadmap

Planned areas include better RomM platform matching, artwork, richer transfer queues, free-space checks, improved Vita game handling, and automated discovery of the installed RetroFlow configuration.
