# RommHeld Nintendo 3DS / DS Capability Matrix

This document records the current implementation direction for Nintendo 3DS and DS targets. It separates storage, transport, frontend, runtime, packaging, device readiness, and RetroAchievements capability so RommHeld does not make emulator choices from file extensions alone.

## 3DS console SD

### GBA

- Preferred direct native route: `open_agb_firm`.
- `open_agb_firm` runs GBA games using the 3DS built-in GBA hardware and can launch `.gba` files directly from SD.
- It is a native-hardware route, not a conventional emulator, and is separate from both RetroArch and HOME Menu CIA packaging.
- RommHeld exposes `open_agb_firm` as a direct-ROM deployment target with the conventional destination `/roms/gba/<filename>`.
- RommHeld retains the separate `native_gba` target for generated HOME Menu GBA CIAs that execute through AGB_FIRM.
- Storage evidence observed on the test card includes `/luma/payloads/open_agb_firm.firm`.
- RetroArch remains a separate route when RetroAchievements support is the priority. The current 3DS bundle includes mGBA, which is the audited achievement-capable GBA core recommendation.
- mGBA's official GBA BIOS is optional. RommHeld must not claim a missing `gba_bios.bin` blocks ordinary mGBA use.

RommHeld also has a conservative open_agb_firm configuration adapter for the current upstream `config.ini` format. It edits only documented settings, preserves unknown keys/comments, backs up before replacement, and refuses legacy/unknown formats rather than migrating them blindly.

### NDS

- Preferred compatibility route: TWiLight Menu++ + `nds-bootstrap` where supported.
- TWiLight Menu++ is the frontend/launcher and `nds-bootstrap` is the loader. They are separate components of one RommHeld NDS route.
- RommHeld exposes the target key `twilight` and uses `/roms/nds/<filename>` as the conventional 3DS SD destination.
- TWiLight is a multi-file runtime and is not directly installed or updated by RommHeld. Prefer Universal-Updater or the maintained upstream installation process.
- A standalone `BOOT.NDS` is not sufficient installation evidence because unrelated DS homebrew can use the same filename.
- For the RommHeld NDS route, readiness requires both `_nds/TWiLightMenu` and `_nds/nds-bootstrap`. A partial tree is reported as incomplete rather than ready.
- RetroAchievements for native DS execution remains experimental/research territory and must not be presented as a guaranteed capability.

### Virtual Boy

- Preferred compatibility/native-style 3DS route: Red Viper.
- Red Viper is a dedicated 3DS Virtual Boy emulator and supports the console's stereoscopic 3D display path.
- RommHeld exposes `red_viper` and RetroArch as separate Virtual Boy targets while keeping `red_viper` as the normal compatibility and native preference.
- The current official 3DS RetroArch recipe builds `mednafen_vb`, the Beetle VB core. RommHeld therefore exposes RetroArch as a real alternate route rather than treating Virtual Boy as dedicated-only.
- RetroAchievements currently supports Beetle VB, so the 3DS `retroachievements` preference selects the RetroArch route for Virtual Boy.
- Both routes use `/roms/virtualboy/<filename>` as RommHeld's conventional content destination; changing runtime must not change transport semantics.
- That ROM directory is content evidence only. It must not prove that Red Viper, RetroArch, or the Beetle VB core is installed.
- Red Viper's single-file 3DSX release is eligible for controlled mounted-SD staging. A CIA-installed copy can exist without a detectable SD-side application marker, so absence is reported as needing on-console confirmation rather than definite absence.
- RetroArch readiness checks specifically for `mednafen_vb_libretro.3dsx` or CIA package evidence instead of accepting a generic RetroArch directory as proof that the Virtual Boy route is usable.
- DSP firmware remains a recommended troubleshooting prerequisite for the Red Viper route and must be generated from the user's own console.
- Red Viper configuration remains owned by the emulator itself for now.
- Beetle VB performance, input behavior, audio, save behavior, and RetroAchievements operation on real 3DS hardware remain unvalidated. Exposing the route is not a hardware-performance claim.

### N64

- Preferred and currently exposed route is `daedalusx64`.
- The current official 3DS RetroArch buildbot does **not** publish Mupen64Plus-Next, ParaLLEl N64, or another audited N64 core. RommHeld therefore does not expose a RetroArch N64 target merely because RetroArch supports N64 on other hosts.
- N64 remains visible in the 3DS RomM library because DaedalusX64 is a dedicated supported target.
- DaedalusX64's documented 3DS content directory is `/3ds/DaedalusX64/Roms/`.
- The content directory is not installation evidence because RommHeld can create it while transferring a ROM. SD detection instead looks for the actual homebrew executable where possible and otherwise treats a CIA-installed copy as needing on-console confirmation.
- DaedalusX64's current upstream 3DS release recommends current Luma plus dumped DSP firmware when game launch freezes, so DSP firmware is a readiness recommendation for this route.
- DaedalusX64 is a multi-file/runtime package and is not directly staged by RommHeld.
- Game compatibility remains title-specific and requires real-device validation.

