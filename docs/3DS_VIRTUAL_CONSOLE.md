# Nintendo 3DS Virtual Console packaging

RommHeld treats Nintendo-style Virtual Console packaging as a separate capability from raw ROM transfer and homebrew emulator deployment. The active implementation is donor-backed where Nintendo runtime or presentation assets are required, but the donor game payload itself is never retained in the reusable cache.

## Supported routes

| Family | Packaging route | Current validation state |
| --- | --- | --- |
| Game Boy Advance | Native `AGB_FIRM` CIA via `agbcia` | Real-device launch path confirmed |
| Game Boy | Nintendo classic VC runtime + RomFS injection | Implemented; donor and target cartridge validation present |
| Game Boy Color | Nintendo classic VC runtime + RomFS injection | Real-device launch path confirmed |
| NES | Nintendo TNES runtime for supported iNES/NES2 mappers | Installed/displayed on hardware; launch/save/relaunch retest remains after the latest package fixes |
| Game Gear | Nintendo/Sega `.GG.m` MArchive runtime | PC cartridge-family, structural and round-trip validation complete; real-device launch validation remains |
| Super Nintendo | New Nintendo 3DS `data.bin` runtime | Conservative simple LoROM/HiROM route implemented; real-device validation remains and generic preset handling is experimental |

Famicom/FDS remain explicit RetroArch routes until their source/container conventions are independently implemented. Unsupported NES mappers and SNES enhancement-chip or unusual mapping cases are rejected to RetroArch rather than being guessed.

## Official-release-first behavior

Before building an injection, RommHeld can query hShop catalogue metadata for a confident official Nintendo Virtual Console match. This is catalogue lookup only. RommHeld does not fetch commercial CIA content.

Catalogue matching requires the exact normalized VC family. For example, a Game Boy lookup cannot be satisfied by a Game Boy Color result merely because the platform names share words.

If no confident official release is available, the local donor-backed injection route remains available.

## Donor preparation and caching

Donor preparation is a one-time local operation using a user-supplied donor CIA and, where required, a valid retail `boot9.bin` or `boot9_prot.bin` dump.

Classic VC preparation caches only the reusable runtime/presentation contract needed by later builds, including the emulator code, exheader, sanitized RomFS template, donor banner/icon presentation and required NCCH auxiliary regions. The donor ROM payload and game-specific patch data are removed or neutralized before reuse.

GBA preparation caches the common AGB_FIRM boot logo and donor-derived HOME Menu presentation. RommHeld validates that a GBA donor's ExeFS `.code` has the documented AGB_FIRM layout: raw GBA ROM followed by the 0x360-byte footer containing the 0x324-byte metadata block, descriptor table and `.CAA` header. Donor acceptance therefore does not depend on a filename or a retail Title ID guess.

After successful preparation, RommHeld forgets the donor CIA and boot9 source paths. The reusable cache remains sufficient for normal deployments.

## Donor compatibility profiles

A donor is not treated as interchangeable merely because it belongs to the correct console family. Nintendo shipped materially different emulator builds.

RommHeld records a runtime fingerprint when preparing a donor. Classic profiles include hashes of the emulator code, exheader and sanitized RomFS template plus the donor identity and ROM path. GBA profiles include the validated donor `.code` fingerprint/ROM size and hashes of the reusable presentation assets.

For caches that contain a runtime profile, those fingerprints are enforced before the cache is reported ready. Classic code, exheader or RomFS changes invalidate the profiled cache. GBA boot-logo, banner or SMDH changes likewise invalidate a profiled GBA cache. The user must re-prepare the donor rather than silently building from modified cached assets. Older unprofiled caches remain governed by their existing cache-version and structural compatibility rules.

Current guidance is:

- **GBA:** any genuine GBA Virtual Console donor is suitable for reusable AGB_FIRM boot-logo/presentation extraction. The target game runs through AGB_FIRM, not a donor-specific GBA emulator runtime.
- **GB/GBC:** prefer a standard later retail runtime. Special-purpose Pokemon VC runtimes should not be the general donor because their emulator behavior differs, including save-state/link behavior.
- **NES:** prefer a later standard retail runtime rather than an early/Ambassador-era build. Unknown fingerprints remain unverified until hardware-tested.
- **Game Gear:** accept structurally valid `.GG.m` donors, but do not label a fingerprint recommended until it has passed real-device validation.
- **SNES:** a valid New Nintendo 3DS SNES donor is required, but donor choice does not replace per-game preset handling. The current generic simple-ROM path remains experimental.

The profile/fingerprint layer is intentionally separate from the UI so future hardware-tested fingerprints can be promoted to known-good profiles without changing packaging architecture.

## Family-specific behavior

### GBA / AGB_FIRM

Native GBA builds use `agbcia` from the compatible `0.1.x` API series. Save type is derived from the target ROM rather than copied from the donor. The generated package uses a GBA AGB_FIRM-compatible Title ID in `0004000000F???00`.

Nintendo's original retail GBA VC donor Title IDs are not required to use that generated-inject namespace. Do not use the `F???` pattern to decide whether a donor is genuine.

