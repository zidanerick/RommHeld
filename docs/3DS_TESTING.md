# Nintendo 3DS filesystem hardware regression testing

Status: real-device validation pending for mounted-SD and current ftpd changes

This document is the authoritative physical-device checklist for RommHeld Nintendo 3DS filesystem deployment on the active integration branch. Unit tests and CI validate path boundaries, staged-copy/upload semantics, cancellation, rollback, listing fallbacks, storage validation and UI policy, but they do not validate a real SD card, mtheall `ftpd`, the console filesystem, Wi-Fi behavior, card-reader behavior, clean-eject behavior, or real-device runtime visibility.

## 1. Supported transfer routes

RommHeld exposes two filesystem routes after the game/runtime target and destination are known:

- **Mounted SD card · Direct / offline**: remove the SD or microSD card, mount it on the desktop through a card reader, and copy directly to the validated card root.
- **ftpd · Wireless / live console**: leave the card in the 3DS, run mtheall `ftpd`, and transfer over the local network.

The direct-card route is not called USB. Nintendo 3DS systems do not expose a standard USB mass-storage mode. A USB card reader is simply one way the desktop may mount the SD card.

Generated GBA/Virtual Console CIA package workflows remain separate from transport selection. After a CIA is generated, RommHeld can deliver it through **FBI Remote Install · Install directly**, **Mounted SD card · Copy CIA**, or **ftpd · Copy CIA**. The mounted-SD and ftpd routes only copy the CIA to `/cias/`; installation remains a separate FBI action on the console.

## 2. Mounted SD preparation

1. Power the 3DS off fully before removing its SD or microSD card.
2. Mount the card on the desktop using an SD/microSD reader.
3. Open **Device -> Connection setup** or **Device -> Mounted SD files**.
4. Select the card root, not a nested `roms/` or `Nintendo 3DS/` directory.
5. Confirm RommHeld reports medium or high 3DS confidence before enabling writes.

A representative CFW card commonly contains at least two strong markers such as:

```text
boot.firm
boot.3dsx
luma/
gm9/
```

### SD-01: validation and persistence

- Select a valid 3DS card root and validate it.
- Close/reopen the Device page and Setup.
- Confirm the mounted root remains configured while the same card/path is present.
- Unmount the card and refresh.
- Confirm the route becomes unavailable rather than treating the stale path as writable storage.
- Mount an unrelated removable volume at a different path and confirm it is not accepted merely because it contains a generic `roms/` directory.

### SD-02: destination confinement

Attempt a harmless traversal-style destination during a controlled test.

Expected: paths that would escape the validated card root are rejected. No file outside the selected 3DS card root is created or modified.

### SD-03: new direct copy

Use a small lawful test file first, not a valuable ROM.

Expected:

1. RommHeld resolves the destination under the validated card root.
2. The file is copied through RommHeld's staged local-transfer path.
3. The final destination appears only after the staged copy completes.
4. The final size is verified before success is reported.
5. No `.rommheld-*.part` file remains after a normal successful copy.

### SD-04: same-size skip

Repeat the exact same transfer.

Expected: RommHeld reports the destination as already present and skips the copy.

### SD-05: explicit safe replacement

Replace the destination manually with recognizable different-size content, then deploy again.

Expected:

- RommHeld reports a different-size destination before replacement;
- the existing destination remains unchanged until the user approves replacement;
- after approval, the old destination remains available while the new staged file copies;
- only the verified staged file replaces the old destination;
- final size matches the source;
- no staged residue remains after normal success.

### SD-06: cancellation rollback

Test both:

1. a new destination;
2. replacement of an existing destination.

Cancel after progress begins.

Expected:

- a new destination leaves no partial final file;
- an existing destination remains intact;
- no staged local file remains after normal cancellation cleanup;
- another transfer can start without restarting RommHeld.

### SD-07: insufficient space

Use a controlled volume or source large enough to exceed available free space.

Expected:

- the transfer is rejected before copying;
- replacement planning reserves enough free space to retain the existing destination while staging the new copy;
- no destination or staged file is modified.

### SD-08: card removal during transfer

