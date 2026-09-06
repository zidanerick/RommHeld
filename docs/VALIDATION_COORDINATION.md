# Validation coordination

Status: validation-only coordination record

This document defines how RommHeld manual, integration, desktop and hardware validation is tracked across device/runtime work. It does not own device/runtime implementation, VC generation or UI fixes.

Coordinator baseline when this document was created: `b7f4e769eddcc7661f0f2931039cb8357f5f8164` on PR #21 (`refactor/apple-like-ui`). Every manual result is tied to the exact Git SHA that was actually tested. Results do not automatically carry forward when the branch advances.

Authoritative platform checklists remain:

- Nintendo 3DS transport/filesystem: `docs/3DS_TESTING.md`
- Nintendo 3DS health/file-manager behavior: `docs/FTP_FILE_MANAGER.md`
- PlayStation Vita/PSTV hardware: `docs/VITA_TESTING.md`
- PlayStation Vita runtime evidence: `docs/VITA_RUNTIME_HEALTH.md`
- Nintendo DS / DSi runtime readiness: `docs/DS_RUNTIME.md`
- 3DS VC/package validation: `docs/3DS_VIRTUAL_CONSOLE.md` and the 3DS VC & Packaging owner

This file coordinates validation across those sources. It must not replace their platform-specific technical contracts.

## 1. Validation-only boundary

The Validation Coordinator may:

- convert device-agent hardware requests into concise operator checklists;
- run or inspect automated tests and CI;
- record native desktop, mounted-storage, live-network and real-device results;
- classify what each observation actually proves;
- identify regressions and route them to the owning agent;
- add synthetic regression fixtures when a manual finding needs deterministic coverage and the change is strictly validation-owned.

The Validation Coordinator must not:

- broadly repair device/runtime defects;
- redesign transport, runtime or package architecture;
- implement competing health/readiness systems;
- modify VC generation to fix package defects;
- make UI-only fixes that belong to UI & Desktop UX;
- claim real-device validation from unit tests, filesystem evidence or successful package staging.

## 2. Result record contract

Every manual result must include all applicable fields:

| Field | Requirement |
| --- | --- |
| Test ID | Stable coordinator identifier |
| Platform/component | 3DS, Vita/PSTV, DS/DSi, app/runtime or transport |
| Validation category | AUT, INT, DESK, MNT, NET or DEV |
| Git SHA | Exact tested commit, mandatory |
| Environment | Device model, storage/transport mode and other non-sensitive reproduction context |
| Detection result | What RommHeld detected |
| Evidence classification | What RommHeld said the evidence means |
| Repair-plan result | Whether the proposed repair is appropriate |
| Repair execution | Whether a supported repair/preparation action completed |
| Post-repair rescan | Classification after repair/reconnect |
| Launch validation | Separate real-device launch/function result |
| Overall result | PASS, FAIL, BLOCKED or RETEST REQUIRED |
| Defect owner | Owning agent if failed |
| Notes | Minimal non-sensitive evidence needed to reproduce |

Historical PASS results remain valid only for their tested SHA. If relevant production behavior changes afterward, the newer SHA is `RETEST REQUIRED` until manually exercised again.

## 3. Validation categories

Keep these categories separate in all reports:

| Code | Category | Scope |
| --- | --- | --- |
| AUT | Automated unit/regression | Parsers, state logic, paths, deterministic failure handling, isolated/offscreen Qt contracts |
| INT | Integration tests | Multiple production modules/adapters working together against synthetic or controlled backends |
| DESK | Native desktop validation | Real compositor/window lifecycle, interaction, browser launch, focus/layout and close/cancel behavior |
| MNT | Mounted-storage validation | Real SD/VitaShell USB/removable media and actual filesystem behavior |
| NET | Live network/FTP validation | Real mtheall ftpd or VitaShell FTP over a live local network |
| DEV | Real-device launch validation | Application/runtime/game launch and functional behavior on physical hardware |

AUT or INT can never be reported as DESK, MNT, NET or DEV validation.

## 4. Health/readiness dimensions

For every health-managed platform/component, track these dimensions independently:

| Code | Dimension | Question |
| --- | --- | --- |
| D | Detection accuracy | Did RommHeld correctly detect or not detect the component/environment? |
| E | Evidence classification accuracy | Did it correctly state what the observed evidence proves? |
| P | Repair-plan accuracy | Is the proposed repair/recovery route correct for this exact state? |
| X | Repair execution | Did the supported preparation/repair operation safely complete? |
| R | Post-repair rescan | Did rescanning/reconnecting reflect the changed evidence correctly? |
| L | Application launch validation | Does the relevant app/runtime/game actually launch and perform the tested function? |
| B | Evidence boundary accuracy | Did filesystem/staging evidence remain distinct from installed/launchable/working state? |

A component is not fully validated merely because detection and evidence classification pass.

## 5. Evidence strength

Use conservative proof labels:

