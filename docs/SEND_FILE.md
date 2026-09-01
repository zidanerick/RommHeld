# Send File

RommHeld provides a file-type-agnostic **Send File** workflow for transferring arbitrary local files to a connected device.

The current implementation targets the Vita-mounted filesystem. Users choose a local file and an explicit `ux0:/...` destination.

Behaviour:

- file extension does not determine the destination
- same-size destination files are skipped
- different-size destination files require explicit overwrite confirmation
- transfers are cancellable
- completed files are verified by size
- Vita destinations are constrained to the mounted `ux0` filesystem

Future devices such as the planned Nintendo 3DS FTP backend should reuse the same high-level workflow through their device backend.