Only perform this with disposable test data. Start a larger transfer and remove/unmount the card during the copy.

Expected:

- RommHeld reports failure rather than success;
- it does not claim final verification;
- an existing destination is not intentionally deleted;
- after remounting, the card can be selected/validated again without restarting RommHeld.

### SD-09: logical destination parity

For representative filesystem targets, compare mounted-SD and ftpd deployment destinations:

- open_agb_firm GBA: `/roms/gba/<file>`
- TWiLight/nds-bootstrap NDS: `/roms/nds/<file>`
- Red Viper Virtual Boy: `/roms/virtualboy/<file>`
- DaedalusX64 N64: `/3ds/DaedalusX64/Roms/<file>`
- RetroArch: `/roms/<platform>/<file>`
- existing CIA copy: `/cias/<file>.cia`

Expected: changing transport changes only how bytes reach the card. It must not change runtime/package selection or the logical destination.

### SD-10: clean eject and console visibility

After successful transfers:

1. eject/unmount the card cleanly from the desktop;
2. return it to the powered-off console;
3. boot the 3DS;
4. open the intended runtime/frontend;
5. confirm the transferred file is visible at the expected path and can be opened where appropriate.

Record any runtime-specific rescan requirement separately from transfer success.

## 3. ftpd preparation

RommHeld's recommended live filesystem server is `mtheall/ftpd`, normally on port `5000`. Use the IP address and port displayed by the console rather than assuming a fixed address.

Upstream:

`https://github.com/mtheall/ftpd`

For the first hardware pass, use the regular ftpd homebrew application rather than a background sysmodule. The desktop and 3DS should be on the same trusted local network.

RommHeld can also stage the verified `ftpd.3dsx` package to a mounted, high-confidence 3DS SD-card root from the readiness workflow. Package staging is separate from the live FTP connection itself.

Use PR #21's active integration branch:

```fish
cd ~/romm-vita-manager
git fetch origin
git checkout refactor/apple-like-ui
git pull
./run.sh
```

Open the Nintendo 3DS workspace, then use **Device -> Connection setup** for FTP configuration or **Device -> Open 3DS manager** for advanced FTP browsing.

Enter:

- Host: the IP address shown by ftpd
- Port: the port shown by ftpd, commonly `5000`
- Username/password: leave at ftpd's documented defaults unless authentication was configured explicitly
- Remote root: `/` for the first test

### FTP-01: normal connection

- Start ftpd and leave it running.
- Connect from RommHeld.
- Confirm connection succeeds.
- Disconnect/close and reconnect.

### FTP-02: actionable failures

Test at least:

- ftpd not running / connection refused
- wrong IP address / timeout
- wrong credentials if authentication is enabled
- invalid configured remote root

Expected: RommHeld reports the relevant console-side correction and does not leave a half-open FTP client behind.

## 4. FTP staged transfer and replacement

Create a small local test file:

```fish
printf 'RommHeld 3DS FTP test\n' > /tmp/rommheld-3ds-test.txt
```

Choose a harmless destination such as `/roms/rommheld-test/rommheld-3ds-test.txt`.

Expected for a new upload:

1. RommHeld creates the destination directory if needed.
2. The upload goes first to a hidden RommHeld staging file in the destination directory.
3. The staging file is size-verified.
4. The verified stage is renamed into the final destination.
5. The UI reports success only after the final remote size is verified.
6. No `.rommheld-*.part` or `.rommheld-*.bak` file remains after an ordinary successful transfer.

Confirm the file contents using 3DS filesystem/homebrew tools or a second FTP client.

### FTP-03: same-size skip

Send the same source to the same destination again.

Expected: RommHeld reports the file as already present and does not transfer it again. This is intentionally size-based because ftpd does not expose a remote checksum operation.

### FTP-04: different-size destination

Replace the destination manually with unrelated content whose size differs from the source, then deploy the source again.

Expected before approval:

- the preflight reports a different-size file;
- nothing is overwritten;
- a RomM-backed source with known positive metadata size is not downloaded yet;
- RommHeld explicitly asks whether to replace the existing file.

