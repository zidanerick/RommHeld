# 3DS Storage and Target Profiles

This document defines how RommHeld reasons about storage attached to a Nintendo 3DS-family workflow.

## Supported filesystem routes

RommHeld supports two distinct ways to place ordinary filesystem content on a Nintendo 3DS SD card:

1. **Mounted SD card · Direct / offline**
   - remove the SD or microSD card from the console and mount it on the desktop through a card reader;
   - RommHeld validates the selected root before allowing writes;
   - this route provides reliable local free-space checks and staged filesystem replacement;
   - it is a good choice for large transfers, initial setup, or any workflow where taking the card out is acceptable.
2. **ftpd · Wireless / live console**
   - leave the card in the console;
   - open mtheall `ftpd` on the 3DS and keep it running;
   - RommHeld transfers to the same logical destination over FTP.

The mounted-card route is deliberately **not** labelled as console USB. Nintendo 3DS systems do not expose a standard USB mass-storage filesystem. A USB-connected SD-card reader is still treated by RommHeld as mounted removable storage because the console itself is not the USB storage device.

Normal filesystem deployment can use either route after the runtime target and destination have been selected. This includes direct-ROM/runtime targets such as open_agb_firm, TWiLight Menu++ / nds-bootstrap, Red Viper, DaedalusX64, RetroArch, and copying an existing CIA into `/cias/` for later installation.

Package generation remains separate. Generated GBA or Virtual Console CIAs first go through their package workflow; selecting SD versus FTP must never decide which runtime or package format is created.

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

The actual listing also showed additional ROM directories, including NES, SNES, Master System, WonderSwan, Neo Geo Pocket and other systems. These are observed storage contents, not universal 3DS requirements.

## Validation rules

Validation must be read-only. It must never create, delete, rename, or modify files merely to identify a storage target.

RommHeld only enables mounted-3DS writes for a **medium or high-confidence** 3DS SD root. The selected root is remembered after successful validation, but it is revalidated before use so an unplugged card, stale path, or unrelated replacement volume does not silently become writable 3DS storage.

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

A single generic directory such as `roms/` is not sufficient evidence for writes.

### TWiLight Menu++ / DS storage

Useful signatures include:

```text
_nds/
BOOT.NDS
roms/
```

TWiLight Menu++ provides multiple interfaces, including Nintendo 3DS, Nintendo DSi, R4 Original and Wood themes. Target identification should therefore remain a profile rather than assuming one UI.

### R4 / flashcart

Do not identify an R4 from one filename. Use a profile-specific set of indicators where possible, such as known kernel directories/files.

## Transfer safety

Mounted 3DS SD transfers reuse RommHeld's local staged-transfer semantics:

- destination paths are confined to the validated card root;
- same-size destinations can be skipped;
- a different-size destination is never silently overwritten;
- explicit replacement keeps the existing destination until the new staged file has copied successfully;
- cancellation preserves the existing destination;
- free space is checked before the staged copy when the operating system reports it;
- the final file size is verified before success is reported.

For RomM-backed games with a known positive source size, both mounted-SD and FTP routes can preflight the destination before downloading the ROM. If RomM does not provide a trustworthy size, RommHeld downloads first and determines the actual size rather than treating zero as authoritative.

After a mounted-SD transfer completes, eject the card cleanly before returning it to the console.

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

Each profile defines its root, platform mappings, validation signatures and capability metadata. Transport remains a separate choice after the deployment target and destination are known.

## FTP inspection note

The 3DS FTP server used during testing did not support `find -maxdepth`; the FTP client sent that argument as part of the remote path. Use ordinary directory listing/browsing for discovery unless the server explicitly advertises a compatible command.
