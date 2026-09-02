# Device backends

RommHeld uses device backends to keep transport and device-specific filesystem behaviour separate from the shared library, transfer, and UI layers.

## Current state

- **PlayStation Vita**: current supported baseline using USB / VitaShell mounted storage.
- **Nintendo 3DS**: active development backend using FTP. The transport implementation exists on the active feature branch but is not yet part of `main`.
- **Nintendo DS / flashcards**: target-profile and storage research exists on the active UI branch; no complete DS transport backend is currently part of `main`.

A device appearing in the new selector does not by itself mean that its complete transfer backend is implemented.

## Backend responsibilities

A backend should provide, as applicable:

- device identity and connection state
- transport configuration
- filesystem root or remote root
- directory listing
- remote/local file metadata
- free-space information
- upload/copy operations
- progress reporting
- cancellation
- resume where the transport supports it
- post-transfer verification

The backend should not decide which emulator or frontend is best for a game.

## Shared responsibilities

The following should remain device-agnostic wherever practical:

- RomM library scanning
- game metadata
- platform identification
- transfer planning
- duplicate detection
- verification policy
- transfer queue state
- user-facing transfer semantics

Platform destinations belong to device-specific target mappings. A RomM platform ID must never be routed to an arbitrary destination because a similarly named emulator happens to exist.

## PlayStation Vita

The Vita baseline uses a host-mounted VitaShell filesystem. Mount discovery is dynamic and does not rely on a hard-coded username or storage UUID.

Known RetroFlow and Adrenaline mappings are handled explicitly. Unknown mappings remain unsupported.

## Nintendo 3DS FTP

The active 3DS transport provides:

- configurable FTP host and port
- optional credentials
- connection timeout and passive-mode configuration
- connection and directory browsing
- configured remote-root enforcement
- path traversal protection
- same-size skipping
- resume where the FTP server supports REST/STOR
- cancellation
- best-effort `SITE AVBL` free-space reporting
- post-transfer size verification

The transport deliberately does not assume a universal 3DS ROM directory. The configured root and destination must be explicit.

Real-device transfer testing and verified platform mappings remain separate implementation work.

## Generic Send File

All device backends should eventually support the same high-level **Send File** workflow:

```text
choose local file
      ↓
choose device
      ↓
choose explicit destination
      ↓
plan/check space
      ↓
transfer with progress + cancellation
      ↓
skip/resume/overwrite according to policy
      ↓
verify result
```

File extensions must not silently select destinations. Known installation layouts can be exposed later as explicit, verified presets.

## Safety rules

- Never hard-code credentials, IP addresses, mount UUIDs, or personal paths.
- Reject remote path traversal and configured-root escape.
- Do not silently overwrite different-size files.
- Do not perform destructive remote operations without explicit user action.
- Treat FTP as a trusted local-network transport rather than an Internet-facing service.
- Do not make transport availability imply emulator/runtime availability.

## Testing

Backend tests should be runnable without physical hardware. FTP should use mocked connections for unit tests, with a separate manual procedure for testing against a real 3DS FTP server.

The common backend contract should be established before adding additional device transports.
