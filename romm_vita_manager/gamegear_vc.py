from __future__ import annotations

import hashlib
import zlib
from pathlib import PurePosixPath


_MARCHIVE_MAGIC = b"mdf\x00"
_MARCHIVE_SEED = "25G/xpvTbsb+6"
_MARCHIVE_KEY_LENGTH = 64
_MASK32 = 0xFFFFFFFF
_SEGA_HEADER_MAGIC = b"TMR SEGA"
_SEGA_HEADER_OFFSETS = (0x7FF0, 0x3FF0, 0x1FF0)
_GAME_GEAR_REGION_CODES = {0x5, 0x6, 0x7}


class _Mt19937:
    """Small MT19937 implementation matching MArchiveBatchTool's C# port."""

    N = 624
    M = 397
    MATRIX_A = 0x9908B0DF
    UPPER_MASK = 0x80000000
    LOWER_MASK = 0x7FFFFFFF

    def __init__(self, keys: list[int]):
        if not keys:
            raise ValueError("MArchive MT19937 seed array cannot be empty.")
        self.mt = [0] * self.N
        self.index = self.N + 1
        self._init_by_array(keys)

    def _init_genrand(self, seed: int) -> None:
        self.mt[0] = seed & _MASK32
        for index in range(1, self.N):
            previous = self.mt[index - 1]
            self.mt[index] = (
                1812433253 * (previous ^ (previous >> 30)) + index
            ) & _MASK32
        self.index = self.N

    def _init_by_array(self, keys: list[int]) -> None:
        self._init_genrand(19650218)
        i = 1
        j = 0
        for _ in range(max(self.N, len(keys))):
            previous = self.mt[i - 1]
            self.mt[i] = (
                (self.mt[i] ^ ((previous ^ (previous >> 30)) * 1664525))
                + keys[j]
                + j
            ) & _MASK32
            i += 1
            j += 1
            if i >= self.N:
                self.mt[0] = self.mt[self.N - 1]
                i = 1
            if j >= len(keys):
                j = 0
        for _ in range(self.N - 1):
            previous = self.mt[i - 1]
            self.mt[i] = (
                (self.mt[i] ^ ((previous ^ (previous >> 30)) * 1566083941)) - i
            ) & _MASK32
            i += 1
            if i >= self.N:
                self.mt[0] = self.mt[self.N - 1]
                i = 1
        self.mt[0] = 0x80000000
        self.index = self.N

    def next_u32(self) -> int:
        if self.index >= self.N:
            for kk in range(self.N - self.M):
                y = ((self.mt[kk] & self.UPPER_MASK) | (self.mt[kk + 1] & self.LOWER_MASK)) >> 1
                self.mt[kk] = self.mt[kk + self.M] ^ y ^ (
                    self.MATRIX_A if self.mt[kk + 1] & 1 else 0
                )
            for kk in range(self.N - self.M, self.N - 1):
                y = ((self.mt[kk] & self.UPPER_MASK) | (self.mt[kk + 1] & self.LOWER_MASK)) >> 1
                self.mt[kk] = self.mt[kk + (self.M - self.N)] ^ y ^ (
                    self.MATRIX_A if self.mt[kk + 1] & 1 else 0
                )
            y = ((self.mt[self.N - 1] & self.UPPER_MASK) | (self.mt[0] & self.LOWER_MASK)) >> 1
            self.mt[self.N - 1] = self.mt[self.M - 1] ^ y ^ (
                self.MATRIX_A if self.mt[0] & 1 else 0
            )
            self.index = 0

        value = self.mt[self.index]
        self.index += 1
        value ^= value >> 11
        value ^= (value << 7) & 0x9D2C5680
        value ^= (value << 15) & 0xEFC60000
        value ^= value >> 18
        return value & _MASK32


def _marchive_key(filename: str, *, seed: str = _MARCHIVE_SEED) -> bytes:
    basename = PurePosixPath(filename.replace("\\", "/")).name.lower()
    if not basename:
        raise ValueError("Game Gear MArchive requires a donor ROM filename.")
    digest = hashlib.md5((seed + basename).encode("utf-8")).digest()
    words = [int.from_bytes(digest[offset : offset + 4], "little") for offset in range(0, 16, 4)]
    twister = _Mt19937(words)
    key = bytearray()
    while len(key) < _MARCHIVE_KEY_LENGTH:
        key += twister.next_u32().to_bytes(4, "little")
    return bytes(key[:_MARCHIVE_KEY_LENGTH])


def _xor_marchive(data: bytes, key: bytes) -> bytes:
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(data))


def _sega_header_offset(data: bytes) -> int | None:
    for offset in _SEGA_HEADER_OFFSETS:
        if offset + 16 <= len(data) and data[offset : offset + 8] == _SEGA_HEADER_MAGIC:
            return offset
    return None


def validate_gamegear_rom(rom: bytes) -> bytes:
    """Return a raw Game Gear ROM after conservative Sega-header validation.

    The Sega header may legally appear at 0x7FF0, 0x3FF0 or 0x1FF0. Some old
    dumps carry a 512-byte copier header, so strip that only when the remaining
    payload exposes a valid Sega header. The header checksum is intentionally
    not enforced because known Game Gear releases frequently contain values
    that are not valid under the export Master System checksum rules.
    """
    data = bytes(rom)
    if not data:
        raise ValueError("Game Gear ROM is empty.")
    if len(data) > 0x800000 + 512:
        raise ValueError("Game Gear ROM is larger than the supported 8 MiB limit.")

    header_offset = _sega_header_offset(data)
    if header_offset is None and len(data) > 512:
        stripped = data[512:]
        stripped_header = _sega_header_offset(stripped)
        if stripped_header is not None:
            data = stripped
            header_offset = stripped_header

    if header_offset is None:
        raise ValueError(
            "Game Gear ROM does not contain the required TMR SEGA cartridge header. "
            "The file may be corrupted, headerless, or for another Sega platform."
        )

    region_code = data[header_offset + 0x0F] >> 4
    if region_code not in _GAME_GEAR_REGION_CODES:
        raise ValueError(
            "ROM has a Sega cartridge header but is not identified as Game Gear. "
            "Use the appropriate Master System/other Sega deployment route instead."
        )
    if len(data) > 0x800000:
        raise ValueError("Game Gear ROM is larger than the supported 8 MiB limit.")
    return data


