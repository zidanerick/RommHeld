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
    cgb_flag = payload[0x143]
    is_colour = cgb_flag in (0x80, 0xC0)
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
    """Validate classic donor family before any runtime is cached."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    previous = vc.extract_classic_vc_runtime

    def extract_classic_vc_runtime(donor_cia, boot9, family: str):
        validate_classic_donor_family(donor_cia, boot9, family, vc)
        return previous(donor_cia, boot9, family)

    vc.extract_classic_vc_runtime = extract_classic_vc_runtime
    _INSTALLED = True