| Evidence | May prove | Must not be promoted to |
| --- | --- | --- |
| Filesystem marker | Relevant file/folder exists | Working installation |
| Runtime/data assets | Supporting runtime data exists | Launchable frontend |
| Staged VPK/CIA/3DSX | Package/file was staged | Installed application |
| 3DSX launch-surface marker | HBL executable exists | HOME Menu CIA installation |
| Luma payload marker | Payload file exists | Successful chainloader launch |
| Known installed-title evidence | Modeled installed title is visible | Successful application launch |
| Live service probe | That specific network service is operational | Other application/runtime functions |
| Manual app launch | Application launches on tested hardware | Game/runtime compatibility beyond the tested path |
| Functional workflow | Specific function succeeds | Unrelated features |
| Representative game launch | Tested runtime/title path works | Universal compatibility |

When evidence is weaker than the product wording, record an evidence-classification failure even if the underlying files are present.

## 6. Repair acceptance

Treat repair as three distinct acceptance points:

1. **Repair plan PASS**: the suggested remediation is technically appropriate.
2. **Repair execution PASS**: RommHeld or the documented manual step completed safely and produced the expected file/config state.
3. **Repair outcome PASS**: post-repair rescan is correct and, where required, real-device launch/function validation succeeds.

Example:

- FBI 3DSX staged: repair execution PASS.
- Rescan sees Homebrew Launcher evidence: rescan PASS.
- FBI CIA installed: not proven by staging.
- FBI launch: not tested until opened on-console.
- FBI Remote Install: not tested until that workflow succeeds on-console.

## 7. Existing Nintendo 3DS manual baseline

The prior manual regression pass is pinned to `01057aa4419281daea301bfa339a4845d6930587`, the tested head immediately preceding the manual-finding fix chain.

| Test | Category | Result at tested SHA | Current-head status |
| --- | --- | --- | --- |
| Mounted 3DS SD detection | MNT | PASS @ `01057aa4419281daea301bfa339a4845d6930587` | RETEST REQUIRED after later detection-threshold changes |
| Live ftpd browse | NET | PASS @ `01057aa4419281daea301bfa339a4845d6930587` | Historical PASS only |
| Live ftpd upload | NET | PASS @ `01057aa4419281daea301bfa339a4845d6930587` | Historical PASS only |
| Live ftpd delete | NET | PASS @ `01057aa4419281daea301bfa339a4845d6930587` | Historical PASS only |
| Live ftpd cancellation | NET | PASS @ `01057aa4419281daea301bfa339a4845d6930587` | Historical PASS only |

Do not rewrite these rows to a newer SHA without repeating the corresponding manual test.

## 8. Nintendo 3DS health/readiness matrix

### ftpd

Track:

- D: mounted/FTP evidence detection;
- E/B: installed evidence without live service remains launch-unverified;
- E: stopped/unreachable service with install evidence becomes needs-attention rather than missing;
- P: repair guidance directs the user to launch ftpd, verify current IP/port and LAN, then update/reinstall only where appropriate;
- X: verified mounted-SD ftpd 3DSX preparation;
- R: restart ftpd and confirm rescan changes to operationally verified;
- L: live ftpd connection is the operational validation for ftpd itself;
- NET: browse, upload, download, mutations, cancellation/retry and reconnect remain distinct transport tests.

### FBI, Universal-Updater, Red Viper and Checkpoint

For each component:

- verify installed-title, 3DSX or other evidence is classified by its actual launch surface;
- verify presence remains launch-unverified until on-console launch;
- verify direct preparation/updater/manual repair guidance is appropriate;
- execute supported preparation where applicable;
- rescan and verify staging does not fabricate CIA installation;
- launch the application on hardware;
- separately validate the relevant function: FBI Remote Install, Universal-Updater catalogue/update operation, Red Viper representative ROM launch, Checkpoint title/save enumeration.

### DaedalusX64, TWiLight Menu++/nds-bootstrap and RetroArch

For each runtime:

- distinguish frontend/install evidence from runtime/data/core assets;
- classify assets-only/partial state without claiming a working frontend;
- verify repair guidance uses the maintained full installation route rather than piecemeal convenient files;
- rescan after repair;
- launch the frontend on-console;
- launch a representative compatible title separately.

### open_agb_firm

- detect valid Luma payload evidence and reject invalid/zero-byte payload evidence;
- never label payload presence as HOME Menu installation;
- keep current repair guidance on the supported upstream/manual route while unverified updater archive behavior remains unsuitable;
- validate chainloader visibility with START boot;
- validate open_agb_firm launch;
- validate representative GBA game/config behavior separately.

### Luma3DS, Homebrew Launcher foundation, GodMode9 and DSP data

- preserve system-sensitive/manual or console-generated repair boundaries;
- validate observed filesystem evidence conservatively;
- never auto-promote presence to working;
- perform physical boot/launch/consumption checks where the component's behavior can only be proven on hardware.

