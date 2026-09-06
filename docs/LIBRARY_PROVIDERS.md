# Library Providers

This document defines the provider boundary for RommHeld library sources. It is intentionally narrower than target/runtime/deployment architecture.

## Rule

A library provider answers **what content exists** and, for remote providers, **how the selected content bytes can be materialized locally**.

A provider must not choose:

- device transport
- runtime/emulator
- destination path
- package format
- installation method

Those decisions remain target/device responsibilities.

The intended flow is:

```text
Local library or RomM
        |
        v
normalized library records
        |
        v
console-specific compatibility/runtime/deployment
```

## Normalized record contract

`library_records.py` defines the provider-neutral contract.

A `LibraryItem` retains three separate forms of platform identity:

1. `platform.provider_platform_id`: the provider's exact platform identifier where available.
2. `platform.source_key`: the exact provider/local source key. This is not replaced by a friendly label.
3. `platform.canonical_key`: RommHeld's normalized compatibility key.

`platform.display_name` is presentation-only.

For RomM, `RomMRemoteGame.source_platform_id` and `source_platform_slug` preserve the exact source identity while the existing `platform_slug` remains the normalized compatibility value used by current 3DS code.

Current `Game` and `RomMRemoteGame` records remain supported. `library_item_from_local()` and `library_item_from_romm()` are adapters so callers can migrate without a broad rewrite.

## RomM query scope

`RomMLibraryWorker` accepts a caller-supplied platform scope, cache scope key and optional ordering. The worker may query and page the remote catalogue, but the caller's target capability defines which platform slugs are relevant.

The legacy 3DS caller can temporarily omit the explicit scope and receives the existing 3DS-compatible set. New Vita/DS/future consumers should pass their own scope explicitly.

## Pagination

Remote loading remains progressive. All-platform browsing uses an opaque integer cursor that carries both:

- current platform position
- current ROM offset within that platform

This prevents a large RomM platform from losing records after the first page and prevents later pages from skipping platforms. A single selected platform retains the ordinary ROM offset behavior.

The UI should treat the all-platform cursor as opaque.

## Cache

RomM browse cache format is version 2.

The cache remains deliberately small (`MAX_ENTRIES = 24`) and is keyed by:

- RomM instance URL
- target/query `scope_key`
- search term
- selected platform slug

Cached records preserve publisher, release year and exact source-platform identity. A Vita all-platform cache therefore cannot collide with the current 3DS all-platform cache on the same RomM host.

The cache is disposable browse state. Version 1 pages are not migrated.

## Artwork authentication

Bearer authentication for artwork is restricted to the configured RomM **origin**, meaning scheme, hostname and effective port must all match. Relative artwork URLs resolve against the configured RomM origin. Credentials are not forwarded to external artwork hosts, protocol downgrades or another service on a different port.

## Current activation state

As of this prerequisite extraction:

- 3DS RomM browsing remains enabled.
- Vita RomM browsing is not yet exposed in the workspace.
- DS RomM browsing remains disabled until its target capability/deployment contract is ready.

The next Vita phase should reuse the provider/query/cache/materialization stack while keeping Vita-specific destination and USB/FTP decisions in Vita-owned code. It should not reuse the 3DS master/detail target-selection widget wholesale.
