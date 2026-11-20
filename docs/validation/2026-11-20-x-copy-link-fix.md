# X Copy link source-return fix

The 20 November soak stopped when Android's clipboard preview covered the unchanged selected post near the bottom of the For you viewport.
Copy link had already produced a fresh native URL, but immediate source verification rejected the covered body before the preview expired.
The parser's occlusion rejection was correct; the workflow needed to retain the receipt while waiting for independent source visibility.

## Behavior and limits

Copy link now retains the validated `PostLink` and waits for the original source using the existing readiness helper.
Only this source-return wait uses one-second intervals, with eight reads and at most seven seconds of scheduled waiting plus device-read time.
Other readiness calls retain their existing interval and attempt count.
Every source-return read rejects a changed receipt, ambiguous or changed source identity/content/geometry, or changed browsing context.
Pure alignment of the original and current source runs even while the body is covered, so temporary header or body shifts cannot be waited through.
The final observable source must pass the existing occurrence/alignment checks and an independent reread before the link reaches the caller.
Receipt disappearance after capture preserves the evidence; another URL cannot replace it.
Copy link is never repeated to recover visibility.
Phone deadlines and cancellation remain active during the wait, and existing narrowly scoped cleanup preserves the primary failure if restoration fails.
Unobservable sources beyond the bound still invalidate browsing without returning a link.

## Captured reproduction and regressions

Before the fix, both the original local replay and the permanent captured regression raised `XError: Copy link did not return to the selected X occurrence.`
After the fix, the original replay passes through the real `Phone`, `XBrowser.copy_link`, and X service with the same source key and occurrence and exactly one Copy link tap:

```bash
../persona-engine-x/.venv/bin/python tests/smoke/replay_soak_copy_failure.py \
  tests/smoke/x-soak-runs/20261120T074807.351791Z
```

Five sanitized XML fixtures preserve the source, Share sheet, fresh receipt, retained coverage, and unobscured return.
Their [manifest](../../tests/unit/social_media/x/fixtures/links/manifest.json) records original and sanitized SHA-256 hashes; the new captures retain pending human visual review.
The permanent [Phone regressions](../../tests/unit/social_media/x/services/browsing/test_links.py) cover the captured sequence, a six-second preview with instantaneous reads, the final permitted read, permanent occlusion, receipt disappearance, changed receipts/sources/context, ambiguity, repeated copies, cancellation/deadlines, and primary failures combined with restoration failure.
The timing regression first failed with the ordinary 0.3-second readiness interval, confirming that fast device reads need a longer interval for this overlay.
The combined original and new link suites pass all 64 cases; the combined link/parser check passes 121 cases.
The review follow-up first reproduced temporary header/body movement escaping validation, then added alignment on every read and six regression cases.

## Compatibility and review

The final Python 3.10 and 3.14 runs each passed 3,385 checks with two skips across shared Phone, X, Instagram/TikTok services, distribution verification, and package metadata/requirements.
Both runtimes built a wheel from the source archive and verified exact checkout contents for 38 wheel files and 42 source-archive files.
All 155 versioned fixture hashes and all 13 original/fixture link capture pairs match.
Ruff lint/format, the repository tree audit, and Git whitespace checks pass.
Independent Standards and Spec follow-up reviews have zero unresolved findings after the geometry correction.
The pre-existing engagement validation document change remains outside this fix.

## Physical validation still required

This fix is verified against captured device responses and automated tests; no new phone session was started.
The user will rerun the requested three-hour validation after publication.
The original soak's incomplete feature coverage, native-ad evidence, and pending human screenshot review remain open.
The original session was closed with keyboard restoration and lock release, as recorded in the [soak findings](2026-11-20-x-soak.md).
