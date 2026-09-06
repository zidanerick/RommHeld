# FTP file manager and 3DS application health

Status: implemented in automated tests; native desktop and real-device validation pending

This document is the authoritative feature contract for RommHeld's contextual FTP file manager and the Nintendo 3DS application-health layer. It supplements `ARCHITECTURE.md`, `DESIGN_SYSTEM.md`, and `UX_REFACTOR_PLAN.md` without changing the project's core separation between library selection, runtime/package choice, transport, and package generation.

## 1. Goals

RommHeld needs two related but distinct capabilities:

1. **Application readiness that explains repair paths.** Detection must distinguish evidence that an application exists from evidence that it actually works.
2. **A general remote filesystem tool for consoles with supported FTP servers.** Users should be able to inspect and manage files without forcing those operations through the game-library deployment workflow.

The current supported FTP file-manager targets are:

- Nintendo 3DS using mtheall `ftpd`
- PlayStation Vita using VitaShell FTP
- PlayStation TV using the same VitaShell FTP implementation

Nintendo DS remains removable-storage first. RommHeld does not expose a DS FTP file-manager route without a specific supported server implementation.

## 2. Presence is not health

`Detected` remains an evidence statement, not a launch-success claim.

RommHeld may detect an application through:

- a mounted-SD filesystem marker;
- a known installed CIA Title ID visible in the mounted or FTP-visible `Nintendo 3DS/<ID0>/<ID1>/title/` tree;
- a launch-surface marker;
- a successful live ftpd connection for ftpd itself.

The health layer in `three_ds_app_health.py` is intentionally separate from this evidence model.

Health states are:

- **Working / verified**: RommHeld has performed an operational check strong enough for the specific component. Currently a successful live ftpd connection qualifies for ftpd.
- **Present / launch not verified**: reliable installation/runtime evidence exists, but RommHeld cannot prove the application launches correctly on-console.
- **Needs attention**: evidence exists but an operational check failed, or only partial/runtime evidence is present.
- **Not verified**: RommHeld has no reliable evidence from the inspected sources. This is not always proof that a NAND-installed application is absent.

RommHeld must not silently promote installed-CIA or 3DSX evidence into a `Working` claim.

## 3. Repair guidance

The selected 3DS readiness component shows a separate Health section with conservative repair instructions.

Examples:

### ftpd

If ftpd is detected but the live service cannot be reached, RommHeld should distinguish common connection failures and tell the user to:

1. launch ftpd and leave it on its server screen;
2. verify the currently displayed IP address and port;
3. confirm the PC and 3DS are on the same local network;
4. update or reinstall ftpd with Universal-Updater if the application itself will not launch, or use RommHeld's verified Homebrew Launcher 3DSX preparation path as a diagnostic fallback;
5. refresh readiness and confirm a live connection before relying on wireless transfers.

A successful live ftpd scan is the current direct operational verification for ftpd.

### FBI

An installed FBI title or Homebrew Launcher executable is not proof that Remote Install works. The repair path tells the user to launch FBI, confirm the expected Remote Install workflow, update/reinstall if needed, then retry with a small lawful CIA.

### Universal-Updater

Presence does not prove catalogue/update operations work. The user is directed to launch the application, refresh its catalogue, and replace/update the maintained bootstrap if it cannot start normally.

### Red Viper and DaedalusX64

Presence remains launch-unverified. Repair guidance separates emulator installation from runtime/game problems and calls out console-generated DSP firmware where relevant.

### TWiLight Menu++ and RetroArch

Partial runtime/core folders are not treated as a complete working frontend. RommHeld directs the user to repair the maintained full installation or frontend/core route rather than copying isolated convenience files.

### Luma3DS, Homebrew Launcher foundation, GodMode9 and DSP data

System-sensitive components remain guide-driven or console-generated. RommHeld provides recovery guidance but does not automatically replace boot-chain components or download console-specific DSP data.

## 4. FTP file-manager architecture

The file manager shares presentation but does **not** merge the protocol backends.

