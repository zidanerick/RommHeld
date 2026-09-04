from __future__ import annotations


# TNES uses its own compact mapper numbering. Mapping is the inverse of the
# long-public TNES->iNES conversion table and covers the mapper families used by
# Nintendo's 3DS NES VC emulator.
_TNES_MAPPER_BY_INES = {
    0: 0,   # NROM
    1: 1,   # SxROM / MMC1
    9: 2,   # PNROM / MMC2
    4: 3,   # TxROM / MMC3
    10: 4,  # FxROM / MMC4
    5: 5,   # ExROM / MMC5
    2: 6,   # UxROM
    3: 7,   # CNROM
    7: 8,   # AxROM
}


def _nes2_rom_units(header: bytes, *, prg: bool) -> int:
    """Return NES 2.0 ROM size in the legacy unit used by TNES.

    TNES can express PRG in 8 KiB units and CHR in 8 KiB units. The ordinary
    NES 2.0 linear-size form maps exactly. The exponent/multiplier form is
    deliberately rejected instead of guessing because Nintendo's TNES header
    has no equivalent representation.
    """
    lsb = header[4] if prg else header[5]
    upper = (header[9] & 0x0F) if prg else (header[9] >> 4)
    if upper == 0x0F:
        kind = "PRG" if prg else "CHR"
        raise ValueError(
            f"NES 2.0 {kind} exponent/multiplier sizing cannot be represented safely as TNES."
        )
    legacy_units = (upper << 8) | lsb
    return legacy_units * (2 if prg else 1)


def ines_to_tnes(rom: bytes) -> bytes:
    """Convert an iNES/NES 2.0 ROM into the 16-byte TNES format used by 3DS VC.

    Only mapper families represented by Nintendo's TNES header are accepted.
    Trainers are removed because TNES stores PRG immediately after its header.
    The payload is validated against the declared PRG/CHR sizes before any
    output is returned, so malformed source ROMs cannot silently produce a
    truncated VC image.
    """
    if len(rom) < 16 or rom[:4] != b"NES\x1A":
        raise ValueError("NES Virtual Console injection requires an iNES or NES 2.0 ROM.")

    header = rom[:16]
    flags6 = header[6]
    flags7 = header[7]
    nes2 = (flags7 & 0x0C) == 0x08

    if nes2:
        mapper = (flags6 >> 4) | (flags7 & 0xF0) | ((header[8] & 0x0F) << 8)
        submapper = header[8] >> 4
        if submapper:
            raise ValueError(
                f"NES 2.0 mapper {mapper} submapper {submapper} is not representable in TNES."
            )
        prg_8k_units = _nes2_rom_units(header, prg=True)
        chr_8k_units = _nes2_rom_units(header, prg=False)
        # Byte 10 stores volatile PRG-RAM (low nibble) and PRG-NVRAM (high).
        explicit_wram = bool(header[10])
    else:
        mapper = (flags6 >> 4) | (flags7 & 0xF0)
        prg_8k_units = header[4] * 2
        chr_8k_units = header[5]
        explicit_wram = bool(header[8])

    try:
        tnes_mapper = _TNES_MAPPER_BY_INES[mapper]
    except KeyError:
        raise ValueError(
            f"NES mapper {mapper} is not supported by Nintendo's 3DS TNES runtime. "
            "Use RetroArch for this ROM."
        ) from None

    if not (1 <= prg_8k_units <= 0xFF):
        raise ValueError(f"NES PRG size ({prg_8k_units} × 8 KiB) is not representable in TNES.")
    if not (0 <= chr_8k_units <= 0xFF):
        raise ValueError(f"NES CHR size ({chr_8k_units} × 8 KiB) is not representable in TNES.")

    trainer_size = 512 if flags6 & 0x04 else 0
    payload_start = 16 + trainer_size
    prg_size = prg_8k_units * 8192
    chr_size = chr_8k_units * 8192
    payload_end = payload_start + prg_size + chr_size
    if payload_end > len(rom):
        raise ValueError(
            "NES ROM is shorter than the PRG/CHR sizes declared by its header."
        )

    # TNES mirroring byte: 0=mapper controlled, 1=horizontal, 2=vertical,
    # 3=four-screen/VRAM. Mapper-controlled boards are left at 0; otherwise use
    # the iNES hard-wired mirroring bits directly.
    mapper_controls_mirroring = mapper in {1, 4, 5, 7, 9, 10}
    if flags6 & 0x08:
        mirroring = 3
    elif mapper_controls_mirroring:
        mirroring = 0
    else:
        mirroring = 2 if flags6 & 0x01 else 1

    battery = 1 if flags6 & 0x02 else 0
    # The retail emulator exposes one boolean WRAM field rather than a size.
    # Preserve explicit source RAM metadata and enable it for mapper families
    # whose normal boards commonly expose CPU work RAM.
    wram = 1 if (explicit_wram or battery or mapper in {1, 4, 5, 9, 10}) else 0

    tnes_header = (
        b"TNES"
        + bytes(
            (
                tnes_mapper,
                prg_8k_units,
                chr_8k_units,
                wram,
                mirroring,
                battery,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        )
    )
    payload = rom[payload_start:payload_end]
    result = tnes_header + payload
    expected = 16 + prg_size + chr_size
    if len(result) != expected or result[:4] != b"TNES":
        raise ValueError("Generated TNES image failed structural validation.")
    return result


_INSTALLED = False


def install() -> None:
    """Extend the validated classic VC pipeline with the NES runtime family."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc

    classic_vc._CLASSIC_FAMILIES.add("nes")
    classic_vc._CLASSIC_ROM_EXTENSIONS["nes"] = (".nes",)

    original_prepare = classic_vc.prepare_classic_rom
    original_product_code = classic_vc._product_code

    def prepare_classic_rom(data: bytes, family: str) -> bytes:
        key = family.lower()
        prepared = original_prepare(data, key)
        return ines_to_tnes(prepared) if key == "nes" else prepared

    def product_code(family: str, romm_id: int) -> str:
        if family.lower() != "nes":
            return original_product_code(family, romm_id)
        import hashlib

        suffix = hashlib.sha256(f"nes:{romm_id}".encode("ascii")).hexdigest()[:3].upper()
        return f"CTR-N-RN{suffix}"

    classic_vc.prepare_classic_rom = prepare_classic_rom
    classic_vc._product_code = product_code
    _INSTALLED = True