### SNES

- RommHeld exposes both Nintendo VC packaging and RetroArch as ordinary runtime choices where appropriate.
- The current official 3DS RetroArch recipe builds `snes9x2002`, `snes9x2005`, `snes9x2005_plus`, `snes9x2010`, and `chimerasnes`, but not current mainline Snes9x.
- RetroAchievements currently lists the older Snes9x 2002/2005/2005+/2010 variants as unsupported/problematic for achievements. Therefore `retroachievements` preference does **not** recommend RetroArch for SNES on 3DS today.
- ChimeraSNES is retained as current core evidence, but RommHeld does not promote it to an achievement-capable recommendation without independent RetroAchievements support evidence.
- When the Nintendo VC route is available, SNES `retroachievements` preference currently falls back to `vc_cia` rather than claiming achievements will work through an unsuitable RetroArch core.
- This is intentionally capability-driven and should be revisited if the official 3DS core bundle changes.

### NES / Famicom / FDS

- The current 3DS RetroArch bundle includes FCEUmm and QuickNES. FCEUmm is the conservative common route for NES/Famicom/FDS and exposes achievement memory monitoring.
- Famicom Disk System use through FCEUmm requires the user-provided `disksys.rom` BIOS.
- RommHeld never downloads copyrighted BIOS data. When RetroArch's configured `system_directory` is explicit, readiness can check for `disksys.rom`; if the directory is `default` or otherwise not knowable, firmware is reported as unverified instead of assumed present or absent.
- Nintendo VC CIA generation remains a separate route for families RommHeld explicitly implements.

### Game Boy / Game Boy Color

- Current 3DS RetroArch builds include Gambatte and mGBA, both valid candidates for GB/GBC content.
- The official boot ROMs used by these cores are optional for ordinary emulation, so RommHeld does not require them for readiness.
- Nintendo VC CIA generation remains a separate route.

### Sega 8/16-bit and Sega CD

- Current official 3DS RetroArch recipe candidates include Genesis Plus GX, PicoDrive, SMS Plus GX, and ClownMDEmu depending on platform.
- Game Gear, Master System, Genesis/Mega Drive, 32X, and Sega/Mega CD can therefore use platform-specific RetroArch routes where the matching current 3DS core is available.
- Historical/generic core metadata is not enough to expose a route. For example, Gearsystem is not treated as current 3DS core evidence when it is absent from the current official 3DS recipe.
- Sega/Mega CD requires a user-provided BIOS matching the game's region. For Genesis Plus GX the documented names include `bios_CD_U.bin`, `bios_CD_E.bin`, and `bios_CD_J.bin`.
- As with FDS, RommHeld checks required BIOS only when the configured RetroArch System/BIOS directory is explicit. It never downloads BIOS files.

### Other RetroArch systems

- A platform being supported by RetroArch in general is not enough to make it a RommHeld 3DS recommendation.
- RommHeld may expose a general RetroArch route only where a current official 3DS core recipe entry exists; RetroAchievements preference is narrower again and requires an audited achievement-capable core.
- The runtime profile set is regression-tested against the exposed RetroArch platform set so a new target cannot silently appear without an evidence profile.
- Amiga and the ScummVM libretro core are not exposed as 3DS RetroArch routes because they are absent from the current official 3DS core recipe. A separate standalone 3DS application route, if added later, must use its own runtime and deployment model rather than masquerading as RetroArch.
- Arcade remains core-specific because compatibility and achievement support vary materially by core.

## Runtime preference policy

`preferred_target_key()` applies the 3DS device preference without inventing unsupported routes:

- `compatibility`: dedicated/native route where modelled, otherwise a supported current 3DS RetroArch route;
- `retroachievements`: RetroArch only for the audited current 3DS achievement-capable platform set, otherwise a dedicated/native or Nintendo VC fallback;
- `native`: dedicated/native route where modelled, then Nintendo VC CIA for supported classic families, then a supported fallback.

Current compatibility defaults are:

| RomM platform | Preferred target |
| --- | --- |
| GBA | `open_agb_firm` |
| NDS | `twilight` |
| Virtual Boy | `red_viper` |
| N64 | `daedalusx64` |
| Nintendo 3DS | `native_3ds_cia` |

