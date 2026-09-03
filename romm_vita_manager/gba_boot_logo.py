"""RommHeld's bundled fallback for the optional 3DS NCCH logo region.

This is intentionally an original, non-Nintendo asset. It exists so native
GBA packaging never blocks on a donor CIA or extracted AGB_FIRM asset.

The NCCH logo region is 0x2000 bytes on modern 3DS applications. The
underlying agbcia pipeline treats the region as opaque bytes and does not
validate the logo format, so this fallback is kept deliberately neutral.
If a real, user-supplied logo is provided later, callers may still pass it
explicitly.
"""

LOGO_REGION_SIZE = 0x2000


def bundled_boot_logo() -> bytes:
    """Return the bundled original fallback logo-region bytes."""
    return bytes(LOGO_REGION_SIZE)