```text
Device page
    -> FTP files
        -> FtpFileManagerDialog
            -> ftp_filesystem_for_console()
                -> ThreeDSFtpFilesystemAdapter
                    -> ThreeDSFtpBackend
                -> VitaFtpFilesystemAdapter
                    -> VitaFtpBackend
```

Relevant modules:

- `ftp_filesystem.py`: shared remote-filesystem contract and console-specific adapters
- `ftp_file_manager_ui.py`: shared Qt browser and operation workers
- `ftp_file_safety.py`: console-aware destructive-path warnings
- `three_ds_ftp.py`: 3DS ftpd protocol backend
- `vita_ftp.py`: VitaShell/ftpvitalib protocol backend
- `workspace_dashboard.py`: contextual Device-page launch actions

The shared UI must ask adapters what is supported rather than assuming every FTP server has the same command set.

## 5. Protocol capability differences

### Nintendo 3DS / mtheall ftpd

Current backend capabilities include:

- directory listing with MLSD and fallback behavior;
- upload;
- download;
- create directory;
- rename;
- delete file;
- remove empty directory;
- REST upload resume where the server supports it;
- ABOR cancellation where practical;
- SIZE verification;
- best-effort `SITE AVBL` free-space reporting.

Uploads retain the existing RommHeld verified staged-replacement behavior.

### Vita / PlayStation TV / VitaShell FTP

The Vita adapter follows ftpvitalib/VitaShell behavior rather than the 3DS assumptions:

- directory listing uses VitaShell's Unix-like `LIST` format;
- upload and download are supported;
- create directory, rename, delete file and remove empty directory are supported;
- upload resume is not advertised because VitaShell does not implement REST;
- free-space reporting is not advertised;
- ABOR is not treated as usable. Cancellation can require dropping the control connection so ftplib does not remain desynchronised.

The Vita file manager must explicitly say that free-space information is unavailable over VitaShell FTP rather than implying it will be checked during transfer.

## 6. File-manager operations

The current advanced file manager exposes:

- current endpoint/root display;
- breadcrumb-like current path plus Up navigation;
- refresh;
- name/type/size table;
- copy current remote path;
- upload one local file;
- download one remote file;
- create folder;
- rename file or folder;
- delete file;
- remove an **empty** directory;
- transfer progress and cancellation;
- different-size replacement confirmation;
- verified atomic local downloads;
- existing backend staged/verified remote uploads.

Routine game deployment remains in Library. The FTP browser is an advanced Device tool and is not a new permanent navigation destination.

## 7. Destructive-operation safety

Recursive remote deletion is intentionally not implemented.

Deleting or renaming under console-managed trees can damage installed software or saves, so the file manager uses stronger warnings for known sensitive locations.

Examples include:

### Nintendo 3DS critical paths

- `Nintendo 3DS/`
- `luma/`
- `gm9/`
- `boot.firm`
- `boot.3dsx`

Caution paths include `3ds/`, `_nds/`, and `cias/`.

### Vita critical paths

- `app/`
- `appmeta/`
- `license/`
- `patch/`
- `user/`
- `tai/`

Caution paths include `data/`, `pspemu/`, `addcont/`, and `repatch/`.

These warnings do not make arbitrary destructive changes safe. They are an additional guard for an explicitly advanced tool.

## 8. Worker and replacement lifecycle

Each file-manager operation owns a short-lived background FTP session. Network I/O does not run on the GUI thread.

The file manager follows the same worker-handoff rules as other RommHeld transfer surfaces:

- only one operation worker is active for the dialog at a time;
- a different-size upload performs preflight first;
- user replacement approval is recorded while that worker is still alive;
- the overwrite worker starts only after the first QThread emits `finished`;
- closing during an active transfer requests cancellation and waits for the operation worker to finish before destroying the dialog;
- local downloads write to a temporary sibling and replace the destination only after successful size verification;
- cancellation or failure removes the temporary local download and preserves an existing local destination;
- remote uploads reuse each console backend's existing destination-preserving staged replacement behavior.

## 9. Device-page placement

The Device page exposes **FTP files** only when the relevant FTP endpoint is configured.

