# Send File

RommHeld provides a file-type-agnostic **Send File** workflow for transferring arbitrary local files to a connected device.

## Behaviour

- Choose any local file.
- Enter an explicit destination path.
- No destination is inferred from the file extension.
- Existing same-size files are skipped.
- Existing different-size files require explicit overwrite confirmation.
- Transfers run through the cancellable transfer engine.
- Completed files are verified by size.

The current implementation is available through the Vita-mounted filesystem. The same workflow is intended to be reused by future device backends such as the Nintendo 3DS FTP backend.

## Safety

For Vita transfers, destination paths are constrained to the mounted `ux0` filesystem. Paths containing traversal components cannot escape that root.

The application does not automatically extract archives, install VPKs, infer package layouts, or modify emulator configuration. Users can obtain software from upstream projects and then use Send File to place the downloaded artifact at an explicitly selected destination.
