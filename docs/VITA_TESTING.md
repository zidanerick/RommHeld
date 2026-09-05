# PlayStation Vita hardware regression testing

Status: real-device validation pending

This document is the authoritative Vita hardware regression checklist for the active RommHeld integration branch. Unit tests and CI validate path handling, rollback semantics, package selection, transport routing and other deterministic behavior, but they do not validate VitaShell, Vita USB mass storage, ftpvitalib, Vita filesystem behavior, emulator launch behavior or physical-device lifecycle.

## Scope

The current Vita regression pass covers:

- VitaShell USB mount detection and storage reporting
- VitaShell FTP connection and transfer behavior
- PlayStation TV operation without a USB mount
- local-library destinations over USB and FTP
- same-size skip and different-size replacement
- cancellation and rollback
- Send File over USB and FTP
- Vita Setup package download and staging over USB and FTP
- emulator/frontend detection where storage is mounted
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
4. Select the USB device that currently backs `ux0:`. This may be the memory card, SD2Vita or another configured storage device.
5. Close Settings.
6. Press `SELECT` to start USB mode.
7. Connect the Vita to the desktop using a USB data cable.

RommHeld should detect the mounted filesystem only when it has strong VitaShell/ux0 evidence. A generic removable disk containing a few similarly named folders must not be treated as a Vita. VitaShell itself creates the `ux0:VitaShell` tree, so RommHeld uses that together with the installed VitaShell application and supporting ux0 structure rather than relying on generic folder names alone.

### USB-01: mount detection

- Start RommHeld with VitaShell USB disconnected.
- Confirm Vita state is not connected.
- Start VitaShell USB and refresh the Device page.
- Confirm RommHeld detects the correct mounted storage.
- Confirm displayed free/total storage is plausible for the selected Vita storage device.
- Stop VitaShell USB, refresh, and confirm RommHeld no longer treats the stale mount as connected.
- If two filesystems with strong VitaShell/ux0 evidence are simultaneously visible to the desktop, confirm RommHeld does not auto-select either one. Ambiguous detection must fail closed rather than choosing the first mount.

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
- Confirm RommHeld explicitly asks before replacing a different-size destination where that workflow preflights local state.
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

On the Vita or PlayStation TV:

1. Open VitaShell.
2. Press `START`.
3. Set `SELECT button` to `FTP`.
4. Close Settings.
5. Press `SELECT`.
6. Enter the IP address and port shown by VitaShell into RommHeld from **Device → Send file / configure FTP**.
7. Keep the Vita/PSTV and desktop on the same trusted local network.

The normal VitaShell/ftpvitalib port is `1337`, but use the endpoint actually displayed by VitaShell.

### FTP-01: connection lifecycle

- Connect with the correct endpoint.
- Confirm connection succeeds at the configured `ux0:` root.
- Disconnect and reconnect.
- Test a wrong address/closed port and confirm the error explains how to start VitaShell FTP and check the endpoint.

### FTP-02: path parity with USB

For representative PSP, PS1, NDS, VPK and RetroFlow-mapped inputs, compare the destination preview over USB and FTP.

Expected: both transports resolve to the same logical `ux0:` destination.

### FTP-03: same-size and replacement

- Upload a new file.
- Repeat it and confirm same-size skip.
- Change the local source size.
- In the library workflow, confirm the batch-copy confirmation states that different-size files can be safely replaced and that free space cannot be pre-checked over FTP.
- Confirm the replacement is uploaded to a hidden temporary file, verified, and then swapped into place.
- Confirm an existing destination remains in place until the new upload is verified.
- Confirm no `.rommheld-*.part` or `.rommheld-*.backup` residue remains after a normal successful replacement.

### FTP-04: cancellation rollback

Cancel a transfer after progress starts, including one replacing an existing file.

Expected:

- existing destination remains intact
- temporary upload is removed using a fresh FTP session if cancellation desynchronizes the original control connection
- the next connection/transfer succeeds

VitaShell FTP does not implement usable `ABOR` semantics for this workflow, so RommHeld deliberately drops the affected control connection on cancellation and cleans the temporary upload through a new session.

### FTP-05: network interruption

Interrupt Wi-Fi or stop VitaShell FTP during a transfer.

Expected:

- RommHeld reports an actionable transfer/connection failure
- it does not report success without final remote-size verification
- an existing destination is not silently destroyed
- reconnect is possible without restarting RommHeld

### FTP-06: PlayStation TV without USB

Run RommHeld with no Vita USB mount available and a saved VitaShell FTP endpoint.

Expected:

