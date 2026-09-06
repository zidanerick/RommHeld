# Nintendo DS / DSi runtime readiness

This document defines RommHeld's DS-owned runtime boundary. Nintendo DS deployment remains removable-storage first. FTP is not a DS prerequisite.

## Supported environment profiles

RommHeld models four environments rather than treating every selected card as a generic flashcart:

- `dsi-homebrew`: Nintendo DSi SD storage used with a homebrew/CFW environment.
- `ds-flashcart`: DS or DS Lite Slot-1 flashcart storage. Exact cart/revision remains unknown unless cart-specific filesystem evidence is present or the user explicitly identifies it.
- `3ds-hosted-twilight`: TWiLight Menu++ hosted on a Nintendo 3DS SD card. The DS scanner may recognise this only to avoid misclassification; readiness and repair are owned by the 3DS workflow.
- `generic-removable`: valid removable storage where the physical environment cannot be established reliably. A standard TWiLight root layout alone is deliberately left here because DSi and flashcart installs share `_nds`, `BOOT.NDS` and `roms`.

`detect_ds_profile()` accepts an explicit profile hint for callers that already know the physical target. Strong 3DS filesystem evidence still defers to the 3DS owner.

## Evidence and health vocabulary

`ds_runtime.py` keeps installation evidence separate from operational proof. It uses `verified`, `not_verified`, `needs_attention`, `missing` and `not_applicable`. Filesystem presence of a launcher/runtime is normally `not_verified`, not `verified`, because RommHeld has not observed an on-console launch.

The health report covers:

- selected storage existence/readability;
- TWiLight Menu++ assets at `/_nds/TWiLightMenu/`;
- current-layout nds-bootstrap `.nds` and `.ver` files directly under `/_nds/`;
- root `BOOT.NDS` and flashcart-specific `BOOT_ALT.NDS` evidence;
- DSi boot/CFW state, with Unlaunch explicitly requiring console confirmation because it is NAND-resident;
- conservative flashcart kernel evidence such as YSMenu + TTMenu, `__rpg`, R4/TTMenu boot markers and common `_DS_MENU` forms;
- `/roms/nds/` and `/roms/nds/saves/`;
- readable TWiLight `settings.ini` shape without interpreting undocumented application keys;
- dated known-version comparison for nds-bootstrap when a readable `.ver` marker supplies a version.

As of 2026-09-06, the upstream release baseline used for reliable comparison is TWiLight Menu++ `v27.24.1` and nds-bootstrap `v2.16.0`. The baseline is intentionally dated so RommHeld does not silently present a stale hard-coded version as permanently current.

## Upstream layout basis

Current DS-Homebrew installation guidance uses environment-specific TWiLight release archives. DSi installs place `_nds`, `BOOT.NDS` and `roms` at SD root. Flashcart installs use the same basic layout, with `BOOT_ALT.NDS` documented for specific DSi-capable flashcarts and cart-specific autoboot/kernel files handled separately. Current nds-bootstrap release instructions place its `.nds` and `.ver` files directly in `root:/_nds/`. Saves are kept in a `saves` directory beside the NDS ROM directory.

This means the old RommHeld marker `/_nds/nds-bootstrap` is not sufficient evidence for a current nds-bootstrap install, and the shared TWiLight root layout is not sufficient evidence to label the medium as a flashcart.

## Repair boundary

`ds_repair.py` automatically creates only the known content/save directories `/roms/nds/` and `/roms/nds/saves/`. That operation does not overwrite runtime files.

TWiLight Menu++, nds-bootstrap, root launchers, flashcart kernels and autoboot files are guided/manual repair. These are multi-file or hardware-specific runtimes and must be updated from the maintained environment-specific release/instructions rather than by copying isolated convenient files. A malformed TWiLight `settings.ini` is reported as a guided backup/regeneration case; RommHeld does not reconstruct undocumented keys.

DSi Unlaunch installation/update and other NAND/boot-chain changes are never automatic. They remain console-confirmed and guide-driven because SD contents cannot establish Unlaunch state and NAND writes carry a materially different risk boundary.

The DS repair layer refuses writes to a storage root identified as 3DS-hosted TWiLight, preventing overlap with the 3DS readiness owner.

## RomM metadata boundary

The existing canonical RomM platform slug `nds` and display label `Nintendo DS` are sufficient for DS library identification. DS deployment additionally needs the ROM filename/path, extension, title and stable game/platform identity already used by library selection. Runtime profile, flashcart model, DSi CFW state, destination path and save layout are device-side state and must not be inferred from RomM platform metadata.

DSiWare should not be silently conflated with ordinary `nds` cartridge deployment if RomM exposes a distinct platform/metadata record in a future provider revision. The Library & RomM owner should preserve any source platform identity so runtime routing can distinguish it when that support is implemented. No RomM provider changes are owned by this DS runtime work.

## Validation still requiring physical hardware

Synthetic filesystem tests can validate profile inference, partial/current-layout runtime evidence, version-marker handling, config health, safe directory creation and the 3DS ownership guard. They cannot validate console boot behavior.

Physical evidence required before claiming operational readiness:

- DSi: SD root listing from a known working TWiLight setup, whether Unlaunch is installed, its configured no-button/default boot target, whether hiyaCFW is used, successful TWiLight launch, successful known-good NDS launch/save/relaunch, and the resulting save path.
- DS/DS Lite flashcart: exact cart front/back label and hardware revision, SD root listing, stock/kernel name and version if displayed, whether TWiLight is launched manually or by autoboot, successful known-good NDS launch/save/relaunch, and the resulting save path.
- Any cart using YSMenu/kernel mode: exact cart model plus evidence that the documented kernel-mode handoff works. Filesystem markers alone are not enough to generalise compatibility across R4-labelled clones.
- 3DS-hosted TWiLight: no DS-agent validation request beyond enough filesystem evidence to recognise/defer the medium. Functional testing belongs to the 3DS owner.

Until those checks are performed, RommHeld must describe runtime files as present/not verified rather than working.
