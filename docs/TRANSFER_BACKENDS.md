# Transfer backends

RommHeld separates the user-facing transfer workflow from the transport used by each handheld.

The current generic Send File implementation uses the Vita's mounted `ux0` filesystem. The planned Nintendo 3DS backend will provide the same high-level operations over FTP.

A future backend should provide explicit device capabilities for:

- connection/discovery
- directory listing
- free-space information
- file metadata
- upload
- cancellation
- resume where the transport permits it
- post-transfer verification

The UI must not infer destinations from file extensions. A destination is chosen by the user or supplied by an explicit, verified device-specific preset.
