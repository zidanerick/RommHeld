from __future__ import annotations


_INSTALLED = False


def install() -> None:
    """Mark generated SNES NCCHs for the New-3DS (snake/KTR) platform.

    The shared agbcia NCCH writer intentionally emits ordinary CTR platform
    content because that is correct for GB/GBC/GBA/NES/Game Gear. Nintendo's
    SNES Virtual Console is New-3DS-only, so its NCCH platform flag must be 2
    rather than 1. The donor exheader already carries the New-3DS system-mode
    constraints and its signed Access Descriptor is left untouched.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    previous = getattr(vc, "postprocess_vc_ncch", None)

    def postprocess_vc_ncch(ncch: bytes, family: str) -> bytes:
        result = previous(ncch, family) if callable(previous) else ncch
        if family.lower() != "snes":
            return result
        if len(result) < 0x190 or result[0x100:0x104] != b"NCCH":
            raise ValueError("Generated SNES NCCH is missing a valid header.")

        patched = bytearray(result)
        # NCCH flags begin at 0x188; byte 4 is Content Platform:
        # 1 = CTR, 2 = snake (New Nintendo 3DS).
        patched[0x18C] = 2
        final = bytes(patched)
        if final[0x18C] != 2:
            raise ValueError("Generated SNES NCCH lost its New-3DS platform flag.")
        return final

    vc.postprocess_vc_ncch = postprocess_vc_ncch
    _INSTALLED = True
