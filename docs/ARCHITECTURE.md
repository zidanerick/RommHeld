# Architecture

The first releases intentionally use a small single-process PySide6 application.

## Data flow

```text
RomM library
    |
    v
Filesystem scanner
    |
    v
Game records + platform names
    |
    +----> installed-state check <---- Vita mount
    |
    v
Destination mapper
    |
    v
Transfer queue
    |
    v
USB-mounted Vita
```

## Design rules

1. The Linux application is the source of truth for transfers. No Vita-side downloader is required.
2. Vita mount points are detected dynamically. Storage UUIDs and personal absolute paths are not hard-coded.
3. RetroFlow destinations are based on the directory structure present on the connected Vita.
4. PSP and PS1 retain their Adrenaline locations.
5. Unknown mappings must fail safely rather than silently copying to a guessed location.
6. Transfers must be cancellable.
7. Existing files with the expected size should not be recopied.
8. New transfers receive a post-copy size check.
9. Any feature that can start a large transfer should check destination free space first.

## Future direction

As the application grows, filesystem scanning, destination mapping, and transfer logic should be separated from the GUI so they can be tested without a running Qt application.
