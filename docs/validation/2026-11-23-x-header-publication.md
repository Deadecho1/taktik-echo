# X missing-header publication integration

This integration combines maintained `main` at `f8d6c91f` with the previously deployed Android and X recovery fixes through `ca9cf134`, then merges missing-header recovery from `bb61b296`.
The Android 16 accessibility initialization, button-bar and full-width drawer recognition, gallery recovery, and safe navigation margins remain included.

The only source conflict was the Android navigation-window reader in `ui/screen.py`.
The existing `system_navigation.bottom_bar` implementation is retained because it validates native controls, rejects duplicate bars, checks Back occlusion, and excludes the complete bottom strip.
The missing-header fixture assertion now expects that full-width exclusion; no header-recovery behavior was removed.
An existing inspection-test import block was also sorted for Ruff.

## Validation

The original unsanitized reproduction was rerun with `taktik.__file__` confirmed to point at this integration checkout.
It recognizes the captured detail page while keeping its missing author identity unavailable.
Successful restoration continuations remain synthetic transport replays, as documented in the [original validation record](2026-11-22-x-missing-header.md).
No live phone or human visual acceptance is claimed.

The focused reader, native visit, inspection, long-reading, drawer, and search-recovery tests passed 253 cases.
The inspection test file passed all 47 cases after its import-only cleanup.
The full browsing compatibility suite passed 4,186 tests with six skips on both Python 3.10.20 and 3.14.4, in 398.05 and 336.22 seconds respectively.
Both Python 3.10.20 and 3.14.4 source and wheel builds passed, with 40 wheel files and 44 source-archive files checked against the browsing source and native assets.
Repository layout, affected-file Ruff and formatting, and whitespace checks passed.

Before pin changes, Persona Engine's maintained `main` passed 871 tests with 14 skips using this Taktik checkout.
Echoseek's query suite passed 90 tests using the candidate Taktik and maintained Engine.
The first Engine run hit sandbox restrictions on localhost HTTP fixtures; the rerun with local sockets allowed passed.
Logs and distribution artifacts are under `/tmp/x-header-publication`.

## Adoption

Publish this complete integration revision before pinning it in Persona Engine's `taktik-install.json`.
Then publish that Engine adoption revision before pinning it in Echoseek's `pipeline-install.json`.
Use both repositories' existing installers and validate their actual vendor imports after installation.
Do not resume personas or change schedules, claims, reservations, or manual stop intent as part of dependency adoption.
