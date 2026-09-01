# Send File workflow

RommHeld's Send File workflow accepts arbitrary local files and requires an explicit destination. File extensions do not determine where files are sent.

The current Vita implementation maps `ux0:/...` paths into the mounted Vita `ux0` filesystem, prevents path escape, skips same-size files, asks before overwriting different-size files, supports cancellation, and verifies the resulting file size.

Future device backends should implement the same high-level behaviour over their own transport. In particular, the planned Nintendo 3DS backend will use FTP.
