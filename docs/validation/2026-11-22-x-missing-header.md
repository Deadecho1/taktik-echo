# X detail recovery with missing author text

Implemented in the maintained Taktik checkout, based on `2615fe66641d43031f6597c42f0a7127ea7fd152`.
The pre-existing change in `2026-11-19-x-engagement.md` is preserved separately.
No downstream source, dependency pin, schedule, reservation, or manual stop state was changed.

## Reproduction and correction

The original full ordinary/native captures failed on this checkout before the header check because the bottom Android navigation window was classified as a clipboard receipt.
Removing only that window exposed the diagnosed `Unrecognized main-post name and handle.` failure.
The original parser reproduction and the public startup/inspection regressions were run before the fix, with the maintained checkout's `taktik.__file__` verified explicitly.

The reader now retains independently recognized detail context for a known author column missing its name, handle, or both text nodes.
The remaining handle's position relative to the viewport does not determine recovery eligibility.
Missing-text variants retain and validate remaining author badges; unknown badges do not gain recovery permission.
Neither the avatar description nor a quoted author supplies a main-post identity.
Malformed identity layouts and unknown page structure remain unsupported.
The captured Android navigation window is recognized by its native structure and bottom geometry, and remains an occlusion.

Entry restoration uses the existing safe downward gesture, with the same eight-attempt bound, exclusions, cancellation, deadline, and uncertainty handling.
Each subsequent read checks the thread, available source evidence, and native text continuity.
An unrevealed header requires progress before another attempt.
Back restoration now makes those checks as well and retains the original thread reference through temporary timestamp/header loss.
A regression reproduced a conflicting timestamp being accepted after that loss, then passed with the retained reference.

Inspection preserves previously verified entry evidence and accumulated character coverage when a later read omits or clips the header.
It continues intentional forward reading without restoring the header at every read.
The coverage regressions were also run against the baseline inspection implementation with the repaired reader: all three missing-text variants failed by losing the retained caption, then passed with the corrected inspection implementation.
Startup reaches supported Back/Home recovery and independently verifies the configured drawer account.
Missing author evidence grants no engagement permission.

## Evidence and validation

The reusable fixtures contain the full ordinary hierarchy and both independent native hierarchies, with synthetic identities, captions, counts, ages, timestamps, and personal system labels.
Comparison with the local originals confirms identical node structure, bounds, classes, packages, resource IDs, and control flags.
The original unsanitized parser reproduction now returns a detail page with an unavailable main post.
Both combined ordinary/native replays offer bounded safe restoration geometry.

The successful toolbar/Home/account continuation is synthetic.
The separate synthetic native detail visit verifies restored author/source attribution and return to the selected occurrence through the public browser and real Phone/TaktikDevice adapter with replayed transport.
No successful physical restoration sequence was captured, and no live device run or human visual acceptance is claimed here.
Raw captures remain local.

The final focused reader, native visit, inspection, and long-caption run passed 177 tests.
The final Python 3.12 X regression suite passed 2,067 tests.
The final browsing compatibility matrix passed 4,146 tests with two skips on each of Python 3.10.20 and 3.14.4, in 336.61 and 285.91 seconds respectively.
Both Python 3.10 and 3.14 source-to-wheel builds passed, and the distribution verifier matched all 39 wheel and 43 source-archive browsing/native-asset files to the corrected checkout.
Ruff, formatting, repository layout, whitespace, all 251 manifest-listed fixture hashes, and changed documentation links passed.
The repository compatibility commands are documented in [X operations](../x-operations.md#reproducible-compatibility-checks).
Local run logs and build artifacts are under `/tmp/taktik-header-recovery`.

## Downstream adoption

Publish the tested Taktik fix commit before consumer adoption.
Persona Engine's owner must update `taktik-install.json` at `source.commit` to that revision and publish an adoption commit after its checks.
Echoseek's owner must then update `pipeline-install.json` at `persona_engine.commit` to the Persona Engine adoption commit and reinstall through its existing workflow.
Recovery remains implemented in Taktik's reader and browsing modules.
