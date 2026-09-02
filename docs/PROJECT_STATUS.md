# Project status

_Last audited: 2026-09-02_

## Executive summary

RommHeld has moved beyond the original Vita-only prototype, but the repository is currently in an integration phase rather than a clean release phase.

`main` is still the conservative Vita baseline. The active feature branches contain a substantially newer application architecture, generic file transfer, Nintendo 3DS FTP support, target-profile research, and a new handheld workspace UI.

The largest current risk is not a missing feature. It is branch fragmentation: several open draft PRs overlap or depend on one another, including two duplicate Send File implementations.

## What is established

- Vita library scanning and platform mapping are modularised.
- VitaShell mount detection and storage checks are separated from the UI.
- Transfer operations support progress, cancellation, same-size skipping, and size verification.
- Vita Setup functionality exists.
- A device/backend boundary exists and is being expanded.
- The 3DS FTP implementation exists on the active feature branch and includes path safety, browsing, upload, cancellation, resume support, and verification.
- The active UI branch adds handheld selection, device-aware workspaces, library-source selection, bundled artwork, and a larger test suite.

## What is not yet release-ready

- The multi-device work is not consolidated into `main`.
- The common backend contract is still relatively thin and does not yet own the complete transfer lifecycle.
- 3DS real-device ROM transfer validation and verified platform mappings remain incomplete.
- DS has UI/research representation but not a complete management backend.
- The new UI can run ahead of backend completeness, so supported/implemented state needs to remain explicit.
- CI exists on feature branches, but a green CI baseline has not been established on the intended final integration branch.
- There are overlapping Send File PRs (#10 and #11) and multiple stacked foundations (#1, #2, #12, #13).

## Active pull requests

| PR | Purpose | Assessment |
| --- | --- | --- |
| #13 | Handheld workspace/UI redesign | Top integration layer, but based on #12 rather than `main` |
| #12 | Nintendo 3DS FTP backend | Important backend work; needs integration and real-device validation |
| #11 | Send File implementation | Prefer one implementation to retain, subject to integration review |
| #10 | Earlier Send File implementation | Overlaps #11 and should not be merged independently |
| #2 | Device backend foundation | Useful architectural history, largely superseded by later work |
| #1 | Modular GUI foundation | Important foundation, largely incorporated into later branches |

## Bugs and risks found

### High: branch/integration fragmentation

The repository has multiple draft PRs built on different bases. PR #13 is 180 commits ahead of `main` and 4 commits behind it, while also being based on the 3DS feature branch. This makes it difficult to establish which code is authoritative.

**Action:** choose one integration branch, rebase or merge the active work into it, and close superseded PRs.

### High: duplicate Send File implementations

PRs #10 and #11 implement the same feature from different branches.

**Action:** select one implementation, integrate it once, then close the duplicate.

### High: backend abstraction is not yet deep enough

The device model identifies device types, but actual transfer workflows still contain device-specific behaviour in UI/application code. The intended architecture calls for transport operations to be owned by the backend.

**Action:** define a small common backend protocol for connection, filesystem operations, free space, upload, cancellation, resume capability, and verification. Move UI transport logic behind it.

### Medium: 3DS FTP resume semantics need real-server testing

The FTP implementation supports REST/STOR-style resume, but resume behaviour depends on the server.

**Action:** test interrupted uploads, reconnects, stale partial files, same-size files, and overwrite cases against the actual 3DS FTP server.

### Medium: 3DS free-space reporting is best-effort

The FTP backend uses `SITE AVBL` when available. Many FTP servers will not provide reliable capacity through that command.

**Action:** represent unavailable capacity explicitly as unknown and never substitute a guess.

### Medium: UI/backend capability mismatch

The active UI branch presents Vita, 3DS, and DS workspaces, but DS has no complete backend and 3DS is still being integrated.

**Action:** make capability state visible and disable or clearly mark unfinished actions.

### Medium: runtime and RetroAchievements routing is not ready

The architecture correctly separates frontend, emulator, transport, and achievement capability, but the routing system is still future work.

**Action:** finish device/transfer stability first, then implement routing from explicit capabilities and user preferences.

### Lower: packaging and cross-platform support

The active UI branch targets Linux/Windows/macOS conceptually, but packaging and removable-storage validation remain unfinished.

**Action:** defer substantial packaging work until the multi-device core is stable.

## Recommended order of work

1. **Integrate the current branch stack.** Establish one source of truth and remove duplicate/superseded PRs.
2. **Make CI authoritative.** Compile and run the full test suite on the integration branch, then add missing transfer/backend edge-case tests.
3. **Finish the common device backend contract.** Make the UI consume capabilities instead of implementing Vita/3DS transfer rules itself.
4. **Validate 3DS FTP with real hardware.** Test connection loss, cancellation, resume, same-size skip, overwrite protection, path safety, and verification.
5. **Implement verified 3DS target profiles and mappings.** Start small and enable only known-good destinations.
6. **Finish the device-aware UI integration.** Keep device-specific controls compartmentalised and capability state honest.
7. **Build the persistent transfer queue.** Add per-file state, retries, resumability, and clear failure reporting.
8. **Add the RomM remote provider.** Add authenticated remote browsing/downloads after local-library behaviour is stable.
9. **Add runtime/frontend detection and routing.** Use explicit capabilities and user preferences.
10. **Implement RetroAchievements-aware routing.** Expose only verified current compatibility paths.
11. **Improve library intelligence.** Artwork, metadata, hashes, duplicate detection, and destination previews.
12. **Package for additional desktop platforms.** Validate Windows and macOS after the core architecture is stable.

## Defer for now

Do not add more handheld backends yet. Do not spend major effort on artwork polish, package mirrors, automatic emulator installation, or sophisticated RetroAchievements routing while branch structure and common transfer architecture remain unsettled.

The immediate opportunity is consolidation and integration, not another large feature branch.