- Device shows the saved FTP endpoint without claiming that a USB filesystem is mounted
- **Send file / configure FTP** opens even though there is no USB mount
- Send File can transfer to `ux0:/...`
- the normal Vita library can select VitaShell FTP and deploy mapped content
- Vita Setup can select VitaShell FTP and stage supported VPK packages
- unavailable USB capacity/install-state information is not fabricated

## 3. Library destination validation

Use at least one small, lawful test file for each applicable route.

### LIB-01: PSP ISO/CSO

Expected: `ux0:/pspemu/ISO/` and visible/launchable through the configured Adrenaline/RetroFlow workflow after rescanning where required.

### LIB-02: PSP EBOOT.PBP

Expected: `ux0:/pspemu/PSP/GAME/<folder>/EBOOT.PBP`.

If the source is already literally named `EBOOT.PBP`, RommHeld should use its source parent directory as the game folder rather than creating an `EBOOT` folder.

### LIB-03: PS1 EBOOT.PBP

Expected: `ux0:/pspemu/PSP/GAME/<folder>/EBOOT.PBP`.

Raw `.cue`, `.bin` or `.chd` inputs must not be silently renamed to `EBOOT.PBP` for Adrenaline.

### LIB-04: DSVita

Expected: `.nds` ROMs go to `ux0:/data/dsvita/`.

After copying:

- confirm `libshacccg.suprx` is installed using the upstream-supported extraction/VitaDB route
- confirm `kubridge.skprx` version `0.3.1` or later is installed in the `*KERNEL` section; the current upstream hotfix release remains `0.3.1`
- open DSVita
- confirm the ROM is visible using its default/recommended directory
- launch a known-good small test title if available

Do not treat DSVita VPK installation alone as runtime readiness. RommHeld must not redistribute `libshacccg.suprx` or silently rewrite the user's kernel plugin configuration.

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

Run this once over USB and once over FTP when practical.

## 4. Vita Setup package validation

RommHeld should never claim SHA-256 verification unless a trusted upstream digest was available. Successful download without an upstream digest is a successful download, not cryptographic provenance validation.

Vita Setup now exposes two staging transports:

- `VitaShell USB · Recommended`
- `VitaShell FTP · Wireless / PlayStation TV`

Package selection/download remains independent from transport. Archive packages remain review-only until an explicit traversal-safe extraction rule exists.

### SETUP-01: RetroFlow

- Download current configured RetroFlow package.
- Confirm digest verification succeeds when the configured/upstream digest is available.
- Stage the VPK over USB.
- Stage it again over FTP and confirm the logical target remains `ux0:/RetroFlow_emu4vita.vpk`.
- Install with VitaShell.
- Reopen Vita Setup with USB mounted and confirm RetroFlow is detected.

### SETUP-02: Adrenaline

RommHeld currently targets the official `6.61 Adrenaline-7` release because that is the version explicitly supported by the current RetroFlow documentation.

- Download and stage `Adrenaline.vpk`.
- Exercise at least one staging transport, and FTP specifically on PSTV.
- Install with VitaShell if needed.
- Confirm detection through the expected Adrenaline application path when USB storage inspection is available.
- Confirm PSP/PS1 library routes work.

### SETUP-03: DSVita

RommHeld prepares the DSVita VPK but does not claim that the VPK alone makes DSVita runnable. Current upstream installation requirements are part of the hardware readiness test:

- download the current configured DSVita VPK and verify the configured SHA-256
- stage/install the VPK
- confirm DSVita title ID `DSVITA000` is detected with USB inspection
- install `libshacccg.suprx` through the upstream-supported extraction guide or VitaDB route; RommHeld does not redistribute it
- install `kubridge.skprx` version `0.3.1` or later, currently the upstream `v0.3.1_hotfix` release
- confirm kubridge is configured in the Vita `*KERNEL` section before launch
- complete LIB-04 and launch a representative `.nds` title

If DSVita crashes at startup or cannot launch games, check those prerequisites before treating the RommHeld ROM deployment route as failed.

### SETUP-04: DaedalusX64

RommHeld uses the Vita-native `Rinnegatamante/DaedalusX64-vitaGL` release and stages `DaedalusX64.vpk`.

- Download the latest upstream VPK.
- Confirm GitHub-provided SHA-256 verification when present.
- Stage and install it.
- Confirm the installed title ID `DEDALOX64` is detected by RommHeld when USB inspection is available.
- Copy an N64 ROM through the normal RetroFlow mapping, rescan, and launch it through the configured RetroFlow/Daedalus route.

