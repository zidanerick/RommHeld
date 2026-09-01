# DS Flashcard / R4 Target

RommHeld treats a DS flashcard as a removable-storage target, not as a generic 3DS SD-card target.

## Observed test card

The supplied filesystem contains multiple boot/kernel components, so the exact physical R4 model is not asserted from filesystem names alone.

Observed markers include:

- `R4.dat`
- `TTMenu.dat`
- `TTMenu/`
- `YSMenu.nds`
- `YSMENU.ARP`
- `_nds/`
- `_nds/nds-bootstrap`
- `_nds/TWiLightMenu`
- `_nds/GBARunner2_arm7dldi_3ds.nds`
- `_nds/GBARunner2_arm7dldi_dsi.nds`
- `_nds/GBARunner2_arm7dldi_ds.nds`
- `roms/nds/`
- `roms/gba/`
- `roms/dsi/`
- `Games/`

## Target model

A future DS flashcard target profile should expose capabilities rather than guess a hardware model:

- NDS ROM storage: `roms/nds/`
- GBA content: `roms/gba/`
- DSi content: `roms/dsi/`
- TWiLight Menu++ present
- nds-bootstrap present
- GBARunner2 present
- YSMenu / TTMenu components present

TWiLight Menu++ documentation confirms the flashcard installation model uses `_nds`, `BOOT.NDS`, and `roms`, and can select either the flashcard kernel or nds-bootstrap as the game loader. It also documents switching between console-SD and flashcard contents on compatible 3DS setups.

Do not infer the exact flashcard hardware from these files alone. Prefer an explicit user-selected flashcard profile when required.