Current conservative RetroAchievements-to-RetroArch recommendations include GBA, GB/GBC, NES/Famicom/FDS, Game Gear, Master System, Genesis/Mega Drive, 32X, Sega/Mega CD, and Virtual Boy through Beetle VB. SNES and N64 are deliberately excluded for the current 3DS core bundle.

Per-title target selection remains available where multiple routes are exposed. For Virtual Boy, selecting `retroachievements` chooses RetroArch while compatibility/native preferences continue to choose Red Viper.

## 3DS RetroAchievements policy

RetroAchievements capability is a property of the runtime/core, not the frontend.

For each target RommHeld should be able to represent:

- `ra_support`: none / experimental / softcore / hardcore / unverified
- `runtime_type`: native / emulator / hybrid
- `frontend`: e.g. RetroArch or TWiLight Menu++
- `core_or_loader`: e.g. mGBA, FCEUmm, Beetle VB, Genesis Plus GX, or nds-bootstrap
- `storage_profile`
- `recommended_route`

RetroArch achievements depend on the installed core, RetroAchievements integration, account configuration, and game support. A global RetroAchievements preference therefore selects only audited routes and never implies that every game or every core on a platform is guaranteed to work.

## Runtime evidence model

`three_ds_runtime_details.py` provides a pure backend evidence layer for runtime checks.

For RetroArch it distinguishes:

- frontend not detected;
- current platform profile not audited;
- matching core package only in `Cores-Notused`;
- no SD-visible core package, requiring on-console confirmation because a CIA core may already be installed;
- `.cia` package evidence, which is **not** treated as proof that the core title is installed;
- `.3dsx` core executable evidence;
- required firmware missing when an explicit System/BIOS directory can be checked;
- required firmware unverified when RetroArch's System/BIOS directory cannot be resolved safely.

Core scanning respects an explicit `libretro_directory` in `retroarch.cfg`; otherwise it uses the documented 3DS bundle location `/RetroArch/Cores`. The optional `Cores-Notused` convention is treated as inactive rather than ready.

The audited profile inventory covers every RetroArch platform RommHeld currently exposes on 3DS, including the dedicated-plus-RetroArch Virtual Boy case. Core existence in the official 3DS recipe establishes route availability, while RetroAchievements recommendation remains a separately audited property.

For TWiLight the detail scanner separately records TWiLight assets, nds-bootstrap, and `BOOT.NDS`, while readiness requires the first two together.

## 3DS readiness and homebrew management

RommHeld separates **required**, **recommended**, and **optional** 3DS components.

Readiness is evaluated from SD-side evidence conservatively:

- `ready`: all required components have sufficient evidence;
- `needs_confirmation`: a required application is not visible from SD markers but may exist as an installed CIA title;
- `missing_required`: a required component with reliable filesystem evidence is absent or incomplete.

Core inventory includes:

- Luma3DS
- Homebrew Launcher environment
- FBI
- ftpd
- Universal-Updater
- GodMode9
- console-generated DSP firmware
- open_agb_firm
- TWiLight Menu++ / nds-bootstrap
- RetroArch
- Red Viper
- DaedalusX64
- Checkpoint

A generic `/3ds` directory is not Homebrew Launcher proof, a ROM directory is not emulator proof, and a partial TWiLight tree is not a ready NDS runtime.

RommHeld does **not** treat every useful homebrew application as mandatory. Universal-Updater, GodMode9, and Checkpoint are generally recommendations unless a specific workflow requires them.

### Direct staging boundary

RommHeld is not a general 3DS app store. Mounted-SD automatic staging is currently limited to simple, auditable single-file 3DSX packages:

- `ftpd.3dsx`
- `Universal-Updater.3dsx`
- `red-viper.3dsx`

For these packages RommHeld:

1. resolves the exact asset from the latest stable upstream GitHub release;
2. rejects unexpected download hosts or package sizes;
3. verifies the upstream asset size;
4. verifies SHA-256 when the GitHub release publishes a digest;
5. requires a high-confidence 3DS SD-card root before writing;
6. backs up an existing target before replacement;
7. stages through a temporary file and atomically replaces the target;
8. supports cancellation while downloading.

Complex or system-sensitive packages such as Luma3DS, TWiLight Menu++, RetroArch, DaedalusX64, GodMode9, and CFW/bootstrap components remain delegated to Universal-Updater or their maintained upstream procedures.

Console-specific DSP firmware must be generated from the user's own console and is never downloaded by RommHeld.

## DS / R4 flashcard

The observed test flashcard contains:

