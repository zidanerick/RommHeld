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
- RetroArch remains a separate route when RetroAchievements support is the priority and the installed core supports the title.

RommHeld also has a conservative open_agb_firm configuration adapter for the current upstream `config.ini` format. It edits only documented settings, preserves unknown keys/comments, backs up before replacement, and refuses legacy/unknown formats rather than migrating them blindly.

### NDS

- Preferred compatibility route: TWiLight Menu++ + `nds-bootstrap` where supported.
- TWiLight Menu++ is a frontend/launcher and `nds-bootstrap` is the loader. They must not be modelled as the same component.
- RommHeld exposes the target key `twilight` and uses `/roms/nds/<filename>` as the conventional 3DS SD destination.
- TWiLight is a multi-file runtime and is not directly installed or updated by RommHeld. Prefer Universal-Updater or the maintained upstream installation process.
- A standalone `BOOT.NDS` is not sufficient installation evidence because unrelated DS homebrew can use the same filename.
- RetroAchievements for native DS execution remains experimental/research territory and must not be presented as a guaranteed capability.

### Virtual Boy

- Preferred dedicated 3DS route: Red Viper.
- Red Viper is a dedicated 3DS Virtual Boy emulator and supports the console's stereoscopic 3D display path.
- RommHeld exposes the target key `red_viper` and currently uses `/roms/virtualboy/<filename>` as a conventional content destination.
- That ROM directory is a RommHeld convention, not Red Viper installation evidence. Red Viper can browse ROMs from other SD locations.
- Red Viper's single-file 3DSX release is eligible for controlled mounted-SD staging. A CIA-installed copy can exist without a detectable SD-side application marker, so absence is reported as needing on-console confirmation rather than definite absence.
- Red Viper configuration remains owned by the emulator itself for now.

### N64

- Preferred compatibility route is currently DaedalusX64, with RetroArch remaining an alternative when an installed core or RetroAchievements requirement justifies it.
- RommHeld exposes `daedalusx64` and `retroarch` as distinct target choices rather than automatically mapping RomM `n64` to one emulator.
- DaedalusX64's documented 3DS content directory is `/3ds/DaedalusX64/Roms/`.
- DaedalusX64 is a multi-file/runtime package and is not directly staged by RommHeld.
- Game compatibility remains title-specific and requires real-device validation.

### SNES / NES / GB / GBC / Genesis / Mega Drive / arcade and similar systems

- RetroArch should be preferred when RetroAchievements is required and the relevant 3DS core is actually supported on the user's installation.
- Nintendo Virtual Console CIA generation remains a separate route for families that RommHeld explicitly implements.
- Native or dedicated emulators should remain possible when they materially improve compatibility, performance, or device-specific features.
- RommHeld records/recommends a route rather than silently replacing a user-selected route.
- Arcade remains core-specific because achievement and compatibility capability varies by core.

## Runtime preference policy

`preferred_target_key()` now applies the 3DS device preference without inventing unsupported routes:

- `compatibility`: dedicated/native route where modelled, otherwise a supported RetroArch route;
- `retroachievements`: RetroArch only when that platform actually exposes a RetroArch target, otherwise the available dedicated route;
- `native`: dedicated/native route where modelled, then Nintendo VC CIA for supported classic families, then a supported fallback.

Current compatibility defaults are:

| RomM platform | Preferred target |
| --- | --- |
| GBA | `open_agb_firm` |
| NDS | `twilight` |
| Virtual Boy | `red_viper` |
| N64 | `daedalusx64` |
| Nintendo 3DS | `native_3ds_cia` |

Per-title target selection remains available where multiple routes are exposed.

## 3DS RetroAchievements policy

RetroAchievements capability is a property of the runtime/core, not the frontend.

For each target RommHeld should be able to represent:

- `ra_support`: none / experimental / softcore / hardcore
- `runtime_type`: native / emulator / hybrid
- `frontend`: e.g. RetroArch or TWiLight Menu++
- `core_or_loader`: e.g. FBNeo or nds-bootstrap
- `storage_profile`
- `recommended_route`

RetroArch achievements depend on the installed core, RetroAchievements integration, account configuration, and game support. A global RetroAchievements preference must therefore select only routes RommHeld actually exposes and must never imply that every core/title is supported.

## 3DS readiness and homebrew management

RommHeld now separates **required**, **recommended**, and **optional** 3DS components.

Readiness is evaluated from SD-side evidence conservatively:

- `ready`: all required components have sufficient evidence;
- `needs_confirmation`: a required application is not visible from SD markers but may exist as an installed CIA title;
- `missing_required`: a required component with reliable filesystem evidence is absent.

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
- `/roms/nds/`
- `/roms/gba/`
- `/roms/nes/`
- `/roms/snes/`
- `/roms/sms/`
- `/roms/ws/`
- `/roms/ngp/`

Validation must be read-only and confidence-based. The presence or absence of any single file must not be treated as universal proof of a device state. Content directories must not be treated as proof that the corresponding emulator is installed.

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
  -> Runtime
      -> open_agb_firm / TWiLight / RetroArch / Red Viper / DaedalusX64 / etc.
  -> Capability
      -> native / emulated / RA softcore / RA hardcore / 3D
  -> Platform mapping
      -> RomM platform -> destination path + route
  -> Optional runtime configuration adapter
      -> version-aware, narrow, backed-up writes only
```

## Validation status

Unit-tested/backend implemented:

- dedicated 3DS target exposure and destination mapping;
- runtime preference policy;
- RomM inclusion of dedicated-runtime platforms such as NDS;
- conservative runtime/homebrew marker detection;
- required/recommended readiness evaluation;
- open_agb_firm current-format configuration editing and backup semantics;
- controlled single-file 3DSX staging rules, verification, backup, and cancellation.

Desktop GUI validation still required:

- `ThreeDSReadinessDialog` rendering and worker lifecycle;
- `OpenAgbSettingsDialog` rendering and save flow;
- final integration of readiness controls into the active 3DS Device/Setup workflow;
- final integration of `preferred_target_key()` into every UI path that currently chooses a default target.

Real-device validation still required:

- direct open_agb_firm ROM transfer, launch, save and relaunch;
- TWiLight NDS transfer, launch, save and relaunch;
- Red Viper staging/launch/3D/save behavior;
- DaedalusX64 destination and selected-title launch behavior;
- RetroArch content path/core behavior and RetroAchievements preference behavior;
- staged ftpd and Universal-Updater 3DSX launch;
- existing FTP/FBI lifecycle regressions;
- outstanding Virtual Console NES, Game Gear, and SNES hardware checks.

N64 compatibility, arcade/core selection, DS RetroAchievements, exact flashcard identification, and title-specific emulator exceptions remain capability/research areas rather than universal fixed mappings.
