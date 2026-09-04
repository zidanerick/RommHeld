"""RomM Vita Manager package."""

# VC modules are imported from several UI paths with ``from ... import``.
# Install family extensions/corrections before those callers bind their local
# symbols so every deployment path sees the same validated implementation.
from .nes_vc import install as _install_nes_vc
from .gamegear_vc import install as _install_gamegear_vc
from .snes_vc import install as _install_snes_vc
from .snes_new3ds_ncch import install as _install_snes_new3ds_ncch
from .classic_vc_title_fix import install as _install_classic_vc_title_fix
from .classic_vc_hardware_fix import install as _install_classic_vc_hardware_fix
from .classic_vc_presentation_fix import install as _install_classic_vc_presentation_fix
from .gba_vc_presentation_compat import install as _install_gba_vc_presentation_compat

_install_nes_vc()
_install_gamegear_vc()
_install_snes_vc()
_install_snes_new3ds_ncch()
_install_classic_vc_title_fix()
_install_classic_vc_hardware_fix()
_install_classic_vc_presentation_fix()
_install_gba_vc_presentation_compat()

del _install_nes_vc
del _install_gamegear_vc
del _install_snes_vc
del _install_snes_new3ds_ncch
del _install_classic_vc_title_fix
del _install_classic_vc_hardware_fix
del _install_classic_vc_presentation_fix
del _install_gba_vc_presentation_compat
