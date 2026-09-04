"""RomM Vita Manager package."""

# Classic VC modules are imported from several UI paths with ``from ... import``.
# Install title identity, hardware layout and donor-derived presentation in that
# order so every later symbol binding sees the same live implementation.
from .classic_vc_title_fix import install as _install_classic_vc_title_fix
from .classic_vc_hardware_fix import install as _install_classic_vc_hardware_fix
from .classic_vc_presentation_fix import install as _install_classic_vc_presentation_fix

_install_classic_vc_title_fix()
_install_classic_vc_hardware_fix()
_install_classic_vc_presentation_fix()

del _install_classic_vc_title_fix
del _install_classic_vc_hardware_fix
del _install_classic_vc_presentation_fix
