# 3DS Agent Scope

## Mission

Extend RommHeld with a Nintendo 3DS device backend using FTP while preserving the existing PlayStation Vita workflow. Do not create a separate 3DS application and do not rewrite the project around the 3DS.

## Repository rules

- GitHub is the source of truth: `https://github.com/zidanerick/RommHeld`.
- Inspect the current repository before changing anything.
- Do not reconstruct code from old chats or generated ZIPs.
- Do not introduce personal paths, usernames, ROM data, credentials, mount UUIDs, or device dumps into the repository.
- Prefer small, coherent commits.
- Keep the project suitable for public GitHub.
- Run syntax checks and tests before declaring work complete.

## Product direction

RommHeld is a device-aware Linux desktop manager for a local RomM library. It should eventually support multiple handheld targets through reusable device backends.

Current target:

- PlayStation Vita: USB / VitaShell mounted filesystem.

Next target:

- Nintendo 3DS: FTP filesystem.

Do not make the 3DS implementation depend on Vita-only paths such as `ux0:/` or `/run/media/<user>/<mount>`.

## First milestone

Implement the Nintendo 3DS FTP backend and library transfer workflow.

The milestone is:

```text
RomM library
    ↓
RommHeld
    ↓
Nintendo 3DS backend
    ↓
FTP
    ↓
filesystem discovery
    ↓
explicit destination mapping
    ↓
safe transfer
    ↓
progress / cancellation
    ↓
post-transfer verification
```

Do not block this milestone on emulator installation or RetroAchievements work.

## Device architecture

Use a device/backend abstraction rather than scattering `if 3ds` throughout the GUI.

A backend should expose concepts similar to:

- device identity
- connection state
- transport information
- filesystem root
- directory listing
- remote file metadata
- free-space information when available
- file upload/copy
- optional resume
- transfer verification

Keep ROM scanning, game metadata, transfer planning, duplicate detection, and verification device-agnostic where practical.

Keep device-specific platform destinations in device-specific mapping definitions.

## FTP requirements

Implement a dedicated FTP backend.

Requirements:

1. configurable host
2. configurable port
3. optional username/password where required
4. connection test
5. timeouts
6. reconnect/error handling
7. safe directory browsing
8. file existence and size checks
9. upload
10. progress reporting
11. cancellation
12. resume where the FTP server supports it
13. post-transfer size verification
14. no destructive remote operations by default

Use Python's standard library or a maintained library. Do not shell out to a command-line FTP client merely to provide core functionality.

Do not hard-code an IP address.

Credentials must remain local configuration and must never be committed.

## 3DS filesystem discovery

Do not assume one universal ROM directory.

Allow the user to browse the FTP filesystem and configure a 3DS ROM root explicitly.

Investigate common layouts as suggestions only, including:

- `/roms/`
- `/roms/<platform>/`
- TwilightMenu++ / nds-bootstrap locations
- RetroArch locations
- Red Viper locations
- other verified frontend/homebrew locations

The app must distinguish a suggested/default location from a user-confirmed destination.

## Generic Send File workflow

RommHeld is intended to support arbitrary file transfer independently of ROM management.

The 3DS backend must therefore support a future first-class **Send File** workflow that can accept any local file, let the user select a remote directory, and reuse the normal transfer engine.

Do not infer remote destinations from file extensions.

Known package layouts may later expose explicit presets, but arbitrary files must remain file-type agnostic.

## 3DS platform mapping

Create a dedicated 3DS mapping layer.

Use RomM's top-level platform IDs as the keys.

Do not infer platforms from filenames.

Start only with mappings that have verified destinations.

Unsupported or uncertain platforms must remain explicitly unsupported rather than being routed into an arbitrary directory.

## Emulator and frontend awareness

Later RommHeld work may support detection and guidance for:

- TwilightMenu++ / nds-bootstrap
- native GBA execution
- RetroArch
- Red Viper
- other verified 3DS emulators/frontends

The initial FTP backend must remain independent of these components.

A frontend is not an emulator, and an emulator's RetroAchievements support must not be inferred from its presence.

## RetroAchievements

RetroAchievements is a first-class product requirement.

The architecture should eventually support explicit route metadata such as:

- native execution
- emulator execution
- RetroAchievements-compatible
- experimental RetroAchievements
- hardcore-compatible where verified

Do not automatically replace native execution with RetroArch just because RetroArch supports achievements.

Do not implement an unverified achievement bridge during the FTP milestone.

## UI

Add 3DS awareness to the existing RommHeld UI without breaking Vita functionality.

The eventual device view should show:

- Nintendo 3DS
- FTP transport
- connection status
- configurable host/port
- configured remote root
- detected frontend/homebrew where supported
- free space where available
- platform mappings
- transfer status

The user should always understand which device is selected before a transfer begins.

## Transfer behaviour

Reuse the existing transfer philosophy where practical:

- plan total size before transfer
- skip identical same-size files when safe
- do not silently overwrite different-size files
- support cancellation
- support retry of failed files
- verify resulting file size
- resume interrupted work where the protocol permits it
- keep a clear transfer result

Avoid destructive operations.

Do not delete remote files unless the user explicitly requests it.

## Safety

Protect remote path handling against:

- `..` traversal
- absolute-path escape from the configured root
- malformed remote paths
- malicious directory entries
- accidental writes outside the configured destination

Do not assume an FTP server's root corresponds to the SD card root without user-visible verification.

## Tests

Add mocked unit tests for:

- connection configuration
- connection failures
- path normalization
- remote path safety
- directory listing
- remote file metadata
- upload progress
- cancellation
- resume logic where applicable
- post-transfer size verification
- device/backend selection
- Vita/3DS mapping isolation

Tests must not require a physical 3DS.

Where practical, document an optional manual test against a real 3DS FTP server.

## Development discipline

Before changing code:

1. inspect the current repository
2. inspect current branches and open work
3. inspect the existing device abstractions and transfer engine
4. preserve working Vita behaviour
5. prefer small changes over rewrites

After changing code:

1. run Python syntax checks
2. run the full test suite
3. inspect the final diff
4. ensure no unrelated files changed
5. document anything not tested

Do not claim tests passed unless they actually passed.

## Future milestones

### Milestone 1
3DS device abstraction and FTP connection.

### Milestone 2
3DS filesystem browsing and generic file transfer.

### Milestone 3
3DS RomM platform mappings and game transfer.

### Milestone 4
3DS frontend/homebrew detection.

### Milestone 5
Emulator and native execution routing.

### Milestone 6
RetroAchievements-aware routing.

### Milestone 7
Upstream software/project links and explicit staging guidance.

## Out of scope for the first milestone

- CFW installation
- exploit deployment
- automatic CIA/3DSX installation
- protected firmware modification
- automatic replacement of existing frontend configuration
- copying proprietary firmware dumps from unknown sources
- automatic emulator/core selection
- RetroAchievements implementation

## Completion criteria

The first 3DS milestone is complete when:

1. an FTP connection can be configured
2. the connection can be tested
3. the remote filesystem can be browsed
4. a file can be uploaded to a user-selected destination
5. cancellation works
6. identical files can be skipped safely
7. remote file size can be verified after upload
8. Vita behaviour remains intact
9. automated tests pass
10. documentation explains setup and limitations
