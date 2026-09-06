# PlayStation Vita runtime health evidence

This document defines the Vita-specific runtime/readiness evidence contract used by `vita_health.py` and Vita Setup. It complements `VITA_TESTING.md`, which remains the authoritative physical transport and hardware regression checklist.

## Principles

Runtime health is separate from transport, package preparation and UI presentation.

- `vita_health.py` owns read-only filesystem/config evidence and health classification.
- `vita_setup.py` renders the service result and routes packageable components through the existing verified package workers.
- `vita.py` remains responsible for conservative VitaShell USB mount detection and storage information.
- VitaShell USB/FTP transport remains in the existing transport modules.
- Package download/staging remains in `package_manager.py` and `vita_package_transport.py`.

Filesystem evidence can prove that files or structural prerequisites exist. It cannot prove that an installed application launches successfully on the Vita. Installed application files therefore remain **Present · launch not verified** until hardware testing confirms launch behavior.

A staged VPK is always staging evidence only. It must never be reported as an installed application.

## Health states

| State | Meaning |
| --- | --- |
| Healthy | The specific structural/data/dependency condition being checked is satisfied by reliable evidence. This does not convert an application into launch-verified state. |
| Present · launch not verified | Installed application files are present, but RommHeld has no real console launch result. |
| Partial | Some required/expected evidence exists, but the installation/runtime evidence is incomplete. |
| Data/assets only | Runtime/user data exists without installed application evidence. |
| Missing | The relevant volume was inspected and the expected evidence was absent. |
| Misconfigured | RommHeld can prove a concrete invalid configuration, such as a taiHEN `*KERNEL` reference to a missing plugin. |
| Outdated | Reserved for evidence-backed version detection. Do not use this state merely because upstream has a newer release. |
| Not checked | The required volume/source was not inspected or the evidence could not be read. |
| Manual-only | The condition is system-sensitive or not safe for RommHeld to modify automatically. The current implementation normally represents this as repair capability on a concrete Missing/Partial/Misconfigured state rather than changing the factual state. |

## Evidence boundaries

`VitaFilesystemEvidence` records which Vita volumes were actually inspected. Absence on an unchecked volume is never interpreted as a missing file.

Normal VitaShell USB mode exposes the selected `ux0:` storage to the desktop. It does not establish that RommHeld has inspected `ur0:`. Therefore:

- ux0 application/data evidence can be inspected through the normal mounted filesystem;
- `ur0:/data/libshacccg.suprx` remains **Not checked** on an ordinary ux0-only mount;
- a kubridge line referencing `ur0:` remains **Not checked** unless ur0 evidence is separately supplied;
- FTP configuration alone is not runtime evidence, so FTP-only/PSTV Setup states remain **Not checked** rather than Missing.

The evidence collector deliberately probes only known runtime paths. It does not crawl or persist ROM libraries, saves or arbitrary application data. It reads taiHEN `config.txt` only when that exact configuration file is part of the supplied/mounted evidence.

Hardware findings must be converted into sanitized synthetic path/config fixtures. Never commit a user's raw device tree or personal device dump.

## taiHEN and kubridge

The active taiHEN configuration is resolved conservatively using the documented precedence:

1. `ux0:tai/config.txt` when present;
2. otherwise `ur0:tai/config.txt` when ur0 has actually been inspected.

kubridge is structurally checked only when RommHeld can read the active configuration. The service verifies that:

- a kubridge path appears under `*KERNEL`;
- the referenced volume was inspected;
- the referenced plugin file exists.

RommHeld does **not** blindly edit taiHEN configuration and does not infer kubridge's binary version from the filename. DSVita currently requires kubridge 0.3.1 or later, but the health service reports a configured file as present/version-unverified unless a future trusted version source is implemented.

## libshacccg

The standard runtime location checked by the health service is:

`ur0:/data/libshacccg.suprx`

A copy found only under `ur0:/data/external/` is partial evidence, not equivalent runtime readiness. RommHeld does not redistribute or silently install `libshacccg.suprx`.