def unpack_gamegear_mdf(data: bytes, filename: str) -> bytes:
    """Decode the zlib/XOR MArchive wrapper used by Nintendo's Game Gear VC."""
    if len(data) < 8 or data[:4] != _MARCHIVE_MAGIC:
        raise ValueError("Game Gear donor ROM is not an mdf MArchive.")
    expected_size = int.from_bytes(data[4:8], "little")
    if expected_size <= 0 or expected_size > 0x800000:
        raise ValueError(f"Game Gear MArchive reports an invalid ROM size: {expected_size} bytes.")
    key = _marchive_key(filename)
    try:
        raw = zlib.decompress(_xor_marchive(data[8:], key))
    except zlib.error as exc:
        raise ValueError(
            "Unable to decompress the Game Gear donor ROM wrapper; this donor may use an unsupported MArchive seed/codec."
        ) from exc
    if len(raw) != expected_size:
        raise ValueError(
            f"Game Gear MArchive decoded to {len(raw)} bytes; expected {expected_size}."
        )
    return raw


def pack_gamegear_mdf(rom: bytes, filename: str) -> bytes:
    """Encode a raw .gg ROM in the exact mdf wrapper consumed by the donor runtime."""
    if not rom:
        raise ValueError("Game Gear ROM is empty.")
    if len(rom) > 0x800000:
        raise ValueError("Game Gear ROM is larger than the supported 8 MiB limit.")
    key = _marchive_key(filename)
    compressed = zlib.compress(bytes(rom), level=9)
    result = _MARCHIVE_MAGIC + len(rom).to_bytes(4, "little") + _xor_marchive(compressed, key)
    # Never return an archive that our independent read path cannot recover.
    if unpack_gamegear_mdf(result, filename) != bytes(rom):
        raise ValueError("Generated Game Gear MArchive failed round-trip validation.")
    return result


_INSTALLED = False


def install() -> None:
    """Extend the validated donor-backed classic VC backend with Game Gear."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    vc._CLASSIC_FAMILIES.add("gamegear")
    vc._CLASSIC_ROM_EXTENSIONS["gamegear"] = (".gg",)
    original_extract_runtime = vc.extract_classic_vc_runtime
    original_product_code = vc._product_code

    def extract_runtime(donor_cia, boot9, family: str):
        key = family.lower()
        if key != "gamegear":
            return original_extract_runtime(donor_cia, boot9, key)

        donor = vc.read_asset(donor_cia)
        keys = vc.read_asset(boot9)
        ncch = vc._primary_ncch_from_cia(donor)
        _, _, _, _, _, ncch_format, _, _ = vc._require_classic_vc_tools()
        info = ncch_format.parse(ncch)
        if info.exheader is None or info.romfs is None:
            raise ValueError("Game Gear VC donor is missing its exheader or RomFS runtime.")

        exheader = vc._decrypt_region(
            ncch,
            info,
            info.exheader,
            keys,
            ncch_format.SECTION_EXTENDED_HEADER,
            extra=False,
        )
        romfs = vc._decrypt_region(
            ncch,
            info,
            info.romfs,
            keys,
            ncch_format.SECTION_ROMFS,
            extra=True,
        )
        files = vc.parse_romfs_files(romfs)
        candidates = sorted(
            path
            for path in files
            if path.casefold().startswith("/system/roms/") and path.casefold().endswith(".gg.m")
        )
        if len(candidates) != 1:
            raise ValueError(
                f"Expected one .GG.m ROM payload in the Game Gear donor, found {len(candidates)}."
            )
        rom_path = candidates[0]
        # Validate the archive, its embedded Game Gear identity, and preserve
        # the exact path. The MArchive key is derived from this basename.
        donor_rom = unpack_gamegear_mdf(files[rom_path], PurePosixPath(rom_path).name)
        validate_gamegear_rom(donor_rom)
        files[rom_path] = b""

        code = vc._extract_ncch_exefs_entry(ncch, keys, ".code")
        try:
            logo = vc._extract_ncch_exefs_entry(ncch, keys, "logo")
        except ValueError:
            logo = b""
        return vc.ClassicVcRuntime(
            family=key,
            exheader=exheader,
            code=code,
            logo=logo,
            romfs_template=vc.build_romfs(files),
            rom_path=rom_path,
        )

    def product_code(family: str, romm_id: int) -> str:
        if family.lower() != "gamegear":
            return original_product_code(family, romm_id)
        suffix = hashlib.sha256(f"gamegear:{romm_id}".encode("ascii")).hexdigest()[:3].upper()
        return f"CTR-N-GG{suffix}"

    def prepare_runtime_payload(data: bytes, family: str, rom_path: str) -> bytes:
        prepared = vc.prepare_classic_rom(data, family)
        if family.lower() == "gamegear":
            prepared = validate_gamegear_rom(prepared)
            return pack_gamegear_mdf(prepared, PurePosixPath(rom_path).name)
        return prepared

    vc.extract_classic_vc_runtime = extract_runtime
    vc._product_code = product_code
    vc.prepare_runtime_payload = prepare_runtime_payload
    _INSTALLED = True