After approval:

- the new source uploads to a separate staging file;
- the old destination remains intact while upload and stage verification run;
- immediately before the final swap, the old destination is moved to a hidden backup;
- the verified stage is renamed into place;
- the final file is size-verified;
- the old backup is removed after success.

### FTP-05: do not resume an arbitrary destination

Create a destination smaller than the source but containing unrelated bytes.

Expected: RommHeld must not append the source remainder to that final file. It reports `different` and requires explicit replacement.

## 5. FTP cancellation, resume and network interruption

Use a sufficiently large lawful test file so transfer progress is visible.

### FTP-06: cancellation and retry

- Start a new upload and cancel after progress begins.
- Confirm the final destination has not been created or changed.
- A hidden content-addressed RommHeld stage may remain intentionally.
- Retry the exact same source to the exact same destination.

Expected when ftpd accepts `REST` for uploads:

- RommHeld resumes the matching content-addressed stage;
- the final destination is touched only after the stage reaches full source size;
- the finished transfer is size-verified;
- the staging file is removed by the final rename.

A partial stage from different source content must not be resumed.

### FTP-07: server without REST

If practical, test with a server/configuration that rejects upload `REST`.

Expected: RommHeld restarts the matching stage from byte zero for that attempt rather than appending to the final destination.

### FTP-08: network interruption

Stop ftpd or interrupt Wi-Fi during an upload.

Expected:

- RommHeld does not report success without final verification;
- an existing final destination remains intact unless the verified replacement swap had already completed;
- reconnect is possible without restarting RommHeld;
- a valid partial RommHeld stage can be reused by a later matching retry where ftpd supports `REST`.

### FTP-09: replacement rollback

Use an existing destination with recognizable contents, approve replacement, then force a failure around the final swap if practical.

Expected:

- if the old destination was already moved to backup, RommHeld attempts restoration;
- a failed final rename must not intentionally delete the old destination;
- recovery artifacts are preserved rather than destroyed if automatic recovery cannot complete.

## 6. FTP directory and root handling

### FTP-10: normal browsing

- Browse `/`, a ROM directory, and nested directories.
- Confirm directories sort ahead of files.
- Confirm navigation works with ftpd's normal `MLSD` listing.

### FTP-11: configured remote root

Configure a safe subdirectory as the remote root, reconnect, and confirm:

- connection fails clearly if the root does not exist;
- transfers cannot escape the configured root;
- `..` traversal is rejected.

### FTP-12: listing fallback

`MLSD` is preferred. The backend also has an `NLST` fallback for compatible servers that omit `MLSD`; this is unit-tested but should be recorded if tested against an alternate server.

## 7. RomM-backed library deployment

Run representative transfers from the 3DS Library using both mounted SD and ftpd.

### LIB-01: known RomM size preflight

For a title whose RomM metadata contains a positive file size:

- create an equal-size destination and deploy;
- confirm RommHeld skips before downloading the ROM;
- create a different-size destination and deploy;
- confirm RommHeld asks before replacement and does not download until approval.

### LIB-02: unknown RomM size

Use or simulate a RomM record without trustworthy positive size metadata.

Expected: RommHeld downloads first, determines the real source size, then applies the same destination checks. Zero metadata must not be treated as an authoritative file size.

### LIB-03: transport switching

With both routes available:

- select mounted SD and deploy a small test title;
- select ftpd and deploy another or repeat after controlled cleanup;
- confirm the runtime target and destination preview do not change when only the transport changes.

Package-generation targets such as generated GBA HOME Menu CIA and Nintendo VC CIA must not be converted into ordinary ROM-copy targets by switching this selector.

## 8. Generated CIA delivery through mounted SD

This section validates the package-to-card boundary, not the correctness of the VC injector itself. Use a generated CIA family that has already passed the relevant packaging prerequisites.

### CIA-SD-01: generated CIA copy

1. Mount and validate the 3DS SD card.
2. Open a generated GBA or classic Virtual Console package workflow.
3. Confirm the delivery choices include:
   - **FBI Remote Install · Install directly**
   - **Mounted SD card · Copy CIA**
   - **ftpd · Copy CIA**