### GB / GBC

RommHeld validates the donor's embedded ROM family before caching it. GB and GBC donor payloads are distinguished using the Game Boy cartridge header rather than product naming alone.

Target ROMs are also validated before injection. The CGB compatibility flag must match the selected GB/GBC family and the standard Game Boy header checksum must be valid. This prevents mislabeled, truncated or corrupt ROMs from becoming CIAs that fail only after installation.

The target ROM replaces the sanitized `/rom/` placeholder while the donor emulator/runtime and retail presentation are retained.

### NES

Target iNES/NES2 ROMs are converted to Nintendo's TNES payload format only for mapper families represented by the Nintendo runtime. Unsupported mapper/submapper or unrepresentable sizing cases fail with a RetroArch recommendation.

Donor-specific `.patch` contents are not applied to unrelated games. RommHeld retains only an inert matching patch lookup path where the retail runtime expects one.

The current cache contract preserves the donor's dedicated NCCH launch-logo region. NES caches created before that contract must be prepared again.

### Game Gear

RommHeld decodes and validates the donor `.GG.m` MArchive, preserves its exact ROM basename because the cipher key depends on it, and re-encodes the target `.gg` ROM using that same convention. Generated archives are independently decoded again before packaging to catch local packing errors.

The raw target and donor ROM payloads must also expose Sega's `TMR SEGA` cartridge header at a standard header location and identify a Game Gear region family. Headerless data and Master System-family payloads are rejected. A 512-byte copier header is stripped only when the stripped payload exposes a valid Sega header. RommHeld deliberately does not reject on the Sega checksum field alone because Game Gear dumps are not uniformly reliable on that field.

### SNES / New Nintendo 3DS

SNES is New Nintendo 3DS-only. Donor seed crypto is resolved using public seed metadata when required.

The native route currently accepts conservative ordinary LoROM/HiROM cartridge types and rejects enhancement-chip/preset-dependent cases to RetroArch. `data.bin` is rebuilt with a generated `KTR-XXXX` identity and the package is marked New-3DS-only.

The generic preset path currently uses preset ID `0x0000` for simple ROMs. Official releases use game-specific preset IDs, so RommHeld does not invent or borrow a preset from an unrelated game. Because those presets may affect cartridge/save behavior, this route remains experimental until real-device launch and SRAM save/relaunch coverage is established.

## Generated Title IDs

RommHeld does not impersonate official retail Title IDs.

The deterministic hash remains each game's preferred generated slot, but actual deployment assignments are recorded in a persistent allocation registry. If another RommHeld game has already claimed that slot, first-time allocation probes forward to a free slot and persists the result. Classic families share one high normal-application pool; GBA uses the required AGB_FIRM `0004000000F???00` pool.

Allocation identity includes the configured RomM source as well as family and RomM ROM ID, so the same numeric ROM ID on two different RomM servers is not silently treated as the same title.

Title ID preview is side-effect free. Opening a deployment dialog does not allocate or write an ID. The assignment is persisted when deployment packaging begins, while the low-level deterministic ID helpers remain independent of user configuration.

The allocation API can avoid explicitly supplied reserved target IDs when making a new assignment. Existing valid assignments remain stable even if that value later appears in a reserved set, because silently changing the ID of an already-deployed title would break upgrade and save continuity.

This prevents collisions between RommHeld-managed generated titles. Current deployment does not claim to inventory every official, manually created or third-party CIA already installed on an arbitrary console, so it is not a guarantee of console-wide Title ID uniqueness.

## Package validation

Classic VC builds are checked before deployment at multiple layers:

- generated RomFS/IVFC structure and hashes
- ticket, TMD and NCCH title identity
- exheader `JumpId` and `ProgramId`
- preservation of the donor signed Access Descriptor
- `SDApplication` launch flag
- TMD content size/hash
- final serialized CIA/NCCH identity after assembly
- family-specific target ROM/container rules, including GB/GBC cartridge headers and Game Gear Sega-family identification
- profiled runtime-cache integrity where a fingerprint is available

NES and SNES additionally preserve required donor NCCH auxiliary launch-logo regions rather than emitting a minimal NCCH layout that only passes local parser checks.

These checks establish package consistency on the PC. They do not replace real-device validation.

## Validation boundary

Keep these categories separate when reporting status:

1. **Unit/structural validation:** automated package/parser/format tests.
2. **Desktop GUI validation:** Qt workflow behavior on a desktop environment.
3. **Integration validation:** RomM download, packaging, FBI Remote Install and FTP lifecycle checks.
4. **Real-device validation:** HOME Menu presentation, launch, save, exit and relaunch on Nintendo 3DS hardware.

Current real-device work still required before the new routes are considered fully validated:

- re-prepare the current NES donor, regenerate the CIA and confirm launch/save/relaunch after the latest launch fixes
- launch and exercise a generated Game Gear CIA
- launch a conservative SNES CIA and confirm SRAM/save/relaunch behavior
- verify icon, animated banner, title/publisher metadata and relaunch behavior for each newly validated family

Do not describe those routes as hardware-validated solely because automated tests pass.
