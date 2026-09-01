# 3DS Storage and Target Profiles

This document defines how RommHeld should reason about storage attached to a Nintendo 3DS-family workflow.

## Observed 3DS SD card

The test card supplied during development contains the following strong indicators:

- `/boot.firm`
- `/boot.3dsx`
- `/luma/`
- `/gm9/`
- `/config/`
- `/roms/`
- `/roms/nds/`
- `/roms/nds/saves/`
- `/luma/payloads/open_agb_firm.firm`

These observations support a high-confidence `3ds-sd` classification and indicate that both 3DS custom-firmware tooling and a ROM hierarchy are present.

The actual listing also showed additional ROM directories, including NES, SNES, Master System, WonderSwan, Neo Geo Pocket and other systems. These should be treated as observed storage contents, not universal 3DS requirements.

## Validation rules

Validation must be read-only. It must never create, delete, rename, or modify files merely to identify a storage target.

### 3DS SD card

Strong signature set:

```text
boot.firm
boot.3dsx
luma/
gm9/
```

Optional supporting signatures:

```text
3ds/
roms/
_nds/
```

### TWiLight Menu++ / DS storage

Useful signatures include:

```text
_nds/
BOOT.NDS
roms/
```

TWiLight Menu++ provides multiple interfaces, including Nintendo 3DS, Nintendo DSi, R4 Original and Wood themes. Therefore target identification should remain a profile rather than assuming one UI. 

### R4 / flashcart

Do not identify an R4 from one filename. Use a profile-specific set of indicators where possible, such as known kernel directories/files.

## Target profiles

A device can have multiple target profiles:

```text
Nintendo 3DS
├── 3DS SD Card
├── RetroArch
├── TWiLight Menu++ / nds-bootstrap
├── Native GBA
├── Virtual Boy / Red Viper
└── DS / R4 Flashcart
```

Each profile defines its transport, root, platform mappings, validation signatures and capability metadata.

## FTP inspection note

The 3DS FTP server used during testing did not support `find -maxdepth`; the FTP client sent that argument as part of the remote path. Use ordinary directory listing/browsing for discovery unless the server explicitly advertises a compatible command.