### SETUP-05: RetroArch

RommHeld currently targets stable RetroArch `1.22.2` for Vita and models the VPK and required data payload as separate readiness components.

- confirm Vita Setup exposes separate `RetroArch` and `RetroArch data` rows
- download/stage `RetroArch.vpk` from the configured `1.22.2` stable Vita build
- install the VPK with VitaShell and confirm the installed RetroArch application is detected independently of its data directory
- download `RetroArch_data.7z` from the same `1.22.2` stable Vita build
- confirm the companion archive is inspected rather than blindly extracted
- manually install/extract the required contents according to upstream into `ux0:/data/retroarch/`
- reopen Setup with USB inspection and confirm the data readiness row is detected independently of the application row
- confirm a representative RetroFlow/libretro title launches

RommHeld must not auto-extract the 7z payload until an explicit extraction implementation rejects traversal, unsafe links and other archive escape cases.

### SETUP-06: FTP package replacement safety

With a supported VPK already staged at its target, stage a different-size replacement through Vita Setup FTP.

Expected:

- package preparation remains in the local cache until staging starts
- FTP uses the Vita-specific package transport adapter
- the replacement goes through VitaShell FTP's verified temporary-upload path
- the existing VPK remains recoverable until the new upload verifies and swaps into place
- final remote size matches the downloaded package
- no ordinary-success `.part` or `.backup` residue remains

### SETUP-07: download-to-stage worker lifecycle

Start a package download and accept the prompt to stage it immediately after download.

Run once with USB and once with FTP.

Expected:

- the download worker fully finishes before the stage worker starts
- transport controls remain locked while each worker is active
- there is no `QThread: Destroyed while thread is still running` warning or abort
- closing is blocked while the current package worker is active

Vita Setup exposes a user-facing cancellation control for downloads and USB/FTP staging. While a package worker is active, Done/accept, Escape/reject and the window close action must all keep the dialog alive until the current worker has finished cancelling or completed normally.

## 5. Worker and application lifecycle

Run these after transfers work normally:

- cancel an active USB transfer
- cancel an active FTP transfer
- attempt to close Send File while a transfer is active
- press Escape in Send File while a transfer is active
- attempt to close Vita Setup during package download/staging
- press Escape in Vita Setup during package download/staging
- stage a package immediately after download using both transports
- switch away from and back to the Vita workspace repeatedly
- disconnect USB while the app is open, then reconnect and refresh
- stop/restart VitaShell FTP and reconnect
- quit RommHeld after workers have completed

Acceptance criteria:

- no `QThread: Destroyed while thread is still running` abort
- no orphaned local/remote temporary files after normal cancellation
- no stale UI state claiming a disconnected Vita is connected after refresh
- no silent overwrite of a different-size destination where explicit confirmation is part of the workflow
- FTP-only/PSTV operation never claims USB-derived capacity or install-state knowledge

## Validation record

Record physical-device results here when executed. Do not mark a route validated solely from CI.

| Area | Unit/CI | Desktop GUI | Real Vita/PSTV | Notes |
| --- | --- | --- | --- | --- |
| USB mount detection | covered | pending | pending | Strong VitaShell evidence; ambiguous candidates fail closed |
| USB copy/skip/replacement | covered | pending | pending | Atomic sibling staging |
| USB cancellation rollback | covered | pending | pending | Existing destination must survive |
| VitaShell FTP backend | covered | pending | pending | Requires real ftpvitalib behavior |
| VitaShell FTP library copy | covered | pending | pending | Destination parity required |
| PSTV FTP-only workflow | covered | pending | pending | No USB mount available |
| PSP/PS1 Adrenaline routes | covered | pending | pending | Launch/rescan requires device |
| DSVita route | covered | pending | pending | `ux0:/data/dsvita/`; libshacccg + kubridge prerequisites |
| Vita VPK staging | covered | pending | pending | Staged is not installed |
| Vita Setup package USB staging | covered | pending | pending | Install/launch requires device |
| Vita Setup package FTP staging | covered | pending | pending | PSTV-capable path |
| RetroArch VPK/data readiness | covered | pending | pending | 1.22.2; archive remains review-only |
| Package cancellation UI/backend | covered | pending | pending | Download and USB/FTP staging cancellation exposed |
| Download-to-stage worker handoff | covered | pending | pending | Must fully finish old QThread first |
| Dialog dismissal during worker | covered | pending | pending | Done, Escape and window close must preserve live worker ownership |
| Lifecycle/shutdown | partial | pending | pending | Exercise worker close/reconnect cases |
