# Nintendo 3DS FTP hardware regression testing

Status: real-device validation pending

This document is the authoritative physical-device checklist for the RommHeld Nintendo 3DS FTP path on the active integration branch. Unit tests and CI validate path boundaries, staged-upload semantics, cancellation, rollback, listing fallbacks and UI policy, but they do not validate mtheall `ftpd`, the console filesystem, Wi-Fi behavior or real-device lifecycle.

## 1. 3DS preparation

RommHeld's recommended live filesystem server is `mtheall/ftpd`, normally on port `5000`. Use the IP address and port displayed by the console rather than assuming a fixed address.

Upstream:

`https://github.com/mtheall/ftpd`

For the first hardware pass, use the regular ftpd homebrew application rather than a background sysmodule. The desktop and 3DS should be on the same trusted local network.

RommHeld can also stage the verified `ftpd.3dsx` package to a mounted, high-confidence 3DS SD-card root from the 3DS readiness workflow. That package-staging route is separate from the live FTP connection itself.

## 2. RommHeld preparation

Use PR #21's active integration branch:

```fish
cd ~/romm-vita-manager
git fetch origin
git checkout refactor/apple-like-ui
git pull
./run.sh
```

Open the Nintendo 3DS workspace, then use **Device → Setup** for FTP configuration or **Device → Open 3DS manager** for transfer testing.

Enter:

- Host: the IP address shown by ftpd
- Port: the port shown by ftpd, commonly `5000`
- Username/password: leave at ftpd's documented defaults unless authentication was configured explicitly
- Remote root: `/` for the first test

Connect and confirm the UI reports the endpoint as connected.

### CONN-01: normal connection

- Start ftpd and leave it running.
- Connect from RommHeld.
- Confirm connection succeeds.
- Disconnect/close and reconnect.

### CONN-02: actionable failures

Test at least:

- ftpd not running / connection refused
- wrong IP address / timeout
- wrong credentials if authentication is enabled
- invalid configured remote root

Expected: RommHeld reports the relevant console-side correction and does not leave a half-open FTP client behind.

## 3. Safe first transfer

Do not start with a ROM. Create a small local test file:

```fish
printf 'RommHeld 3DS FTP test\n' > /tmp/rommheld-3ds-test.txt
```

Choose a harmless destination such as `/roms/rommheld-test/rommheld-3ds-test.txt`.

Expected:

1. RommHeld creates the destination directory if needed.
2. The upload goes first to a hidden RommHeld staging file in the destination directory.
3. The staging file is size-verified.
4. The verified stage is renamed into the final destination.
5. The UI reports success only after the final remote size is verified.
6. No `.rommheld-*.part` or `.rommheld-*.bak` file remains after an ordinary successful transfer.

Confirm the file contents using the 3DS filesystem/homebrew tools or a second FTP client.

## 4. Repeatability and replacement

### FTP-01: same-size skip

Send the same source to the same destination again.

Expected: RommHeld reports the file as already present and does not transfer it again.

This is intentionally a size-based skip because ftpd does not expose a remote checksum operation.

### FTP-02: different-size destination

Replace the destination manually with unrelated content whose size differs from the source, then deploy the source again.

Expected:

- the first preflight reports that a different-size file exists
- nothing is overwritten and a RomM-backed source is not downloaded yet
- RommHeld explicitly asks whether to replace the existing file
- declining leaves the destination unchanged

Approve the replacement on a second attempt.

Expected:

- the new source uploads to a separate staging file
- the old destination remains intact while upload and stage verification run
- immediately before the final swap, the old destination is moved to a hidden backup
- the verified stage is renamed into place
- the final file is size-verified
- the old backup is then removed

### FTP-03: do not resume an arbitrary destination

Create a destination that is smaller than the source but contains unrelated bytes.

Expected: RommHeld must not append the remainder of the source to that final file. It must report `different` and require the explicit replacement flow.

This specifically guards the old unsafe size-only resume behavior.

## 5. Interrupted and resumed staging

Use a sufficiently large lawful test file so transfer progress is visible.

### FTP-04: cancellation and retry

