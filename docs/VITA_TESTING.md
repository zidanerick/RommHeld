# PlayStation Vita hardware regression testing

Status: real-device validation pending

This document is the authoritative Vita hardware regression checklist for the active RommHeld integration branch. Unit tests and CI validate path handling, rollback semantics, package selection, and other deterministic behavior, but they do not validate VitaShell, the Vita USB mass-storage implementation, ftpvitalib, Vita filesystem behavior, emulator launch behavior, or physical-device lifecycle.

## Scope

The current Vita regression pass covers:

- VitaShell USB mount detection and storage reporting
- VitaShell FTP connection and transfer behavior
- local-library destinations
- same-size skip and different-size replacement
- cancellation and rollback
- Send File over USB and FTP
- Vita Setup package download and staging
- emulator/frontend detection
- close-during-worker and reconnect behavior

Broad UI or architecture changes are out of scope unless a hardware failure demonstrates a concrete need.

## Expected Vita destinations

These paths are the current deployment contract. USB paths are relative to the filesystem VitaShell exposes as the storage backing `ux0:`. FTP paths use the equivalent `ux0:/...` path.

| Source | Expected destination | Notes |
| --- | --- | --- |
| PSP `.iso` / `.cso` | `ux0:/pspemu/ISO/<file>` | Adrenaline |
| PSP `.pbp` | `ux0:/pspemu/PSP/GAME/<game>/EBOOT.PBP` | Adrenaline |
| PS1 `.pbp` | `ux0:/pspemu/PSP/GAME/<game>/EBOOT.PBP` | Adrenaline |
| PS1 `.cue`, `.bin`, `.chd` | no automatic Adrenaline deployment | Requires conversion/alternate runtime rather than silent rename |
| Nintendo DS `.nds` | `ux0:/data/dsvita/<file>` | DSVita recommended directory |
| Vita `.vpk` | `ux0:/<file>.vpk` | Staged only; install manually with VitaShell |
| Other mapped retro ROM | `ux0:/data/RetroFlow/ROMS/<mapped system>/<file>` | RetroFlow default library layout |

A staged VPK must be shown as staged, not installed. RommHeld does not infer installed Vita application state merely because a VPK exists on storage.

## 1. VitaShell USB preparation

On the Vita:

1. Open VitaShell.
2. Press `START`.
3. Set `SELECT button` to `USB`.
4. Select the USB device that currently backs `ux0:`. This may be the memory card, SD2Vita, or another configured storage device.
5. Close Settings.
6. Press `SELECT` to start USB mode.
7. Connect the Vita to the desktop using a USB data cable.

RommHeld should detect the mounted filesystem only when it has strong VitaShell/ux0 evidence. A generic removable disk containing a few similarly named folders must not be treated as a Vita.

### USB-01: mount detection

- Start RommHeld with VitaShell USB disconnected.
- Confirm Vita state is not connected.
- Start VitaShell USB and refresh the Device page.
- Confirm RommHeld detects the correct mounted storage.
- Confirm displayed free/total storage is plausible for the selected Vita storage device.
- Stop VitaShell USB, refresh, and confirm RommHeld no longer treats the stale mount as connected.

### USB-02: Send File path mapping

Send a small test file to `ux0:/data/rommheld-regression/test.bin`.

Verify on the mounted filesystem that the final file is:

`data/rommheld-regression/test.bin`

There must not be an extra nested `ux0/` directory.

### USB-03: same-size skip

- Send/copy a test file successfully.
- Repeat the same operation without changing the source.
- Confirm RommHeld reports the destination as already present/skipped.
- Confirm the destination contents remain unchanged.

### USB-04: safe replacement

- Put an existing destination file on the Vita with different contents and a different size.
- Start a replacement through Send File or the local library.
- Confirm RommHeld explicitly asks before replacing a different-size destination.
- Approve the replacement.
- Confirm the old file remains in place until the replacement copy finishes.
- Confirm final size matches the source.
- Confirm no hidden `.rommheld-*.part` file remains.

