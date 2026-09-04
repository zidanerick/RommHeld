from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .gba_vc import prepare_vc_title_badge

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource


def _align(value: int, boundary: int) -> int:
    remainder = value % boundary
    return value if remainder == 0 else value + boundary - remainder


def _hash_blocks_padded(data: bytes, block_size: int) -> bytes:
    """Hash complete IVFC blocks, zero-padding the final short block."""
    if not data:
        return b""
    return b"".join(
        hashlib.sha256(data[offset : offset + block_size].ljust(block_size, b"\x00")).digest()
        for offset in range(0, len(data), block_size)
    )


def install() -> None:
    """Install the hardware-correct GB/GBC VC implementation.

    Real-device testing exposed two differences that unit tests did not catch:
    IVFC logical offsets were being treated as physical file positions, and the
    classic VC path discarded Nintendo's animated donor banner in favour of a
    generic flat banner. This compatibility layer fixes both while the family
    injector is being hardened on hardware.
    """
    from . import classic_vc as vc

    @dataclass(frozen=True)
    class HardwareClassicVcRuntime:
        family: str
        exheader: bytes
        code: bytes
        logo: bytes
        romfs_template: bytes
        rom_path: str
        donor_banner: bytes = b""

    original_extract_runtime = vc.extract_classic_vc_runtime

    def find_level3_offset(romfs: bytes) -> int:
        if romfs[:4] != b"IVFC":
            raise ValueError("VC donor RomFS is not an IVFC image.")

        # Retail 3DS RomFS stores Level 3 physically at 0x1000. The IVFC
        # descriptor's Level-3 offset is a logical hash-tree offset, not a
        # physical file position.
        if vc._looks_like_level3(romfs, 0x1000):
            return 0x1000

        # Keep a conservative fallback for old cached/synthetic fixtures.
        limit = min(len(romfs), 0x400000)
        for offset in range(0x20, limit, 0x10):
            if vc._looks_like_level3(romfs, offset):
                return offset
        raise ValueError("Unable to locate the RomFS Level 3 filesystem header.")

    def build_romfs(files: dict[str, bytes], *, block_size_log2: int = 12) -> bytes:
        level3 = vc._build_level3(files)
        block_size = 1 << block_size_log2

        # Nintendo-authored RomFS physically stores:
        #   header/master hash -> Level 3 -> Level 1 -> Level 2
        # while the descriptor offsets describe the logical hash tree.
        level2 = _hash_blocks_padded(level3, block_size)
        level1 = _hash_blocks_padded(level2, block_size)
        master = _hash_blocks_padded(level1, block_size)

        def padded(data: bytes) -> bytes:
            return data.ljust(_align(len(data), block_size), b"\x00")

        level3_padded = padded(level3)
        level1_padded = padded(level1)
        level2_padded = padded(level2)

        level1_logical = 0
        level2_logical = len(level1_padded)
        level3_logical = level2_logical + len(level2_padded)

        header = (
            b"IVFC"
            + (0x10000).to_bytes(4, "little")
            + len(master).to_bytes(4, "little")
            + level1_logical.to_bytes(8, "little")
            + len(level1).to_bytes(8, "little")
            + block_size_log2.to_bytes(4, "little")
            + bytes(4)
            + level2_logical.to_bytes(8, "little")
            + len(level2).to_bytes(8, "little")
            + block_size_log2.to_bytes(4, "little")
            + bytes(4)
            + level3_logical.to_bytes(8, "little")
            + len(level3).to_bytes(8, "little")
            + block_size_log2.to_bytes(4, "little")
            + bytes(4)
            + bytes(4)
            + (0).to_bytes(4, "little")
        ).ljust(0x60, b"\x00")

        first_block = (header + master).ljust(block_size, b"\x00")
        return first_block + level3_padded + level1_padded + level2_padded

    def extract_runtime(donor_cia: Path, boot9: Path, family: str):
        base = original_extract_runtime(donor_cia, boot9, family)
        donor = vc.read_asset(donor_cia)
        keys = vc.read_asset(boot9)
        ncch = vc._primary_ncch_from_cia(donor)
        donor_banner = vc._extract_ncch_exefs_entry(ncch, keys, "banner")
        return HardwareClassicVcRuntime(
            family=base.family,
            exheader=base.exheader,
            code=base.code,
            logo=base.logo,
            romfs_template=base.romfs_template,
            rom_path=base.rom_path,
            donor_banner=donor_banner,
        )

    def build_cia(
        rom: bytes,
        artwork: "ImageSource",
        runtime: HardwareClassicVcRuntime,
        *,
        romm_id: int,
        title_name: str,
        long_title: str | None = None,
        publisher: str = "",
        title_version: int = 0,
    ) -> bytes:
        family = runtime.family.lower()
        if family not in vc._CLASSIC_FAMILIES:
            raise ValueError(f"Unsupported classic VC family: {family}")
        rom = vc.prepare_classic_rom(rom, family)
        title_id = vc.classic_title_id_for_romm_id(romm_id, family)
        product_code = vc._product_code(family, romm_id)
        exheader = vc._patch_exheader(runtime.exheader, title_id, product_code)

        files = vc.parse_romfs_files(runtime.romfs_template)
        if runtime.rom_path not in files:
            raise ValueError("Cached classic VC runtime is missing its ROM placeholder.")
        files[runtime.rom_path] = rom
        romfs = build_romfs(files)

        (
            banner_assembly,
            _,
            _,
            cia_format,
            exefs_format,
            ncch_format,
            ticket_format,
            tmd_format,
        ) = vc._require_classic_vc_tools()

        icon_source = vc.prepare_vc_icon_artwork(artwork) if isinstance(artwork, bytes) else artwork
        icon = banner_assembly.build_icon(
            icon_source,
            title_name[:128],
            (long_title or title_name)[:128],
            publisher[:128],
            save_data=vc._read_sci_save_data_size(exheader) > 0,
        )

        if runtime.donor_banner:
            try:
                from agbcia.banner.donor import patch_donor_banner
            except ImportError as exc:
                raise RuntimeError("Animated GB/GBC VC banners require agbcia banner donor support.") from exc
            # Official GB/GBC donors use the same COMMON1 (box art) and
            # COMMON2 (title badge) texture contract as the GBA VC donor
            # banner. Leave the donor shell/environment textures untouched.
            banner = patch_donor_banner(
                runtime.donor_banner,
                artwork,
                bottom_badge_image=prepare_vc_title_badge(title_name),
            )
        else:
            # Old caches created before animated-banner extraction can still
            # launch after the IVFC fix; re-preparing the donor upgrades the
            # presentation without making the cache unusable.
            banner = banner_assembly.build_banner(artwork)

        entries = [
            exefs_format.ExeFSFile(name=".code", data=runtime.code),
            exefs_format.ExeFSFile(name="banner", data=banner),
            exefs_format.ExeFSFile(name="icon", data=icon),
        ]
        if runtime.logo:
            entries.append(exefs_format.ExeFSFile(name="logo", data=runtime.logo))
        exefs = exefs_format.build(entries)

        ncch = ncch_format.Ncch(
            title_id=title_id,
            product_code=product_code,
            exheader=exheader,
            exefs=exefs,
            romfs=romfs,
        )
        ncch_bytes = ncch_format.build(ncch)
        ticket = ticket_format.build(ticket_format.Ticket(title_id=title_id))
        content = tmd_format.content_chunk_from_data(
            content_id=0,
            content_index=0,
            data=ncch_bytes,
        )
        tmd = tmd_format.build(
            tmd_format.Tmd(
                title_id=title_id,
                contents=(content,),
                save_data_size=vc._read_sci_save_data_size(exheader),
                title_version=title_version,
            )
        )
        meta = cia_format.MetaRegion(icon=icon)
        return cia_format.build(ticket=ticket, tmd=tmd, content=ncch_bytes, meta=meta)

    vc.ClassicVcRuntime = HardwareClassicVcRuntime
    vc._find_level3_offset = find_level3_offset
    vc._hash_blocks = _hash_blocks_padded
    vc.build_romfs = build_romfs
    vc.extract_classic_vc_runtime = extract_runtime
    vc.build_classic_vc_cia = build_cia