- Start a new upload and cancel after progress begins.
- Confirm the final destination has not been created or changed.
- A hidden `.rommheld-*.part` stage may remain intentionally.
- Retry the exact same source to the exact same destination.

Expected when ftpd accepts `REST` for uploads:

- RommHeld resumes the matching content-addressed stage
- the final destination is touched only after that stage reaches the complete source size
- the finished transfer is size-verified
- the staging file is removed by the final rename

The staging filename is tied to both the local source SHA-256 and destination path. A partial stage from different source content must not be resumed.

### FTP-05: server without REST

If practical, test with a server/configuration that rejects upload `REST`.

Expected: RommHeld abandons resume for that attempt and uploads the matching stage from byte zero rather than failing the transfer or appending to the final destination.

### FTP-06: network interruption

Stop ftpd or interrupt Wi-Fi during an upload.

Expected:

- RommHeld does not report success without final verification
- an existing final destination remains intact unless the verified replacement swap had already completed
- reconnect is possible without restarting RommHeld
- a valid partial RommHeld stage can be reused by a later matching retry where ftpd supports `REST`

## 6. Replacement rollback

Use an existing destination with recognizable contents, approve replacement, then force a failure around the final swap if practical, for example by stopping ftpd immediately after the staged upload completes.

Expected:

- if the old destination was already moved to a backup, RommHeld attempts to restore it
- a failed final rename must not intentionally delete the old destination
- recovery artifacts should be left intact rather than destroyed when automatic recovery itself cannot complete

Inspect the directory after reconnecting and record any `.part` or `.bak` residue.

## 7. Directory and root handling

### PATH-01: normal browsing

- Browse `/`, a ROM directory, and nested directories.
- Confirm directories sort ahead of files.
- Confirm navigation works with ftpd's normal `MLSD` listing.

### PATH-02: configured remote root

Configure a safe subdirectory as the remote root, reconnect, and confirm:

- connection fails clearly if the root does not exist
- transfers cannot escape the configured root
- `..` traversal is rejected

### PATH-03: listing fallback

`MLSD` is preferred. The backend also has an `NLST` fallback for compatible servers that omit `MLSD`; this is unit-tested but should be recorded if tested against an alternate server.

## 8. 3DS readiness and ftpd staging

With the 3DS SD card mounted on the desktop:

1. Open **Device → Runtime / FTP readiness**.
2. Select ftpd.
3. Stage the supported `ftpd.3dsx` package.
4. Confirm it lands in the expected `3ds/ftpd/ftpd.3dsx` path.
5. Reinsert/remount the SD card and launch ftpd through the Homebrew Launcher.
6. Complete CONN-01 using the staged application.

RommHeld must not treat this as a general CFW or homebrew-package-manager capability. Complex/system-sensitive packages remain delegated to their maintained upstream installation route or Universal-Updater.

## 9. Security and compatibility notes

FTP is unencrypted. Use it only on a trusted local network and do not expose the 3DS FTP server directly to the Internet.

RommHeld intentionally does not depend on `MDTM`. The backend uses the command set required for current transfers and verifies completion with `SIZE`.

## Validation record

Do not mark a route validated solely because CI passes.

| Area | Unit/CI | Desktop GUI | Real 3DS | Notes |
| --- | --- | --- | --- | --- |
| Connection/error handling | covered | pending | pending | Requires real ftpd |
| Remote-root enforcement | covered | pending | pending | Test existing and invalid roots |
| Directory listing | covered | pending | pending | MLSD on ftpd |
| New staged upload | covered | pending | pending | Verify hidden stage lifecycle |
| Same-size skip | covered | pending | pending | Size heuristic only |
| Different-size preflight | covered | pending | pending | Must not download RomM source before approval |
| Safe replacement/rollback | covered | pending | pending | Existing destination must survive failure |
| Cancellation/content-bound resume | covered | pending | pending | Confirm ftpd REST behavior |
| ftpd package staging | covered | pending | pending | Mounted SD plus real Homebrew Launcher |
| Reconnect/shutdown | partial | pending | pending | Exercise repeated connect/cancel/close |