## 9. Nintendo 3DS mounted-storage matrix

At minimum track:

- genuine card detection and configured-root persistence;
- rejection of generic ROM libraries as 3DS media;
- medium/high-confidence write threshold;
- boot/runtime marker classification;
- known installed-title versus 3DSX versus Luma payload versus assets-only evidence;
- zero-byte executable/payload rejection;
- direct preparation/staging execution;
- immediate post-stage rescan;
- safe replacement/cancellation/card-removal behavior;
- clean eject and console visibility;
- application/runtime launch after storage is returned to the console.

A successful staged copy is MNT evidence only. It is not DEV validation.

## 10. PlayStation Vita / PlayStation TV matrix

Follow `docs/VITA_RUNTIME_HEALTH.md` and `docs/VITA_TESTING.md`.

For VitaShell, RetroFlow, Adrenaline, RetroArch, RetroArch data/cores, DaedalusX64, Flycast, ScummVM, DSVita, FAKE-08, kubridge and libshacccg, track D/E/P/X/R/L/B independently where applicable.

Required evidence boundaries include:

- a staged VPK is staging evidence only;
- installed app files remain `Present · launch not verified` until real Vita launch evidence exists;
- RetroArch frontend, data and cores are separate evidence;
- DSVita app presence does not prove libshacccg/kubridge readiness or game launch;
- normal VitaShell USB inspection of ux0 does not prove ur0 state;
- FTP-only/PSTV must not fabricate USB capacity or install-state evidence;
- VitaShell FTP must not claim free-space reporting that the protocol does not provide;
- trusted hardware observations may promote or refine health only through sanitized evidence, never raw device dumps.

Physical Vita/PSTV validation remains separated into USB, live FTP and actual runtime/application launch results.

## 11. Nintendo DS / DSi matrix

Follow `docs/DS_RUNTIME.md` and keep environment profile explicit:

- `dsi-homebrew`
- `ds-flashcart`
- `3ds-hosted-twilight`
- `generic-removable`

Track storage, TWiLight Menu++ assets, current-layout nds-bootstrap files/version markers, root launcher state, DSi boot/CFW state, flashcart kernel/runtime evidence, ROM/save directories and TWiLight config health.

Required evidence boundaries:

- shared `_nds` / `BOOT.NDS` / `roms` layout does not by itself prove DSi versus flashcart environment;
- filesystem runtime presence is normally not launch-verified;
- Unlaunch is NAND-resident and requires console confirmation;
- flashcart compatibility must not be generalized from generic R4-like markers;
- `3ds-hosted-twilight` is recognised only to defer ownership to the 3DS workflow;
- safe automatic DS repair is currently limited to known content/save directory creation;
- TWiLight, nds-bootstrap, flashcart kernels, autoboot files and NAND/boot-chain changes remain guided/manual;
- known-good NDS launch, save and relaunch are DEV validation and must be recorded separately from storage evidence.

## 12. Hardware-request intake

When a device agent asks for hardware validation, produce a concise operator checklist containing:

1. exact Git SHA to test;
2. required hardware/storage/network setup;
3. exact actions to perform;
4. expected RommHeld detection and evidence classification;
5. repair/preparation action if part of the test;
6. required rescan/reconnect;
7. physical launch/function check where applicable;
8. cleanup/recovery step for mutating tests;
9. minimal result format to return: PASS/FAIL plus observed wording/error and non-sensitive evidence.

Record the returned result here or in the authoritative platform testing document without duplicating implementation work.

## 13. Defect routing

| Defect | Owner |
| --- | --- |
| 3DS detection/readiness/app health/mounted SD/ftpd/runtime | 3DS Device & Runtime |
| Vita USB/FTP/runtime health/setup/device behavior | Vita Device & Transport |
| DS/DSi environment/runtime/storage health | Nintendo DS / DSi Device & Runtime |
| GBA/GB/GBC/NES/GG/SNES VC generation, CIA structure/runtime metadata | 3DS VC & Packaging |
| UI-only rendering/layout/focus/hierarchy/native Qt presentation | UI & Desktop UX |
| Library-source/RomM normalization defect | Library Providers & RomM Integration |

When a failure crosses boundaries, create one primary defect against the likely root-cause owner and record dependent retests. Do not create parallel implementations or duplicate fixes.

## 14. Validation status language

Use only evidence-supported claims:

- `PASS @ <sha>`: exercised successfully at that exact SHA.
- `FAIL @ <sha>`: exercised and failed at that exact SHA.
- `BLOCKED @ <sha>`: could not execute due to an external prerequisite or unavailable hardware/environment.
- `RETEST REQUIRED`: an older PASS exists but relevant code changed afterward.
- `AUT covered`: automated coverage exists but no manual/hardware claim is implied.
- `Not tested`: no valid result exists for the requested layer.

Never replace `Not tested` with an assumption based on another validation category.
