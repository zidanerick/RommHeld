from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .hshop_catalog import find_vc_seed_by_title_id


_MAX_SNES_ROM_SIZE = 48 * 1024 * 1024 // 8  # Nintendo VC injector precedent: 48 Mbit
_DATA_HEADER_SIZE = 0x60
_GENERIC_PRESET_ID = 0x0000
_DEFAULT_VOLUME = 0x5A
_SIMPLE_CARTRIDGE_TYPES = {0x00, 0x01, 0x02}


@dataclass(frozen=True, slots=True)
class SnesRomInfo:
    rom: bytes
    mapping: str
    vc_rom_type: int
    cartridge_type: int
    map_mode: int
    checksum_valid: bool


@dataclass(frozen=True, slots=True)
class SnesDataInfo:
    rom_start: int
    rom_end: int
    product_id: str
    preset_id: int
    volume: int
    rom_type: int


def _strip_copier_header(rom: bytes) -> bytes:
    # Legacy .smc dumps commonly prepend exactly 512 bytes. Restrict removal to
    # the canonical 32 KiB bank-size remainder so an ordinary ROM is never
    # shortened merely because its filename happened to use .smc.
    if len(rom) > 512 and len(rom) % 0x8000 == 512:
        return rom[512:]
    return rom


def _candidate_score(rom: bytes, offset: int, expected_map_low: int) -> tuple[int, int, bool] | None:
    if offset < 0 or offset + 0x40 > len(rom):
        return None
    map_mode = rom[offset + 0x15]
    if (map_mode & 0x0F) != expected_map_low:
        return None

    complement = int.from_bytes(rom[offset + 0x1C : offset + 0x1E], "little")
    checksum = int.from_bytes(rom[offset + 0x1E : offset + 0x20], "little")
    checksum_valid = bool(checksum or complement) and ((checksum ^ complement) == 0xFFFF)
    reset_vector = int.from_bytes(rom[offset + 0x3C : offset + 0x3E], "little")
    title = rom[offset : offset + 21]
    printable = sum(1 for value in title if value == 0 or 0x20 <= value <= 0x7E)

    score = 4
    if checksum_valid:
        score += 5
    if reset_vector >= 0x8000:
        score += 3
    if printable >= 17:
        score += 1
    return score, map_mode, checksum_valid


