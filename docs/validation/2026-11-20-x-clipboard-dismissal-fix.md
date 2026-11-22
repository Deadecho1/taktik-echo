# X clipboard-dismissal continuation fix

The 20 November validation restart copied a post link successfully, then stopped during the next stationary refresh when Android retained an empty System UI window while dismissing its clipboard preview.
The X subtree and selected post were unchanged.
Receipt parsing rejected the empty window, and navigation masked that unsupported read with a misleading Home-controls error.

## Behavior

The pure reader keeps an inert empty System UI window unsupported and exposes separately parsed underlying evidence with the window's occlusion intact.
It supplies no receipt, observable post, controls, or scrolling targets on the unsupported result.
After a previously observed valid clipboard receipt, the stationary browser refresh can wait for dismissal when the empty window retains the previous top, right, and bottom edges and only retracts its left edge.
This geometry authorizes bounded rereads only.
It never authorizes an action or establishes a fresh clipboard receipt.

The wait allows eight reads, including the initial transient read, separated by at most seven 0.3-second Phone readiness waits.
Every read independently checks foreground app, browsing context, selected source uniqueness, author, content, and geometry.
Copy link return and dismissal share the same source verifier, including every nested native visibility rectangle while allowing coverage and readability to change.
Changed receipts or exposed account evidence fail verification immediately.
The prior selection remains unchanged during the wait, and the current screen must establish that the external window is gone before observation resumes.
The existing final refresh still requires an observable source and preserves the browser occurrence and verified link.
Cancellation, expiry, and transport uncertainty propagate through existing cleanup without repeating Copy link.
Unsupported hierarchies report the reader's reason before any comparison of Home or search header state.

## Reproduction and coverage

Before editing production code, the original captured Phone/browser replay reproduced `XError: X Home controls changed outside adapter scrolling.`
The new permanent regression failed with the same error before the fix.
Both original captured reproductions now pass with the same source and occurrence and exactly one Copy link tap:

```bash
../persona-engine-x/.venv/bin/python tests/smoke/replay_soak_clipboard_dismissal.py \
  tests/smoke/x-soak-runs/20261120T094336.645235Z
../persona-engine-x/.venv/bin/python tests/smoke/replay_soak_copy_failure.py \
  tests/smoke/x-soak-runs/20261120T074807.351791Z
```

Five sanitized XML fixtures preserve source, Share sheet, receipt, empty dismissal window, and clean return.
The [fixture manifest](../../tests/unit/social_media/x/fixtures/links/manifest.json) records original and sanitized SHA-256 hashes and keeps human visual review pending.
The captured replay's five successful receipt reads remain unchanged; the failing refresh now reads the empty window and independently rereads the clean Home capture.

The [link regressions](../../tests/unit/social_media/x/services/browsing/test_links.py) cover the captured transition, recovery on the final allowed read, persistent and unknown windows, source and context changes, ambiguous occurrences, fresh-receipt rejection, search query/tab checks, foreground changes, interrupted waits, and failed cleanup.
The [reader regressions](../../tests/unit/social_media/x/ui/test_inspection_screen.py) verify that external-window coverage remains in body visibility and gesture/tap exclusions, and that malformed or ambiguous windows stay unsupported.
The subsequent-scrolling regression combines the dismissal overlay with the existing search advancement fixture and its established 350-pixel shift.
That scrolling sequence is separate replay evidence, not a claim that the failed physical run selected a later post.

## Validation and publication

All 113 link regressions and the combined 180 link/parser cases pass.
The original covered-body Copy link reproduction also remains green.
Independent Standards and Spec follow-up reviews have zero unresolved findings.
The initial Spec review reproduced changes to body-left, body-bottom, and header-right edges escaping the existing alignment helper.
Six regression cases first failed, then passed after complete rectangle verification was shared across dismissal and Copy link return.
Both Python runtimes built wheels from source archives and verified exact contents for 38 wheel files and 42 source-archive files.
All 160 fixture hashes and 18 original/fixture link source pairs match.
Ruff lint/format, tree layout, and Git whitespace checks pass.
Python 3.10 and 3.14 each passed 3,444 shared/X/Instagram-service/TikTok-service and packaging checks, with two skips per runtime.
Publication targets `origin/feature/x-platform` and the existing [draft PR #1](https://github.com/Deadecho1/taktik-echo/pull/1).
The tested/published revision and its hosted CI results are recorded in the PR and local implementation plan.

## Pending physical validation

No new phone session was started for this fix.
The three-hour/all-feature rerun belongs to the user's next validation request after publication.
Native-ad evidence and human visual review remain open.
The failed physical session was closed, Gboard restored, and its locks released as recorded in the [restart findings](2026-11-20-x-soak-restart.md).
