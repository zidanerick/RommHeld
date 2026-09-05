from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .classic_vc_hardware_fix import validate_classic_package_identity, validate_retail_romfs
from .vc_banner_patch import patch_official_vc_banner
from .vc_metadata import normalize_vc_metadata
from .vc_presentation import (
    prepare_official_vc_badge,
    prepare_official_vc_front_artwork,
    prepare_official_vc_icon_artwork,
)

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource


_INSTALLED = False


def _align(value: int, boundary: int = 0x40) -> int:
    return (value + boundary - 1) & ~(boundary - 1)


def validate_final_vc_cia(
    cia: bytes,
    *,
    title_id: bytes,
    expected_jump_id: bytes,
    expected_rom_path: str,
    family: str,
) -> None:
    """Re-open the final CIA bytes and verify launch-critical identity.

    Earlier validators operated on the pieces before CIA assembly. This one is
    deliberately independent of the builder objects: it walks the serialized
    CIA/TMD/content layout, finds the final NCCH, then checks the exheader that
    HOME Menu/loader will actually read. This catches wrapper/order mistakes
    before a hardware test can be used as a parser.
    """
    if len(cia) < 0x4000 or int.from_bytes(cia[0:4], "little") != 0x2020:
        raise ValueError("Generated VC CIA has an invalid serialized header.")
    cert_size = int.from_bytes(cia[0x08:0x0C], "little")
    ticket_size = int.from_bytes(cia[0x0C:0x10], "little")
    tmd_size = int.from_bytes(cia[0x10:0x14], "little")
    ticket_offset = _align(0x2020)
    tmd_offset = _align(ticket_offset + cert_size + ticket_size)
    content_offset = _align(tmd_offset + tmd_size)
    if content_offset + 0xA00 > len(cia):
        raise ValueError("Generated VC CIA content is truncated.")

    ticket = cia[ticket_offset : ticket_offset + ticket_size]
    if len(ticket) < 0x1E4 or ticket[0x1DC:0x1E4] != title_id:
        raise ValueError("Final VC CIA ticket does not contain the generated title ID.")

    tmd = cia[tmd_offset : tmd_offset + tmd_size]
    if len(tmd) < 0xB34 or tmd[0x18C:0x194] != title_id:
        raise ValueError("Final VC CIA TMD does not contain the generated title ID.")
    content_size = int.from_bytes(tmd[0xB0C:0xB14], "big")
    content_hash = tmd[0xB14:0xB34]
    ncch = cia[content_offset : content_offset + content_size]
    if len(ncch) != content_size or ncch[0x100:0x104] != b"NCCH":
        raise ValueError("Final VC CIA does not contain the expected NCCH application.")
    if hashlib.sha256(ncch).digest() != content_hash:
        raise ValueError("Final VC CIA NCCH does not match its serialized TMD hash.")

    disk_title_id = title_id[::-1]
    if ncch[0x108:0x110] != disk_title_id or ncch[0x118:0x120] != disk_title_id:
        raise ValueError("Final VC NCCH partition/program IDs do not match the generated title.")
    if int.from_bytes(ncch[0x180:0x184], "little") != 0x400:
        raise ValueError("Final VC NCCH does not expose a normal extended header.")
    exheader = ncch[0x200:0xA00]
    if len(exheader) != 0x800:
        raise ValueError("Final VC NCCH extended header is truncated.")
    if exheader[0x1C8:0x1D0] != expected_jump_id[::-1]:
        raise ValueError("Final VC SCI JumpId does not point at the generated title.")
    if exheader[0x200:0x208] != expected_jump_id[::-1]:
        raise ValueError("Final VC ACI ProgramId does not match the generated title.")
    if not (exheader[0x0D] & 0x02):
        raise ValueError("Final VC exheader lost the retail SDApplication flag.")
    if hashlib.sha256(exheader[:0x400]).digest() != ncch[0x160:0x180]:
        raise ValueError("Final VC serialized exheader hash is invalid.")

    # The path itself is checked earlier against the rebuilt RomFS. Keep it in
    # this final preflight contract so family adapters cannot accidentally pass
    # an empty/invalid runtime path while the outer CIA still looks plausible.
    if not expected_rom_path.startswith("/") or expected_rom_path.endswith("/"):
        raise ValueError(f"Final {family.upper()} VC runtime has an invalid ROM path.")


