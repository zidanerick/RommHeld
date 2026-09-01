# Transfer workflow

RommHeld separates transfer planning from device transport.

The generic **Send File** workflow accepts arbitrary local files and an explicit destination. File extensions do not determine the destination.

The current Vita implementation uses the mounted `ux0` filesystem, skips identical same-size files, requires explicit confirmation for different-size overwrites, supports cancellation, and verifies final size.

Future device backends such as the Nintendo 3DS FTP backend should reuse these semantics rather than implement a separate transfer workflow.
