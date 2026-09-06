# RommHeld Project Status

This file intentionally records only current integration checkpoints that are not already captured in the more stable architecture and UX documents.

## Current integration checkpoint

- Active PR: #21 (`refactor/apple-like-ui` into `feature/ui-redesign`)
- 3DS Runtime readiness can inspect a validated mounted SD card, a configured live ftpd endpoint, or both.
- FTP readiness uses the same application markers and known modeled CIA Title IDs as mounted-SD readiness, runs off the UI thread, and treats a successful ftpd connection as positive ftpd readiness evidence.
- TWiLight Menu++ `_nds` assets and generic RetroArch data/core folders are evidence that runtime files exist, not proof that a HOME Menu launcher or launchable frontend is installed. Their generic readiness state remains conservative until stronger launcher/title/core evidence is available.
- Direct verified 3DS homebrew staging and device-side configuration editing remain mounted-SD-only.
- Latest confirmed green checkpoint for this readiness work: `f90005d0cf96f88ccb3b9aa04b51786215ae4b2d`, GitHub Actions workflow #1786, compile passed and 537 tests passed.

## Validation boundary

The FTP readiness implementation is unit-tested and exercised through offscreen Qt lifecycle tests, including closing the dialog while a live FTP inventory worker is active. It has not yet been validated against a real Nintendo 3DS ftpd session. Real-device confirmation remains required before treating FTP runtime/title detection as hardware-validated.
