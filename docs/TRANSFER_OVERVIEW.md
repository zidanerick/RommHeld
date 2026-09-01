# Transfer overview

RommHeld separates transfer planning from device transport. The generic Send File workflow accepts arbitrary local files and an explicit destination.

The current Vita implementation uses the mounted ux0 filesystem, skips identical same-size files, requires explicit confirmation for different-size overwrites, supports cancellation, and verifies final size.

Future backends such as Nintendo 3DS FTP should reuse these semantics.
