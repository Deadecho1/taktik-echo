# X long-caption validation continuation

The all-feature workflow now handles a verified inline viewport limit through explicit account/context recovery while retaining incomplete text coverage for the original occurrence.
This fixes the validation workflow stop in run `20261120T110248.963317Z`, which reached the documented inline viewport limit after 727.788 seconds.
The inline visibility guard remains conservative, and the full three-hour phone validation remains pending.

## Behavior and evidence

`XInlineExpansionLimit` is an `XError` subtype emitted only after the expanded source's identity, prefix, header geometry, body origin, context, and unchanged controls/overlays have been checked.
Its bounded classification covers a body extending below the viewport with media/footer pushed out of view.
The body must remain accessible and its visible bounds must match the viewport intersection.
It still invalidates browsing and does not establish completeness of clipped text or offscreen media.
Other source/context changes, ambiguity, overlays, and uncertainty remain errors.

`XBrowser.recover()` uses the existing Phone and lower-level recovery to verify the saved account, timeline, query, and result tab.
It clears cached caption/media/link state and establishes a new occurrence.
The maintained `scripts/eval/x_caption_validation.py` alternates supported inline attempts with bounded native-detail reading and records each result separately.
The local soak calls this workflow and requires successful `read_more` and `native_long_caption` coverage independently.
A handled limit records both identities and `original_text_complete=false`, with no successful inline or native-text credit.

The original workflow replay first failed at the captured exception through `Soak.feature`, `XBrowser`, and the real Phone interface.
It now continues in under one second, with exactly one expansion tap and verified startup at a new occurrence.
The two permanent expansion fixtures retain source provenance and hashes.
Recovery uses separately captured startup/account screens; the 20 November stop did not capture a physical recovery of this particular post.
The original contract replay still reports `documented_limit_confirmed` and verifies that all 3,143 XML characters do not become an observable complete caption.

The separate native-detail regression reads 1,857 characters through eight measured scrolls and retains the original clipped main snapshot.
Zero-scroll inspection returns only its 727 observed characters and keeps completeness false.
The supported short inline replay preserves occurrence identity and changes the content key only after verified expansion.
Cancellation, expiry, account mismatch, uncertain tap/recovery, and cleanup uncertainty remain distinct outcomes.
Independent Spec review found that the initial classifier also admitted inaccessible bodies and ancestor clipping.
Three captured regressions reproduced those failures before the accessibility/intersection correction and pass afterward.
The composed workflow regression runs a handled limit, a separate complete native long-caption read, and a supported inline expansion; each earns only its own coverage and leaves the original limit's text incomplete.
Both original clipboard reproductions continue to pass with one Copy link tap each.

## Verification and publication

Python 3.10 and 3.14 each passed 3,472 shared/platform/packaging/workflow checks with two skips on the final implementation.
All 16 workflow checks, 38 inline-expansion checks, and both original clipboard reproductions pass.
Both runtimes built wheels from source archives, and exact distribution comparisons verified 38 wheel files and 42 source-archive files against the checkout.
All 162 X fixture hashes and 10 local expansion source hashes match.
Ruff, formatting, repository layout, whitespace, and final independent Standards/Spec reviews pass.
The final review has no remaining findings after the visibility-classification correction and shared browser cache reset.
The existing [draft PR #1](https://github.com/Deadecho1/taktik-echo/pull/1) records publication and hosted Python 3.10/3.14 CI for its current head.

No new phone session was started.
The complete three-hour/all-feature validation, native-ad evidence, and outstanding human visual review remain open.
No consumer dependency pins or sibling implementation were changed.
