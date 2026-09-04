"""RomM Vita Manager package."""

# Classic VC modules are imported from several UI paths with ``from ... import``.
# Install the corrected title-ID generator and hardware-validated GB/GBC builder
# at package initialization so every later symbol binding sees the same live
# implementation.  This avoids import-order-dependent deployment behaviour.
from .classic_vc_title_fix import install as _install_classic_vc_title_fix
from .classic_vc_hardware_fix import install as _install_classic_vc_hardware_fix

_install_classic_vc_title_fix()
_install_classic_vc_hardware_fix()

del _install_classic_vc_title_fix
del _install_classic_vc_hardware_fix