### Nintendo 3DS

Contextual actions can include:

- Connection setup
- Mounted SD files
- FTP files
- Runtime readiness
- 3DS manager

### Vita / PlayStation TV

Contextual actions can include:

- Send file / configure FTP
- FTP files
- Vita setup

The button is disabled when no FTP endpoint is configured. The user is directed to the existing connection/configuration workflow rather than being given another competing settings surface.

## 10. Automated validation

At confirmed checkpoint `35e544f2dc8732159d1665d444be7cbcaa7f0a70`, GitHub Actions workflow #1840 passed:

- `python -m compileall -q .`
- full pytest suite: **581 passed**

Coverage includes:

- 3DS health semantics;
- live-ftpd versus installed-but-unverified state;
- app-specific repair guidance;
- VitaShell LIST parsing;
- protocol capability differences;
- root-relative remote entries;
- atomic verified downloads;
- Vita cancellation dropping the control connection;
- explicit file mutations and empty-directory-only removal;
- sensitive path warnings;
- file-manager Qt lifecycle;
- different-size upload worker handoff;
- contextual 3DS/Vita Device actions;
- absence of a DS FTP action.

Automated validation does not prove real ftpd/VitaShell interoperability, native desktop rendering, or console behavior.

## 11. Native desktop validation pending

Verify on the target desktop environment:

- the file manager fits the design system at normal and compact window sizes;
- long filenames and paths remain readable;
- selection/action enablement is clear;
- destructive warnings are visually distinct without becoming decorative branding;
- close/cancel does not leave a visible frozen dialog or `QThread` destruction warning;
- a different-size replacement prompt cannot start a second worker before the first finishes;
- 3DS health/repair text wraps cleanly and remains scannable for long app-specific instructions.

## 12. Real Nintendo 3DS validation pending

With real mtheall ftpd:

1. Connect and browse `/`.
2. Navigate several nested directories and return with Up.
3. Download a harmless test file and verify the local copy.
4. Upload a new harmless test file and verify it on the SD filesystem.
5. Create an empty test folder.
6. Rename a test file and test folder.
7. Delete a test file.
8. Remove the empty test folder.
9. Confirm the `Nintendo 3DS/` tree receives the critical destructive warning.
10. Cancel a larger upload and verify destination-preserving cleanup/resume behavior.
11. Cancel a larger download and verify no partial final local file remains.
12. Confirm best-effort free-space reporting behaves sensibly when `SITE AVBL` is supported and degrades to unavailable when it is not.
13. Close the dialog during an active transfer and verify safe cancellation/no Qt worker warning.
14. Stop ftpd while its installed-title evidence remains visible and confirm readiness says **Needs attention / service unreachable** with repair steps.
15. Restart ftpd and refresh readiness; confirm it changes to **Working / live connection verified**.
16. For FBI, Universal-Updater, Red Viper and Checkpoint, confirm detected presence still says **Launch not verified** until the user performs the on-console check described by RommHeld.

## 13. Real Vita / PlayStation TV validation pending

With VitaShell FTP active:

1. Connect to `ux0:` and confirm directory listing names, types and sizes parse correctly.
2. Navigate nested directories.
3. Download and verify a harmless test file.
4. Upload a new test file.
5. Create and remove an empty test folder.
6. Rename a test file/folder.
7. Delete a test file.
8. Confirm sensitive Vita paths receive stronger warnings.
9. Cancel an upload and verify VitaShell reconnect/temporary-file cleanup behavior.
10. Cancel a download and verify the local final destination remains intact.
11. Confirm the UI never claims VitaShell FTP free space is available.
12. Repeat on PlayStation TV, where FTP is the practical VitaShell transport.
13. Close during an active transfer and verify safe shutdown without an orphaned QThread.

## 14. Future expansion boundary

Do not turn the shared file-manager UI into a generic FTP backend abstraction that hides protocol differences.

A future console/server may join the file manager only when RommHeld has a concrete supported server implementation and can define its capabilities, path boundary, cancellation behavior, listing semantics, replacement safety and hardware test plan.