### USB-05: cancellation rollback

Run both cases:

1. new destination
2. replacement of an existing destination

Cancel after transfer progress has started.

Expected:

- a new destination leaves no partial final file
- an existing destination remains byte-for-byte intact
- no `.rommheld-*.part` file remains
- the application remains responsive and can start another transfer

### USB-06: insufficient storage

Use a source larger than the available free space, or a controlled test volume when practical.

Expected:

- transfer is rejected before copying
- a safe replacement reserves enough space for the full staged replacement while retaining the old destination
- no destination or temporary file is modified

## 2. VitaShell FTP preparation

On the Vita:

1. Open VitaShell.
2. Press `START`.
3. Set `SELECT button` to `FTP`.
4. Close Settings.
5. Press `SELECT`.
6. Enter the IP address and port shown by VitaShell into RommHeld.
7. Keep the Vita and desktop on the same local network.

### FTP-01: connection lifecycle

- Connect with the correct endpoint.
- Confirm connection succeeds at the configured `ux0:` root.
- Disconnect and reconnect.
- Test a wrong address/closed port and confirm the error explains how to start VitaShell FTP and check the endpoint.

### FTP-02: path parity with USB

For representative PSP, PS1, NDS, VPK, and RetroFlow-mapped inputs, compare the destination preview over USB and FTP.

Expected: both transports resolve to the same logical `ux0:` destination.

### FTP-03: same-size and replacement

- Upload a new file.
- Repeat it and confirm same-size skip.
- Change the local source size.
- Confirm the batch-copy UI explicitly states that different-size destinations may be replaced before transfer starts.
- Approve it.
- Confirm the replacement is uploaded to a hidden temporary file, verified, and then swapped into place.
- Confirm no `.rommheld-*.part` or `.rommheld-*.backup` residue remains after a normal successful replacement.

### FTP-04: cancellation rollback

Cancel a transfer after progress starts, including one replacing an existing file.

Expected:

- existing destination remains intact
- temporary upload is removed using a fresh FTP session if cancellation desynchronizes the original control connection
- the next connection/transfer succeeds

### FTP-05: network interruption

Interrupt Wi-Fi or stop VitaShell FTP during a transfer.

Expected:

- RommHeld reports an actionable transfer/connection failure
- it does not report success without final remote-size verification
- an existing destination is not silently destroyed
- reconnect is possible without restarting RommHeld

## 3. Library destination validation

Use at least one small, lawful test file for each applicable route.

### LIB-01: PSP ISO/CSO

Expected: `ux0:/pspemu/ISO/` and visible/launchable through the configured Adrenaline/RetroFlow workflow after rescanning where required.

### LIB-02: PSP EBOOT.PBP

Expected: `ux0:/pspemu/PSP/GAME/<folder>/EBOOT.PBP`.

If the source is already literally named `EBOOT.PBP`, RommHeld should use its source parent directory as the game folder rather than creating an `EBOOT` folder.

### LIB-03: PS1 EBOOT.PBP

Expected: `ux0:/pspemu/PSP/GAME/<folder>/EBOOT.PBP`.

Raw `.cue`, `.bin`, or `.chd` inputs must not be silently renamed to `EBOOT.PBP` for Adrenaline.

### LIB-04: DSVita

Expected: `.nds` ROMs go to `ux0:/data/dsvita/`.

After copying:

- open DSVita
- confirm the ROM is visible using its default/recommended directory
- launch a known-good small test title if available

### LIB-05: generic RetroFlow system

Use at least one small ROM for a mapped RetroFlow system.

Expected:

- copy lands in `ux0:/data/RetroFlow/ROMS/<system>/`
- RetroFlow finds it after `Rescan`
- the configured runtime launches it

### LIB-06: Vita VPK staging

