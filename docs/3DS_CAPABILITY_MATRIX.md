# RommHeld Nintendo 3DS / DS Capability Matrix

This document records the current implementation direction for Nintendo 3DS and DS targets. It separates storage, transport, frontend, runtime, and RetroAchievements capability so RommHeld does not make emulator choices from file extensions alone.

## 3DS console SD

### GBA

- Preferred native route: `open_agb_firm`.
- `open_agb_firm` runs GBA games using the 3DS built-in GBA hardware and can launch `.gba` files directly from SD.
- It is a native-hardware route, not a conventional emulator, and should be treated separately from RetroArch.
- Storage evidence observed on the user's test card includes `/luma/payloads/open_agb_firm.firm`.
- Official 3DS Virtual Console titles are a separate title-specific route. Do not assume every GBA ROM has a matching VC release.
- RetroArch remains a separate route when RetroAchievements support is the priority.

Sources: official `open_agb_firm` repository and RetroAchievements emulator support documentation.

### NDS

- Preferred compatibility route: TWiLight Menu++ + `nds-bootstrap` where supported.
- TWiLight Menu++ is a frontend/launcher and `nds-bootstrap` is the loader. They must not be modelled as the same component.
- 3DS SD installations use a `roms` tree for game storage.
- RetroAchievements for native DS execution should currently be considered unavailable/experimental in RommHeld. The historical `nds-bootstrap` RetroAchievements request was closed as not planned.
- Recent community work indicates native-3DS DS achievement experiments exist, so this should remain a research item rather than a hard-coded unsupported state.

### Virtual Boy

- Preferred native 3DS route: Red Viper.
- Red Viper is a dedicated 3DS Virtual Boy emulator and supports the console's stereoscopic 3D display path.
- Recent RetroAchievements community work reports softcore achievement unlocking in Red Viper, with hardcore support under evaluation.
- RommHeld should therefore model Red Viper as both a runtime and a potential RA-capable route, with hardcore compatibility tracked separately from softcore.

### N64

- Preferred compatibility route currently remains a choice between DaedalusX64 and RetroArch depending on game and achievement goals.
- Do not automatically map RomM `n64` to one emulator.
- Keep N64 target selection capability-based until the 3DS RetroAchievements/core situation is verified for the user's installed RetroArch build.

### SNES / NES / GB / GBC / Genesis / Mega Drive / arcade and similar systems

- RetroArch should be preferred when RetroAchievements is required and the relevant 3DS core is actually supported on the user's installation.
- Native or dedicated emulators should remain possible when they materially improve compatibility, performance, or device-specific features.
- RommHeld should record the recommended route rather than silently replacing a user-selected route.
- Arcade should remain core-specific because FBNeo provides RetroAchievements support, while not every arcade core has the same capabilities.

## 3DS RetroAchievements policy

RetroAchievements capability is a property of the runtime/core, not the frontend.

For each target RommHeld should be able to represent:

- `ra_support`: none / experimental / softcore / hardcore
- `runtime_type`: native / emulator / hybrid
- `frontend`: e.g. RetroArch or TWiLight Menu++
- `core_or_loader`: e.g. FBNeo or nds-bootstrap
- `storage_profile`
- `recommended_route`

RetroArch documentation confirms that achievements depend on the RetroAchievements integration and account configuration, and Hardcore mode disables emulation assists such as save states and fast-forward.

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

Validation must be read-only and confidence-based. The presence or absence of any single file must not be treated as universal proof of a device state.

## File and target model

The implementation should converge on:

```text
Device
  -> Transport
      -> Mounted filesystem / FTP / USB filesystem
  -> Storage profile
      -> 3DS SD / DS flashcard / Vita ux0 / future
  -> Runtime
      -> open_agb_firm / TWiLight / RetroArch / Red Viper / etc.
  -> Capability
      -> native / emulated / RA softcore / RA hardcore / 3D
  -> Platform mapping
      -> ROMM platform -> destination path + route
```

## Research status

Research is sufficient to implement the architecture and storage/profile model, but not yet sufficient to automatically select every best runtime. N64, arcade, DS RetroAchievements, Virtual Console matching, and exact flashcard identification remain capability/research areas rather than fixed universal mappings.
