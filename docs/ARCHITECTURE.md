# Architecture

RommHeld is a PySide6 desktop application built around a shared library and transfer workflow with device-specific backends.

The current `main` branch is still the Vita baseline. The active development stack adds the 3DS FTP transport and a larger device-aware UI. Those branches should converge before more device-specific functionality is added.

## Current data flow

```text
Local RomM library / future RomM provider
                    │
                    ▼
             Library scanner
                    │
                    ▼
          Game + platform records
                    │
                    ▼
          Transfer planning/mapping
                    │
                    ▼
             Device backend
             ┌──────┴──────┐
             │             │
          VitaShell       FTP
             │             │
             ▼             ▼
            Vita          3DS
```

## Layer responsibilities

### Library

Discovers or retrieves game records and their RomM platform IDs. Platform identity comes from the library structure or provider metadata, not filename guessing.

### Transfer planning

Determines which files are candidates for transfer, applies explicit platform/destination mappings, performs safety and capacity checks, and exposes transfer state to the UI.

### Device backend

Owns transport-specific connection, filesystem, metadata, free-space, upload/copy, cancellation, resume, and verification operations.

The Vita backend uses a host-mounted VitaShell filesystem. The active 3DS backend uses FTP.

### UI

Presents devices, library sources, mappings, transfer state, setup, and runtime choices. The UI should not contain transport-specific filesystem logic where that logic can live in a backend.

### Emulator/runtime metadata

Describes frontends, emulators, cores, native runtimes, and RetroAchievements capability separately from transport. Installing or selecting a frontend must not automatically imply emulator or achievement support.

## Device backend rules

1. Keep transport-specific behaviour behind a device/backend boundary.
2. Do not scatter `if vita` / `if 3ds` transport logic throughout the GUI.
3. Device destinations must be explicit or backed by verified device-specific mappings.
4. Unknown platform mappings must fail safely rather than silently choosing a destination.
5. Backends must expose cancellation and clear transfer results.
6. Same-size files may be skipped where safe.
7. Different-size files must not be silently overwritten.
8. Completed transfers must be verified, currently by size.
9. Free-space preflight should be used where the backend can provide reliable information.
10. Remote path handling must prevent traversal and configured-root escape.
11. Destructive remote operations must require explicit user action.

## Current implementation boundaries

The package is being decomposed into focused modules including:

- `config.py` for persistent local configuration
- `models.py` for shared data structures
- `mappings.py` for platform mappings
- `romm.py` for local RomM library discovery
- `devices.py` for device metadata and backend boundaries
- `vita.py` for Vita filesystem discovery and storage information
- `three_ds_ftp.py` for the 3DS FTP transport on the active development branch
- `transfers.py` for reusable local transfer operations
- `emulators.py` for emulator/frontend metadata
- `vita_setup.py` for Vita setup information
- `ui.py` and the newer workspace modules for the application interface on the active UI branch

The root `romm_vita_manager.py` file remains as a compatibility entry point during the migration.

## Branch/integration state

The repository currently has several open draft PRs that form a dependency stack:

```text
main
 │
 ├── modular GUI foundation
 │     │
 │     ├── Send File
 │     │
 │     └── 3DS FTP
 │             │
 │             └── UI redesign
```

There are also duplicate Send File PRs. These should be consolidated rather than merged independently.

The UI redesign branch is substantially ahead of `main` and already contains its own tests, requirements, 3DS transport, target-profile work, and documentation. It is currently based on the 3DS feature branch, so integration order matters.

## Testing direction

Pure library, mapping, path-safety, transfer, and backend logic should be testable without Qt or physical handheld hardware. FTP behaviour should use mocked servers for automated tests, supplemented by documented real-device tests.

CI should at minimum compile the Python tree and run the complete unit-test suite. A green CI result should be established on the intended integration branch before claiming the new multi-device stack is stable.

## Future direction

The next architectural milestone is not another device. It is a clean common backend contract that lets Vita and 3DS share transfer planning, queueing, progress, cancellation, retry, verification, and error handling without duplicating UI workflows.

Once that foundation is stable, target profiles can describe filesystem layouts and runtime choices without coupling those concerns to the transport layer.