Copy a test/homebrew VPK from a local Vita platform folder.

Expected:

- VPK is staged at `ux0:/<name>.vpk`
- RommHeld reports it as staged, not installed
- VitaShell can see the VPK and install it manually
- after installation, the staged VPK remains a staging artifact unless the user removes it

## 4. Vita Setup package validation

RommHeld should never claim SHA-256 verification unless a trusted upstream digest was available. Successful download without an upstream digest is a successful download, not cryptographic provenance validation.

### SETUP-01: RetroFlow

- Download current configured RetroFlow package.
- Confirm digest verification succeeds when the configured/upstream digest is available.
- Stage the VPK.
- Install with VitaShell.
- Reopen Vita Setup and confirm RetroFlow is detected.

### SETUP-02: Adrenaline

RommHeld currently targets the official `6.61 Adrenaline-7` release because that is the version explicitly supported by the current RetroFlow documentation.

- Download and stage `Adrenaline.vpk`.
- Install with VitaShell if needed.
- Confirm detection through the expected Adrenaline application path.
- Confirm PSP/PS1 library routes work.

### SETUP-03: DSVita

- Download current configured DSVita VPK.
- Verify the configured SHA-256.
- Stage/install it.
- Confirm DSVita detection.
- Complete LIB-04.

Also confirm the user-facing prerequisite note remains accurate for the tested DSVita build, including any required plugins/runtime dependencies.

### SETUP-04: DaedalusX64

RommHeld uses the Vita-native `Rinnegatamante/DaedalusX64-vitaGL` release and stages `DaedalusX64.vpk`.

- Download the latest upstream VPK.
- Confirm GitHub-provided SHA-256 verification when present.
- Stage and install it.
- Confirm the installed title ID `DEDALOX64` is detected by RommHeld.
- Copy an N64 ROM through the normal RetroFlow mapping, rescan, and launch it through the configured RetroFlow/Daedalus route.

### SETUP-05: RetroArch

- Download/stage the configured RetroArch VPK.
- Confirm the companion data archive is inspected rather than blindly extracted.
- Complete manual/upstream-required data installation.
- Confirm a representative RetroFlow/libretro title launches.

## 5. Worker and application lifecycle

Run these after transfers work normally:

- cancel an active USB transfer
- cancel an active FTP transfer
- attempt to close Send File while a transfer is active
- attempt to close Vita Setup during package download/staging
- switch away from and back to the Vita workspace repeatedly
- disconnect USB while the app is open, then reconnect and refresh
- stop/restart VitaShell FTP and reconnect
- quit RommHeld after workers have completed

Acceptance criteria:

- no `QThread: Destroyed while thread is still running` abort
- no orphaned local/remote temporary files after normal cancellation
- no stale UI state claiming a disconnected Vita is connected after refresh
- no silent overwrite of a different-size destination without an explicit user decision

## Validation record

Record physical-device results here when executed. Do not mark a route validated solely from CI.

| Area | Unit/CI | Desktop GUI | Real Vita | Notes |
| --- | --- | --- | --- | --- |
| USB mount detection | covered | pending | pending | Requires VitaShell USB |
| USB copy/skip/replacement | covered | pending | pending | Atomic sibling staging |
| USB cancellation rollback | covered | pending | pending | Existing destination must survive |
| VitaShell FTP backend | covered | pending | pending | Requires real ftpvitalib behavior |
| VitaShell FTP library copy | covered | pending | pending | Destination parity required |
| PSP/PS1 Adrenaline routes | covered | pending | pending | Launch/rescan requires device |
| DSVita route | covered | pending | pending | `ux0:/data/dsvita/` |
| Vita VPK staging | covered | pending | pending | Staged is not installed |
| Vita Setup packages | covered | pending | pending | Install/launch requires device |
| Lifecycle/shutdown | partial | pending | pending | Exercise worker close/reconnect cases |
