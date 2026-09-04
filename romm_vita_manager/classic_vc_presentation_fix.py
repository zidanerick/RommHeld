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


def install() -> None:
    """Layer donor-derived retail presentation over the validated classic builder.

    ``classic_vc_hardware_fix`` owns package/filesystem correctness. This layer
    deliberately leaves that code intact and changes only presentation:

    * cache the donor SMDH visual presentation in addition to its animated banner;
    * retain each donor family's cartridge/console/banner scene;
    * patch only the profile-declared game artwork and optional title badge;
    * rebuild SMDH text/flags rather than copying title-specific donor metadata.

    No donor binary is embedded in RommHeld. All retained material comes from
    the user's locally prepared donor cache.
    """
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
            raise ValueError("Classic VC donor did not provide a usable SMDH icon.")
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
            raise ValueError("Cached classic VC runtime is missing its animated donor banner.")
        if not runtime.donor_icon:
            raise ValueError(
                "Cached classic VC runtime is missing its donor icon presentation. "
                "Re-prepare this VC donor once."
            )

        metadata = normalize_vc_metadata(title_name, long_title=long_title, publisher=publisher)
        rom = vc.prepare_classic_rom(rom, family)
        title_id = vc.classic_title_id_for_romm_id(romm_id, family)
        product_code = vc._product_code(family, romm_id)
        exheader = vc._patch_exheader(runtime.exheader, title_id, product_code)

        validate_retail_romfs(runtime.romfs_template)
        files = vc.parse_romfs_files(runtime.romfs_template)
        if runtime.rom_path not in files:
            raise ValueError("Cached classic VC runtime is missing its ROM placeholder.")
        files[runtime.rom_path] = rom
        romfs = vc.build_romfs(files)
        validate_retail_romfs(romfs)

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

        icon_source = prepare_official_vc_icon_artwork(
            runtime.donor_icon,
            artwork,
            family,
        )
        icon = banner_assembly.build_icon(
            icon_source,
            metadata.short_title,
            metadata.long_title,
            metadata.publisher,
            save_data=vc._read_sci_save_data_size(exheader) > 0,
        )

        front_artwork = prepare_official_vc_front_artwork(
            runtime.donor_banner,
            artwork,
            family,
        )
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
            raise ValueError("Generated classic VC CIA failed final container validation.")
        if hashlib.sha256(ncch_bytes).digest() not in tmd:
            raise ValueError("Generated classic VC TMD lost its NCCH content hash.")
        return cia

    vc.ClassicVcRuntime = PresentedClassicVcRuntime
    vc.extract_classic_vc_runtime = extract_runtime
    vc.build_classic_vc_cia = build_cia
    _INSTALLED = True