## Component evidence

### VitaShell

Installed app evidence uses the `VITASHELL` application tree plus its executable. The `ux0:/VitaShell` data tree is supporting evidence. VitaShell is system/transport-sensitive and is not automatically repaired by this readiness service.

### RetroFlow

Installed app evidence and `ux0:/data/RetroFlow` are distinguished. A staged `RetroFlow_emu4vita.vpk` remains partial/staged evidence only.

### Adrenaline

The application tree is `ux0:/app/PSPEMUCFW/`. `ux0:/pspemu/` is supporting runtime/content evidence. The known `adrenaline_kernel.skprx` path can be inspected separately in future readiness work, but its absence is not currently treated as proof that Adrenaline is unusable because upstream configuration varies by installation/update history.

### RetroArch frontend

The health model recognizes the current `RETROARCH` application tree and the older `RETROVITA` tree already supported by RommHeld. Application presence is kept separate from companion data.

### RetroArch data

`ux0:/data/retroarch/` is the companion data root. Presence of its assets tree is treated as strong structural data evidence. This is not a frontend launch test.

### RetroArch cores

Vita static libretro cores are inventoried from `*_libretro.self` executables inside the installed RetroArch application tree. The current health service reports whether any cores are structurally present. Per-platform core requirements and game-specific firmware remain hardware/runtime validation rather than guessed global health.

### DaedalusX64

The native app is checked independently. Because the current Vita build is vitaGL-based, libshacccg evidence is included as a runtime dependency. If ur0 is unavailable, the app remains present/launch-unverified with the dependency explicitly Not checked.

### Flycast

The `FLYCASTDC` app is checked independently. Current Vita builds rely on vitaGL/vitashark and kubridge; the health model therefore includes both libshacccg and kubridge evidence without pretending their versions are known.

### ScummVM

The app tree and `ux0:/data/scummvm/` are separate evidence. Data without the app is **Data/assets only**.

### DSVita

The `DSVITA000` app is not sufficient runtime readiness on its own. Current upstream requirements include:

- `libshacccg.suprx` in the supported runtime location;
- kubridge 0.3.1 or later;
- kubridge configured under taiHEN `*KERNEL`.

RommHeld will not redistribute libshacccg or silently rewrite taiHEN configuration. Even when all structural prerequisites are present, DSVita remains **Present · launch not verified** until a real Vita launch/game test succeeds.

### FAKE-08

The `FAKE00008` app and `ux0:/p8carts/` cart data are separate evidence. Cart data by itself is not application-install evidence.

## Repair boundary

Safe automatic actions remain narrow:

- verified package download/cache preparation;
- VitaShell USB staging;
- VitaShell FTP verified temporary upload and safe replacement;
- manual VitaShell installation of staged VPKs.

Manual/system-sensitive conditions remain read-only unless a future adapter has sufficiently well-understood format and semantics to edit narrowly and preserve user configuration. Current examples include taiHEN plugin configuration and libshacccg installation.

## Hardware evidence intake

During physical validation, record only the facts needed to test a rule. Useful sanitized evidence includes:

- whether the known app directory and `eboot.bin` exist;
- whether the relevant runtime/data directory exists;
- the names of RetroArch `*_libretro.self` executables;
- whether `ur0:/data/libshacccg.suprx` exists;
- which taiHEN config is active;
- a sanitized `*KERNEL` section containing only plugin paths relevant to the check;
- the actual kubridge version from a trusted source if it can be established;
- launch/pass/fail results performed on the Vita.

Convert those observations into synthetic fixtures in `tests/`. Do not add the raw filesystem listing.

## Physical validation

Runtime evidence tests do not replace `docs/VITA_TESTING.md`. The real Vita regression must still cover VitaShell USB and FTP transfer, cancellation, safe replacement, same-size/staged skip, stale disconnect behavior, Send File, Vita Setup staging and close/dismissal lifecycle, followed by direct launches of the runtimes that are present on the test device.
