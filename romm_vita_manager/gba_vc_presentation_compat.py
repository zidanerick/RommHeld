from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agbcia.banner.image import ImageSource


_INSTALLED = False


def install() -> None:
    """Keep existing GBA deployment callers compatible with the richer cache.

    The deployment worker predates the cached donor SMDH and supplies the boot
    logo + banner explicitly. Until that UI is decomposed into the shared VC
    deployment pipeline, resolve the companion SMDH from the same package cache
    here. Old caches are rejected by ``configured_donor_banner`` so this never
    silently falls back to generic presentation.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from . import gba_vc

    original_build = gba_vc.build_native_gba_cia

    def build_native_gba_cia(
        rom: bytes,
        artwork: "ImageSource",
        *,
        boot_logo: bytes,
        title_id: bytes,
        title_name: str,
        long_title: str | None = None,
        publisher: str = "",
        donor_banner: bytes | None = None,
        donor_icon: bytes | None = None,
        release_year: int | None = None,
        title_version: int = 0,
    ) -> bytes:
        if donor_banner is not None and donor_icon is None:
            from .gba_assets import cached_donor_icon_path

            path = cached_donor_icon_path()
            if not path.is_file():
                raise ValueError(
                    "The GBA VC presentation cache predates official-style icons. "
                    "Re-prepare the GBA donor once."
                )
            donor_icon = path.read_bytes()
        return original_build(
            rom,
            artwork,
            boot_logo=boot_logo,
            title_id=title_id,
            title_name=title_name,
            long_title=long_title,
            publisher=publisher,
            donor_banner=donor_banner,
            donor_icon=donor_icon,
            release_year=release_year,
            title_version=title_version,
        )

    gba_vc.build_native_gba_cia = build_native_gba_cia
    _INSTALLED = True
