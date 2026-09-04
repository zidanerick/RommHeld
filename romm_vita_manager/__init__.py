"""RomM Vita Manager package."""

# GB/GBC Virtual Console hardware validation found that the initial nested
# RomFS builder treated IVFC logical offsets as physical file offsets and
# hashed the final partial block without zero padding. Install the corrected
# hardware layout before any deployment modules import classic_vc symbols.
from .classic_vc_hardware_fix import install as _install_classic_vc_hardware_fix

_install_classic_vc_hardware_fix()
del _install_classic_vc_hardware_fix
