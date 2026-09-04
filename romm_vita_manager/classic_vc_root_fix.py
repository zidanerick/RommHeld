from __future__ import annotations


_INSTALLED = False


def install() -> None:
    """Use the retail RomFS root-directory parent convention.

    In Nintendo-authored RomFS images the root directory's parent offset points
    back to the root entry itself (offset 0). The original GB/GBC builder used
    the ordinary no-entry sentinel (0xFFFFFFFF) instead. RommHeld's own parser
    did not consult this field, so round-trip tests passed even though a real
    3DS can reject or fail to traverse the rebuilt filesystem at runtime.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from . import classic_vc as vc

    vc._ROOT_PARENT = 0
    _INSTALLED = True