4. Select **Mounted SD card · Copy CIA**.
5. Build the CIA and let the transfer complete.
6. Confirm RommHeld reports a verified copy under `/cias/` and does not claim that the CIA is installed.
7. Confirm no staged `.rommheld-*.part` file remains after normal success.

Expected: package generation is unchanged by transport choice. Mounted SD only changes delivery of the completed CIA.

### CIA-SD-02: clean eject and manual installation

1. Eject/unmount the SD card cleanly.
2. Return it to the powered-off 3DS and boot the console.
3. Open FBI and browse to the copied CIA under `/cias/`.
4. Confirm the CIA is present and install it manually.
5. Confirm RommHeld's earlier copy status was accurate: the file was copied, but installation occurred only after the explicit FBI action.

For a family still awaiting real-device package validation, continue with that family's separate launch/save/relaunch checklist after installation. A successful SD copy does not validate the generated CIA runtime.

### CIA-SD-03: delivery parity

For the same generated CIA, compare the logical destination shown by Mounted SD and ftpd copy modes.

Expected:

- both copy modes use the same `/cias/...` destination;
- FBI Remote Install remains the only route labelled as direct installation;
- selecting Mounted SD or ftpd does not change Title ID allocation, donor/runtime selection, package contents, or metadata.

## 9. Readiness and ftpd staging

With the 3DS SD card mounted on the desktop:

1. Open **Device -> Runtime readiness**.
2. Select ftpd.
3. Stage the supported `ftpd.3dsx` package.
4. Confirm it lands in `3ds/ftpd/ftpd.3dsx`.
5. Eject the SD card cleanly, reinsert it in the 3DS, and launch ftpd through the Homebrew Launcher.
6. Complete FTP-01 using the staged application.

RommHeld must not treat this as a general CFW/homebrew package manager. Complex or system-sensitive packages remain delegated to their maintained upstream route or Universal-Updater.

## 10. Security and compatibility notes

FTP is unencrypted. Use it only on a trusted local network and do not expose the 3DS FTP server directly to the Internet.

RommHeld intentionally does not depend on `MDTM`. The backend uses the command set required for current transfers and verifies completion with `SIZE`.

## Validation record

Do not mark a route validated solely because CI passes.

| Area | Unit/CI | Desktop GUI | Real 3DS | Notes |
| --- | --- | --- | --- | --- |
| Mounted-SD root validation | covered | pending | pending | Medium/high confidence required for writes |
| Mounted-SD path confinement | covered | pending | pending | Must never escape selected card root |
| Mounted-SD copy/skip/replacement | covered | pending | pending | Local staged-transfer semantics |
| Mounted-SD cancellation | covered | pending | pending | Existing destination must survive |
| Mounted-SD free-space preflight | covered | pending | pending | OS-reported free space |
| Mounted-SD removal/recovery | partial | pending | pending | Requires real removable media |
| SD/FTP logical destination parity | covered | pending | pending | Same target/destination, different transport |
| Generated CIA mounted-SD copy | covered | pending | pending | Copy only; manual FBI install remains separate |
| Generated CIA SD/FTP delivery parity | covered | pending | pending | Transport must not alter package identity/content |
| ftpd connection/error handling | covered | pending | pending | Requires real ftpd |
| FTP remote-root enforcement | covered | pending | pending | Test existing and invalid roots |
| FTP directory listing | covered | pending | pending | MLSD on ftpd |
| FTP new staged upload | covered | pending | pending | Verify hidden stage lifecycle |
| FTP same-size skip | covered | pending | pending | Size heuristic only |
| FTP different-size preflight | covered | pending | pending | Known RomM size should avoid download before approval |
| FTP safe replacement/rollback | covered | pending | pending | Existing destination must survive failure |
| FTP cancellation/content-bound resume | covered | pending | pending | Confirm ftpd REST behavior |
| ftpd package staging | covered | pending | pending | Mounted SD plus real Homebrew Launcher |
| Reconnect/shutdown | partial | pending | pending | Exercise repeated connect/cancel/close |
