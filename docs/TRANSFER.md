# Transfer workflow

RommHeld separates the transfer workflow from the device transport.

The first generic workflow is **Send File**. It accepts arbitrary local files and an explicit remote destination. File extensions do not select a destination automatically.

The current Vita implementation uses the mounted `ux0` filesystem and reuses the cancellable chunked transfer engine. It skips identical same-size files, asks before overwriting different-size files, and verifies the final file size.

Future transports, including the planned Nintendo 3DS FTP backend, should implement the same semantics through a device backend rather than creating another transfer implementation.
