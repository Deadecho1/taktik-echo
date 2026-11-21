# X operational and merge preparation

Milestone 7 adds reproducible compatibility and distribution checks, repairs shared native-reader cleanup, and documents the extension's operating limits.
It prepares the extension for review independently of consumer adoption.
Native promoted/ad evidence and outstanding human visual review remain open under milestones 5 and 6.

## Shared Phone cleanup

Review reproduced a cancellation that became an ordinary uncertain error when native-reader restoration or temporary-file removal also failed.
A native transport failure followed by a configuration-restoration failure could also downgrade `UNCERTAIN` to `FAILED`.
The reproduction calls the real `Phone.read("screen_reader_hierarchy")` interface with the existing simulated native transport.

The reader now checks pending cancellation/deadline expiry before cleanup and preserves the primary failure through ordinary restoration errors.
The same rule applies when temporary-file removal fails after restoration has already failed.
A new cancellation during restoration still escapes, including when subsequent removal fails.
Cleanup remains bounded, attempts removal once, and never repeats the native read.
New regressions cover 21 combined-failure and interruption cases, with recorded failing reproductions before the fixes.
All 42 native-reader cases pass through the public Phone interface.

## Installable distributions and automation

A clean Python 3.14 `python -m build --no-isolation` reproduced a source-installation failure: `setup.py` could not read `requirements.txt` from the source archive.
`MANIFEST.in` now includes that installation input.
The native reader directory is also an explicit Python package, with its Java source, DEX, and manifest declared as package data.
This removes setuptools' warning that the native package was absent from package discovery.

The permanent artifact verifier checks exact checkout bytes for 38 browsing source/asset files in the wheel and those files plus four installation inputs in the source archive.
It checks native source/DEX provenance and rejects missing or stale artifacts.
Eleven artifact-gate tests cover valid wheel/source archives, missing or stale runtime files, and the CLI failure for a source archive without installation requirements.
The Browsing compatibility workflow runs the shared/X/Instagram-service/TikTok-service suites, packaging checks, layout audit, and source-archive-to-wheel build on Python 3.10 and 3.14.
It runs without a phone or external model calls.

## Validation

The clean Python 3.10.20 environment passed all 3,343 combined compatibility, packaging, and artifact-gate checks, with two skips, in 160.08 seconds.
The clean Python 3.14.4 environment passed 3,342 checks with two skips in 124.74 seconds before the final source-requirements CLI regression was added.
All 11 artifact-gate tests then passed separately on Python 3.14, including that new regression.
The earlier Python 3.12 baseline passed 3,299 shared/X/Instagram-service/TikTok-service checks with two skips.
Both supported-endpoint environments built a source distribution and successfully built its wheel.
The final Python 3.14 wheel and source archive pass the 38/42-file checkout comparison.
An isolated installation of that wheel, imported outside the checkout, parsed a captured native search and verified the installed Java/DEX hashes against the packaged manifest.

Physical run `20261119T230243.954881Z` used the repaired native reader on the Pixel 4a with Android 13, English X `12.42.0-prod.01`, and 1080 × 2340 dimensions.
Top search for `from:NASA -filter:replies` passed startup and one advance, with two paired ordinary/screen-reader samples.
Replay verified both observations, the movement check, and source geometry after native-reader restoration.
The run checked controller reservations, held the established device/account locks, verified the expected account, restored Gboard after Taktik Keyboard query entry, and completed cleanup.
No phone session remains active; the two screenshots remain local and pending human review.

All 150 versioned XML fixture hashes across the seven fixture manifests were verified.
Ruff lint/format, tree layout, local Markdown links, and Git whitespace checks pass.
The independent Standards and Spec follow-ups have no unresolved findings in the final implementation.
Local test/build logs and final artifact hashes are retained under ignored `tests/smoke/x-operational-validation/20261120/`.
The phone run and its evidence audit remain under `tests/smoke/x-coverage-runs/20261119T230243.954881Z/`.

## Operating and review limits

The [operational guide](../x-operations.md) describes session ownership, cancellation, explicit recovery, observation/action lifecycle, supported runtime/device versions, and repeatable checks.
The native reader's Android API floor and the package's Python support do not establish complete physical X coverage on other devices or app versions.
Native-ad discovery and XML checks cannot supply the outstanding human visual approvals.
Prepare the extension as a draft merge review while those evidence limits remain open.
Consumer pins, model policy, and workflow adoption remain tracked separately and are not changed by this milestone.