- `R4.dat`
- `TTMenu.dat`
- `YSMenu.nds`
- `TTMenu/`
- `YSMENU.ARP`
- `_nds/nds-bootstrap`
- `_nds/TWiLightMenu`
- multiple GBARunner2 builds
- `roms/nds/`
- `roms/gba/`
- `roms/dsi/`

This is enough to classify the storage as a feature-rich DS flashcard environment, but not enough to identify the exact physical R4 hardware revision.

TWiLight Menu++ documentation states that flashcards use `_nds`, `BOOT.NDS`, and `roms`, and supports multiple loaders including nds-bootstrap, a flashcard kernel, and Pico Loader depending on the card.

RommHeld should therefore expose:

- NDS target: `roms/nds/`
- GBA target: `roms/gba/`
- DSi target: `roms/dsi/`
- loader capability: nds-bootstrap / kernel / Pico Loader when detectable

It should not label the card as a specific R4 model unless additional hardware-specific evidence is available.

## 3DS SD storage validation signatures

Strong CFW indicators observed on the test card:

- `/boot.firm`
- `/boot.3dsx`
- `/luma/`
- `/luma/config.ini`
- `/gm9/`
- `/config/`

Useful optional capability indicators observed:

- `/luma/payloads/open_agb_firm.firm`
- `/_nds/TWiLightMenu/` together with `/_nds/nds-bootstrap/`
- `/RetroArch/`

ROM/content directories such as `/roms/nds/`, `/roms/gba/`, `/roms/virtualboy/`, or `/3ds/DaedalusX64/Roms/` are destination/content evidence only. They must not prove the corresponding runtime is installed.

Validation must be read-only and confidence-based. The presence or absence of any single generic directory must not be treated as universal proof of a device state.

## File and target model

The implementation is converging on:

```text
Device
  -> Transport
      -> Mounted filesystem / FTP / USB filesystem
  -> Storage profile
      -> 3DS SD / DS flashcard / Vita ux0 / future
  -> Readiness
      -> required / recommended / optional applications
      -> detected / confirm-on-console / missing
      -> runtime/core/firmware evidence
  -> Runtime
      -> open_agb_firm / TWiLight / RetroArch / Red Viper / DaedalusX64 / etc.
  -> Capability
      -> native / emulated / RA support / stereoscopic 3D
  -> Platform mapping
      -> RomM platform -> destination path + route
  -> Optional runtime configuration adapter
      -> version-aware, narrow, backed-up writes only
```

## Validation status

Unit-tested/backend implemented:

- dedicated 3DS target exposure and destination mapping;
- persisted runtime preference policy;
- conservative RetroAchievements route gating;
- current official 3DS RetroArch recipe gating and one-to-one exposed-target/core-profile coverage;
- dual Virtual Boy routing with Red Viper as compatibility/native default and Beetle VB/RetroArch for the audited RetroAchievements preference;
- RomM inclusion of dedicated-runtime platforms such as NDS and N64 without inventing unavailable RetroArch targets;
- conservative runtime/homebrew marker detection;
- coherent TWiLight/nds-bootstrap detection;
- RetroArch core-package/executable and required-firmware evidence scanning;
- required/recommended readiness evaluation;
- open_agb_firm current-format configuration editing and backup semantics;
- controlled single-file 3DSX staging rules, verification, backup, and cancellation.

Desktop GUI validation still required:

- `ThreeDSReadinessDialog` rendering and worker lifecycle;
- `OpenAgbSettingsDialog` rendering and save flow;
- 3DS Device/Setup readiness presentation with the tightened evidence rules;
- Settings persistence and the 3DS RetroAchievements preference control;
- 3DS Manager default target selection after preference changes, including Red Viper versus RetroArch on Virtual Boy.

Real-device validation still required:

- direct open_agb_firm ROM transfer, launch, save and relaunch;
- TWiLight NDS transfer, launch, save and relaunch;
- Red Viper staging/launch/3D/save behavior;
- Virtual Boy RetroArch/Beetle VB launch, performance, input, audio, save behavior and RetroAchievements operation on real 3DS hardware;
- DaedalusX64 destination and selected-title launch behavior, including DSP-firmware troubleshooting path;
- RetroArch content path/core behavior and RetroAchievements preference behavior on audited current cores;
- FDS and Sega CD required-BIOS handling with user-owned BIOS files;
- staged ftpd and Universal-Updater 3DSX launch;
- existing FTP/FBI lifecycle regressions;
- outstanding Virtual Console NES, Game Gear, and SNES hardware checks.

N64 game compatibility, arcade/core selection, DS RetroAchievements, exact flashcard identification, and title-specific emulator exceptions remain capability/research areas rather than universal fixed mappings.