def inspect_snes_rom(data: bytes) -> SnesRomInfo:
    """Identify a standard LoROM/HiROM image safe for generic Nintendo SNES VC.

    Nintendo's emulator has game-specific presets for enhancement chips and
    unusual mappings. RommHeld therefore accepts only ordinary ROM/RAM/battery
    cartridges here; DSP/Cx4/SuperFX/SA-1/SDD-1/etc. are rejected to RetroArch
    instead of pretending the Mario's Super Picross donor preset is universal.
    """
    rom = _strip_copier_header(bytes(data))
    if not rom:
        raise ValueError("SNES ROM is empty.")
    if len(rom) > _MAX_SNES_ROM_SIZE:
        raise ValueError("SNES ROM is larger than Nintendo's 48 Mbit VC injector limit; use RetroArch.")
    if len(rom) < 0x8000:
        raise ValueError("SNES ROM is too small to contain a standard LoROM/HiROM header.")

    candidates: list[tuple[int, str, int, int, bool]] = []
    for mapping, offset, map_low, vc_type in (
        ("lorom", 0x7FC0, 0x00, 0x14),
        ("hirom", 0xFFC0, 0x01, 0x15),
    ):
        result = _candidate_score(rom, offset, map_low)
        if result is None:
            continue
        score, map_mode, checksum_valid = result
        cartridge_type = rom[offset + 0x16]
        candidates.append((score, mapping, vc_type, cartridge_type, checksum_valid))

    if not candidates:
        raise ValueError(
            "Unable to identify this SNES ROM as standard LoROM or HiROM. Use RetroArch for unusual mappings."
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, mapping, vc_type, cartridge_type, checksum_valid = candidates[0]
    header_offset = 0x7FC0 if mapping == "lorom" else 0xFFC0
    map_mode = rom[header_offset + 0x15]

    if cartridge_type not in _SIMPLE_CARTRIDGE_TYPES:
        raise ValueError(
            f"SNES cartridge type 0x{cartridge_type:02X} requires game-specific enhancement-chip/preset handling. "
            "Use RetroArch for this ROM."
        )

    return SnesRomInfo(
        rom=rom,
        mapping=mapping,
        vc_rom_type=vc_type,
        cartridge_type=cartridge_type,
        map_mode=map_mode,
        checksum_valid=checksum_valid,
    )


def build_snes_data_bin(data: bytes, *, product_id: str = "KTR-RH00") -> bytes:
    """Build Nintendo's documented 0x60-byte SNES VC data.bin + raw ROM."""
    info = inspect_snes_rom(data)
    product = product_id.encode("ascii", errors="strict")
    if len(product) != 8 or not re.fullmatch(rb"KTR-[A-Z0-9]{4}", product):
        raise ValueError("SNES VC product ID must match KTR-XXXX.")

    rom = info.rom
    end = _DATA_HEADER_SIZE + len(rom)
    if len(rom) > 0xFFFFFF:
        raise ValueError("SNES ROM size does not fit the Nintendo data.bin 24-bit length field.")

    header = bytearray(_DATA_HEADER_SIZE)
    header[0x00:0x04] = (0x100).to_bytes(4, "little")
    header[0x04:0x08] = end.to_bytes(4, "little")
    header[0x08:0x0C] = (0x30).to_bytes(4, "little")
    header[0x0C:0x10] = (0x50).to_bytes(4, "little")
    header[0x10:0x14] = _DATA_HEADER_SIZE.to_bytes(4, "little")
    header[0x14:0x18] = end.to_bytes(4, "little")
    header[0x18:0x1C] = end.to_bytes(4, "little")  # no PCM/footer
    header[0x1C:0x20] = bytes(4)
    header[0x20:0x24] = end.to_bytes(4, "little")  # no SDD-1 region
    header[0x24:0x2C] = product
    header[0x2C:0x30] = bytes(4)
    header[0x30] = 0x3C
    header[0x31:0x34] = len(rom).to_bytes(3, "little")
    header[0x34] = 0
    header[0x35:0x38] = bytes(3)
    header[0x38] = 0
    header[0x39:0x3B] = bytes(2)
    header[0x3B:0x3D] = bytes(2)
    header[0x3D:0x3F] = _GENERIC_PRESET_ID.to_bytes(2, "little")
    header[0x3F] = 0x02
    header[0x40] = _DEFAULT_VOLUME
    header[0x41] = info.vc_rom_type
    header[0x42:0x50] = bytes(0x0E)
    header[0x50:0x54] = (3).to_bytes(4, "little")
    header[0x54:0x58] = (1).to_bytes(4, "little")
    header[0x58:0x60] = bytes(8)

    result = bytes(header) + rom
    parsed = parse_snes_data_bin(result)
    if parsed.rom_end != len(result) or parsed.rom_type != info.vc_rom_type:
        raise ValueError("Generated SNES data.bin failed structural validation.")
    return result


def parse_snes_data_bin(data: bytes) -> SnesDataInfo:
    if len(data) < _DATA_HEADER_SIZE:
        raise ValueError("SNES VC data.bin is shorter than its 0x60-byte header.")
    if int.from_bytes(data[0:4], "little") != 0x100:
        raise ValueError("SNES VC data.bin has the wrong header magic/value.")
    file_size = int.from_bytes(data[4:8], "little")
    rom_start = int.from_bytes(data[0x10:0x14], "little")
    rom_end = int.from_bytes(data[0x14:0x18], "little")
    footer_start = int.from_bytes(data[0x18:0x1C], "little")
    sdd1_start = int.from_bytes(data[0x20:0x24], "little")
    if file_size != len(data) or rom_start != 0x60 or not (rom_start <= rom_end <= len(data)):
        raise ValueError("SNES VC data.bin contains inconsistent size/ROM offsets.")
    if footer_start > len(data) or sdd1_start > len(data):
        raise ValueError("SNES VC data.bin optional-region offsets extend past the file.")
    if int.from_bytes(data[8:12], "little") != 0x30 or int.from_bytes(data[12:16], "little") != 0x50:
        raise ValueError("SNES VC data.bin is missing its fixed header constants.")
    if data[0x3F] != 0x02 or int.from_bytes(data[0x50:0x54], "little") != 3 or int.from_bytes(data[0x54:0x58], "little") != 1:
        raise ValueError("SNES VC data.bin is missing required runtime constants.")
    declared_rom_size = int.from_bytes(data[0x31:0x34], "little")
    if declared_rom_size != rom_end - rom_start:
        raise ValueError("SNES VC data.bin ROM-size field does not match its ROM region.")
    try:
        product_id = data[0x24:0x2C].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("SNES VC data.bin product ID is not ASCII.") from exc
    if not re.fullmatch(r"KTR-[A-Z0-9]{4}", product_id):
        raise ValueError("SNES VC data.bin product ID does not match KTR-XXXX.")
    rom_type = data[0x41]
    if rom_type not in {0x14, 0x15}:
        raise ValueError(f"SNES VC data.bin has unsupported ROM type 0x{rom_type:02X}.")
    return SnesDataInfo(
        rom_start=rom_start,
        rom_end=rom_end,
        product_id=product_id,
        preset_id=int.from_bytes(data[0x3D:0x3F], "little"),
        volume=data[0x40],
        rom_type=rom_type,
    )


def _seeded_key_y(ncch: bytes, info, seed: bytes) -> bytes:
    if len(seed) != 16:
        raise ValueError("SNES NCCH seed must be exactly 16 bytes.")
    expected = hashlib.sha256(seed + info.title_id[::-1]).digest()[:4]
    actual = ncch[0x114:0x118]
    if actual != expected:
        raise ValueError("hShop seed metadata does not match the SNES donor NCCH seed-verification hash.")
    return hashlib.sha256(info.key_y + seed).digest()[:16]


def _decrypt_seeded_region(vc, ncch: bytes, info, region, boot9: bytes, section: int, key_y: bytes) -> bytes:
    raw = ncch[region.offset : region.offset + region.size]
    if info.no_crypto:
        return raw
    _, aes_ctr, ncch_keys, _, _, _, _, _ = vc._require_classic_vc_tools()
    key = ncch_keys.extra_key(boot9, key_y, info.crypto_method)
    return aes_ctr.decrypt_region(key, info.title_id, section, raw)


def _extract_seeded_code(vc, ncch: bytes, info, boot9: bytes, key_y: bytes) -> bytes:
    _, aes_ctr, ncch_keys, _, exefs_format, ncch_format, _, _ = vc._require_classic_vc_tools()
    if info.exefs is None:
        raise ValueError("SNES VC donor NCCH has no ExeFS.")
    exefs = ncch[info.exefs.offset : info.exefs.offset + info.exefs.size]
    header = exefs[: exefs_format.HEADER_SIZE]
    if not info.no_crypto:
        main_key = ncch_keys.main_key(boot9, info.key_y)
        header = aes_ctr.decrypt_region(main_key, info.title_id, ncch_format.SECTION_EXEFS, header)
    entries = exefs_format.parse_header(header)
    entry = entries.get(".code")
    if entry is None:
        raise ValueError("SNES VC donor ExeFS is missing .code.")
    file_offset = exefs_format.HEADER_SIZE + entry.offset
    raw = exefs[file_offset : file_offset + entry.size]
    if info.no_crypto:
        return raw
    key = ncch_keys.extra_key(boot9, key_y, info.crypto_method)
    return aes_ctr.decrypt_region(
        key,
        info.title_id,
        ncch_format.SECTION_EXEFS,
        raw,
        block_offset=file_offset // aes_ctr.BLOCK_SIZE,
    )


_INSTALLED = False


def install() -> None:
    """Install conservative New-3DS SNES VC support into the validated backend."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    vc._CLASSIC_FAMILIES.add("snes")
    vc._CLASSIC_ROM_EXTENSIONS["snes"] = (".sfc", ".smc")
    original_extract_runtime = vc.extract_classic_vc_runtime
    original_product_code = vc._product_code
    original_patch_exheader = vc._patch_exheader
    original_prepare_payload = getattr(vc, "prepare_runtime_payload", None)
    original_postprocess_icon = getattr(vc, "postprocess_vc_icon", None)
    original_aux_files = getattr(vc, "prepare_runtime_aux_files", None)

    def extract_runtime(donor_cia, boot9, family: str):
        key = family.lower()
        if key != "snes":
            return original_extract_runtime(donor_cia, boot9, key)

        donor = vc.read_asset(donor_cia)
        keys = vc.read_asset(boot9)
        ncch = vc._primary_ncch_from_cia(donor)
        _, _, _, _, _, ncch_format, _, _ = vc._require_classic_vc_tools()
        info = ncch_format.parse(ncch)
        if info.exheader is None or info.romfs is None:
            raise ValueError("SNES VC donor is missing its exheader or RomFS runtime.")

        bitmask = ncch[0x18F]
        key_y = info.key_y
        if bitmask & 0x20:
            seed = find_vc_seed_by_title_id(info.title_id.hex().upper())
            if seed is None:
                raise ValueError(
                    "This SNES donor uses New-3DS seed crypto, but its public seed could not be found in hShop metadata. "
                    "Check the network connection and retry donor preparation."
                )
            key_y = _seeded_key_y(ncch, info, seed)

        exheader = vc._decrypt_region(
            ncch,
            info,
            info.exheader,
            keys,
            ncch_format.SECTION_EXTENDED_HEADER,
            extra=False,
        )
        romfs = _decrypt_seeded_region(
            vc,
            ncch,
            info,
            info.romfs,
            keys,
            ncch_format.SECTION_ROMFS,
            key_y,
        )
        files = vc.parse_romfs_files(romfs)
        if "/data.bin" not in files:
            raise ValueError("SNES VC donor RomFS is missing /data.bin.")
        parse_snes_data_bin(files["/data.bin"])
        # Remove the donor ROM immediately; only the small reusable runtime
        # assets and structural template are retained in RommHeld's cache.
        files["/data.bin"] = b""
        code = _extract_seeded_code(vc, ncch, info, keys, key_y)

        return vc.ClassicVcRuntime(
            family="snes",
            exheader=exheader,
            code=code,
            logo=b"",
            romfs_template=vc.build_romfs(files),
            rom_path="/data.bin",
        )

    def product_code(family: str, romm_id: int) -> str:
        if family.lower() != "snes":
            return original_product_code(family, romm_id)
        suffix = hashlib.sha256(f"snes:{romm_id}".encode("ascii")).hexdigest()[:3].upper()
        return f"KTR-N-R{suffix}"

    def patch_exheader(exheader: bytes, title_id: bytes, product_code_value: str) -> bytes:
        patched = original_patch_exheader(exheader, title_id, product_code_value)
        if not product_code_value.startswith("KTR-N-"):
            return patched
        short_id = "KTR-" + product_code_value[len("KTR-N-") :]
        if len(short_id) != 8:
            raise ValueError("Generated SNES product ID must match KTR-XXXX.")
        value = bytearray(patched)
        value[0:8] = short_id.encode("ascii")
        return bytes(value)

    def prepare_runtime_payload(data: bytes, family: str, rom_path: str) -> bytes:
        if family.lower() == "snes":
            return build_snes_data_bin(data)
        if callable(original_prepare_payload):
            return original_prepare_payload(data, family, rom_path)
        return vc.prepare_classic_rom(data, family)

    def postprocess_icon(icon: bytes, family: str) -> bytes:
        result = original_postprocess_icon(icon, family) if callable(original_postprocess_icon) else icon
        if family.lower() != "snes":
            return result
        try:
            from agbcia.formats import smdh
        except ImportError as exc:
            raise RuntimeError("SNES SMDH finalization requires agbcia.") from exc
        parsed = smdh.parse(result)
        rebuilt = smdh.build(
            smdh.Smdh(
                titles=parsed.titles,
                icon_small=parsed.icon_small,
                icon_large=parsed.icon_large,
                region_free=parsed.region_free,
                flags=parsed.flags | smdh.FLAG_NEW_3DS,
            )
        )
        if not (smdh.parse(rebuilt).flags & smdh.FLAG_NEW_3DS):
            raise ValueError("Generated SNES SMDH lost its New-3DS-only flag.")
        return rebuilt

    def prepare_aux_files(files: dict[str, bytes], family: str, product_code_value: str, icon: bytes) -> dict[str, bytes]:
        result = (
            original_aux_files(dict(files), family, product_code_value, icon)
            if callable(original_aux_files)
            else dict(files)
        )
        if family.lower() != "snes":
            return result
        if "/data.bin" not in result:
            raise ValueError("SNES runtime lost /data.bin before auxiliary metadata finalization.")
        short_id = "KTR-" + product_code_value[len("KTR-N-") :]
        if not re.fullmatch(r"KTR-[A-Z0-9]{4}", short_id):
            raise ValueError("Generated SNES internal product ID does not match KTR-XXXX.")

        data_bin = bytearray(result["/data.bin"])
        parse_snes_data_bin(bytes(data_bin))
        data_bin[0x24:0x2C] = short_id.encode("ascii")
        result["/data.bin"] = bytes(data_bin)

        old_icons = [path for path in result if re.fullmatch(r"/KTR-[A-Z0-9]{4}\.icn", path, re.I)]
        if len(old_icons) != 1:
            raise ValueError(
                f"Expected one KTR-XXXX.icn copy in the SNES donor RomFS, found {len(old_icons)}."
            )
        for path in old_icons:
            result.pop(path, None)
        result[f"/{short_id}.icn"] = icon
        return result

    vc.extract_classic_vc_runtime = extract_runtime
    vc._product_code = product_code
    vc._patch_exheader = patch_exheader
    vc.prepare_runtime_payload = prepare_runtime_payload
    vc.postprocess_vc_icon = postprocess_icon
    vc.prepare_runtime_aux_files = prepare_aux_files
    _INSTALLED = True
