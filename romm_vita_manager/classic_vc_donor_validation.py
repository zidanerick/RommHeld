from __future__ import annotations


_INSTALLED = False


def _classic_donor_rom_payload(donor_cia, boot9, vc) -> tuple[str, bytes]:
    donor = vc.read_asset(donor_cia)
    keys = vc.read_asset(boot9)
    ncch = vc._primary_ncch_from_cia(donor)
    _, _, _, _, _, ncch_format, _, _ = vc._require_classic_vc_tools()
    info = ncch_format.parse(ncch)
    if info.romfs is None:
        raise ValueError("Classic Virtual Console donor has no RomFS runtime.")
    romfs = vc._decrypt_region(
        ncch,
        info,
        info.romfs,
        keys,
        ncch_format.SECTION_ROMFS,
        extra=True,
    )
    files = vc.parse_romfs_files(romfs)
    candidates = sorted(path for path in files if path.casefold().startswith("/rom/"))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one classic Virtual Console ROM payload, found {len(candidates)}."
        )
    path = candidates[0]
    return path, files[path]


def _is_colour_gameboy(payload: bytes) -> bool:
    return len(payload) > 0x143 and payload[0x143] in (0x80, 0xC0)


def validate_gameboy_target_rom(payload: bytes, family: str) -> bytes:
    """Validate a GB/GBC target before it is inserted into a donor runtime.

    File extensions and RomM platform labels are useful routing hints, but the
    cartridge header is the launch-time contract. Validate the CGB flag and the
    standard header checksum so a mislabeled or truncated ROM is rejected on
    the PC instead of producing a CIA that fails only after installation.
    """
    key = family.strip().lower()
    if key not in {"gb", "gbc"}:
        return payload
    data = bytes(payload)
    if len(data) <= 0x14D:
        raise ValueError(
            f"{key.upper()} Virtual Console injection requires a ROM with a complete Game Boy cartridge header."
        )

    is_colour = _is_colour_gameboy(data)
    if key == "gbc" and not is_colour:
        raise ValueError(
            "Target ROM is a monochrome Game Boy cartridge, not a Game Boy Color cartridge. Use the Game Boy target."
        )
    if key == "gb" and is_colour:
        raise ValueError(
            "Target ROM declares Game Boy Color compatibility. Use the Game Boy Color target."
        )

    checksum = 0
    for value in data[0x134:0x14D]:
        checksum = (checksum - value - 1) & 0xFF
    if checksum != data[0x14D]:
        raise ValueError(
            "Game Boy cartridge header checksum is invalid. The ROM may be corrupted, truncated, or incorrectly patched."
        )
    return data


def validate_classic_donor_family(donor_cia, boot9, family: str, vc) -> None:
    """Reject a retail donor whose embedded runtime belongs to another family.

    Product/title naming is not enough to identify a 3DS VC family reliably.
    RommHeld therefore checks the payload convention the Nintendo runtime
    actually consumes before caching it. This prevents, for example, a GB
    PAC-MAN CIA from being accepted as an NES donor merely because both are
    Virtual Console titles.
    """
    key = family.strip().lower()
    if key not in {"gb", "gbc", "nes"}:
        return

    rom_path, payload = _classic_donor_rom_payload(donor_cia, boot9, vc)
    if key == "nes":
        if len(payload) < 16 or payload[:4] != b"TNES":
            raise ValueError(
                "Selected NES donor is not a Nintendo TNES runtime. Choose an official NES Virtual Console CIA."
            )
        return

    if payload[:4] == b"TNES":
        raise ValueError(
            f"Selected {key.upper()} donor is actually an NES/TNES Virtual Console title."
        )
    if len(payload) <= 0x143:
        raise ValueError(
            f"Selected {key.upper()} donor ROM is too small to contain a valid Game Boy cartridge header."
        )

    # Cartridge header byte 0x143 is the CGB compatibility flag. 0x80 means
    # colour-enhanced/backward-compatible and 0xC0 means CGB-only. Nintendo's
    # GBC VC donors use one of those values; ordinary monochrome GB donors do
    # not. The check uses the donor's original ROM only and never caches it.
    is_colour = _is_colour_gameboy(payload)
    if key == "gbc" and not is_colour:
        raise ValueError(
            "Selected Game Boy Color donor contains a monochrome Game Boy ROM. Choose an official GBC VC CIA."
        )
    if key == "gb" and is_colour:
        raise ValueError(
            "Selected Game Boy donor contains a Game Boy Color ROM. Choose an official GB VC CIA."
        )

    if not rom_path.startswith("/rom/"):
        raise ValueError("Classic Virtual Console donor uses an unexpected ROM path.")


def install() -> None:
    """Validate classic donor families and GB/GBC target ROMs."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    previous_extract = vc.extract_classic_vc_runtime
    previous_prepare = vc.prepare_classic_rom

    def extract_classic_vc_runtime(donor_cia, boot9, family: str):
        validate_classic_donor_family(donor_cia, boot9, family, vc)
        return previous_extract(donor_cia, boot9, family)

    def prepare_classic_rom(data: bytes, family: str) -> bytes:
        prepared = previous_prepare(data, family)
        return validate_gameboy_target_rom(prepared, family)

    vc.extract_classic_vc_runtime = extract_classic_vc_runtime
    vc.prepare_classic_rom = prepare_classic_rom
    _INSTALLED = True
