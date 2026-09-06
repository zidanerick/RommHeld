# DS Flashcard / R4 Target

`docs/DS_RUNTIME.md` is the authoritative DS/DSi runtime-readiness model. This file keeps the flashcart-specific fixture evidence and cautions that are useful when validating that model.

RommHeld treats a DS flashcart as a removable-storage target, not as a generic 3DS SD-card target. It must not infer an exact cart model from filesystem names alone.

## Observed test card

The supplied filesystem contains multiple boot/kernel components, so the exact physical R4 model is deliberately not asserted from storage evidence alone.

Observed markers include:

- `R4.dat`
- `TTMenu.dat`
- `TTMenu/`
- `YSMenu.nds`
- `YSMENU.ARP`
- `_nds/`
- `_nds/nds-bootstrap`
- `_nds/TWiLightMenu/`
- `_nds/GBARunner2_arm7dldi_3ds.nds`
- `_nds/GBARunner2_arm7dldi_dsi.nds`
- `_nds/GBARunner2_arm7dldi_ds.nds`
- `roms/nds/`
- `roms/gba/`
- `roms/dsi/`
- `Games/`

The observed `_nds/nds-bootstrap` path is retained here as fixture evidence only. It is not treated as proof of a current nds-bootstrap installation. Current upstream nds-bootstrap release instructions place versioned `.nds` and `.ver` files directly under `/_nds/`, and the DS health scanner checks that current layout.

## Flashcart readiness model

The DS runtime scanner reports capabilities and evidence instead of guessing hardware identity:

- TWiLight Menu++ runtime assets;
- current-layout nds-bootstrap runtime/version evidence;
- root `BOOT.NDS` or documented `BOOT_ALT.NDS` launcher evidence;
- NDS ROM and sibling save directories;
- conservative YSMenu/TTMenu, Wood/RPG and common R4 boot markers;
- readable TWiLight configuration state;
- missing, partial or dated/outdated runtime evidence where the evidence is reliable.

Current TWiLight Menu++ flashcart installation guidance uses `_nds`, `BOOT.NDS` and `roms` at the flashcart root. `BOOT_ALT.NDS` is documented for specific DSi-capable flashcarts. Autoboot/kernel files remain cart-specific and must be selected for the exact hardware from the maintained upstream instructions.

Do not generalise compatibility from an `R4` label or a familiar filename. Exact cart model/revision and a successful launch/save/relaunch cycle remain physical-device evidence.