def install() -> None:
    """Layer donor-derived retail presentation over the validated VC builder."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    @dataclass(frozen=True)
    class PresentedClassicVcRuntime:
        family: str
        exheader: bytes
        code: bytes
        logo: bytes
        romfs_template: bytes
        rom_path: str
        donor_banner: bytes = b""
        donor_icon: bytes = b""

    hardware_extract_runtime = vc.extract_classic_vc_runtime

    def extract_runtime(donor_cia: Path, boot9: Path, family: str):
        base = hardware_extract_runtime(donor_cia, boot9, family)
        donor = vc.read_asset(donor_cia)
        keys = vc.read_asset(boot9)
        ncch = vc._primary_ncch_from_cia(donor)
        donor_icon = vc._extract_ncch_exefs_entry(ncch, keys, "icon")
        if not donor_icon:
            raise ValueError("Virtual Console donor did not provide a usable SMDH icon.")
        validate_retail_romfs(base.romfs_template)
        return PresentedClassicVcRuntime(
            family=base.family,
            exheader=base.exheader,
            code=base.code,
            logo=base.logo,
            romfs_template=base.romfs_template,
            rom_path=base.rom_path,
            donor_banner=base.donor_banner,
            donor_icon=donor_icon,
        )

    def build_cia(
        rom: bytes,
        artwork: "ImageSource",
        runtime: PresentedClassicVcRuntime,
        *,
        romm_id: int,
        title_name: str,
        long_title: str | None = None,
        publisher: str = "",
        release_year: int | None = None,
        title_version: int = 0,
    ) -> bytes:
        family = runtime.family.lower()
        if family not in vc._CLASSIC_FAMILIES:
            raise ValueError(f"Unsupported classic VC family: {family}")
        if not runtime.donor_banner:
            raise ValueError("Cached VC runtime is missing its animated donor banner.")
        if not runtime.donor_icon:
            raise ValueError(
                "Cached VC runtime is missing its donor icon presentation. Re-prepare this VC donor once."
            )

        metadata = normalize_vc_metadata(title_name, long_title=long_title, publisher=publisher)
        payload_builder = getattr(vc, "prepare_runtime_payload", None)
        if callable(payload_builder):
            payload = payload_builder(rom, family, runtime.rom_path)
        else:
            payload = vc.prepare_classic_rom(rom, family)
        title_id = vc.classic_title_id_for_romm_id(romm_id, family)
        product_code = vc._product_code(family, romm_id)
        exheader = vc._patch_exheader(runtime.exheader, title_id, product_code)

        validate_retail_romfs(runtime.romfs_template)
        files = vc.parse_romfs_files(runtime.romfs_template)
        if runtime.rom_path not in files:
            raise ValueError("Cached VC runtime is missing its ROM placeholder.")
        files[runtime.rom_path] = payload

        # Family runtimes may require a file-level invariant in addition to the
        # ROM payload itself. NES, for example, performs a per-ROM .patch lookup;
        # its donor patch is game-specific, so RommHeld supplies an inert empty
        # matching INI instead of either applying donor code patches or deleting
        # the lookup path entirely.
        runtime_files_builder = getattr(vc, "prepare_runtime_files", None)
        if callable(runtime_files_builder):
            files = runtime_files_builder(files, family, runtime.rom_path)
        if runtime.rom_path not in files or files[runtime.rom_path] != payload:
            raise ValueError("VC runtime file finalization changed or removed its ROM payload.")

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

        icon_source = prepare_official_vc_icon_artwork(runtime.donor_icon, artwork, family)
        icon = banner_assembly.build_icon(
            icon_source,
            metadata.short_title,
            metadata.long_title,
            metadata.publisher,
            save_data=vc._read_sci_save_data_size(exheader) > 0,
        )
        icon_postprocessor = getattr(vc, "postprocess_vc_icon", None)
        if callable(icon_postprocessor):
            icon = icon_postprocessor(icon, family)

        auxiliary_builder = getattr(vc, "prepare_runtime_aux_files", None)
        if callable(auxiliary_builder):
            files = auxiliary_builder(files, family, product_code, icon)
        if runtime.rom_path not in files:
            raise ValueError("VC runtime preparation removed its ROM payload path.")
        romfs = vc.build_romfs(files)
        validate_retail_romfs(romfs)

        front_artwork = prepare_official_vc_front_artwork(runtime.donor_banner, artwork, family)
        badge = prepare_official_vc_badge(
            runtime.donor_banner,
            metadata.banner_title,
            family,
            release_year=release_year,
        )
        banner = patch_official_vc_banner(
            runtime.donor_banner,
            front_artwork,
            family,
            badge_image=badge,
        )

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
        ncch_postprocessor = getattr(vc, "postprocess_vc_ncch", None)
        if callable(ncch_postprocessor):
            ncch_bytes = ncch_postprocessor(ncch_bytes, family)
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
        validate_classic_package_identity(
            ncch=ncch_bytes,
            exheader=exheader,
            donor_exheader=runtime.exheader,
            title_id=title_id,
            ticket=ticket,
            tmd=tmd,
        )
        meta = cia_format.MetaRegion(icon=icon)
        cia = cia_format.build(ticket=ticket, tmd=tmd, content=ncch_bytes, meta=meta)

        if len(cia) < len(ncch_bytes) or cia[:4] != (0x2020).to_bytes(4, "little"):
            raise ValueError("Generated VC CIA failed final container validation.")
        if hashlib.sha256(ncch_bytes).digest() not in tmd:
            raise ValueError("Generated VC TMD lost its NCCH content hash.")
        validate_final_vc_cia(
            cia,
            title_id=title_id,
            expected_jump_id=title_id,
            expected_rom_path=runtime.rom_path,
            family=family,
        )
        return cia

    vc.ClassicVcRuntime = PresentedClassicVcRuntime
    vc.extract_classic_vc_runtime = extract_runtime
    vc.build_classic_vc_cia = build_cia
    _INSTALLED = True
