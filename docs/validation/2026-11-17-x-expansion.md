# Native X inline text expansion

`X.read_more()` now verifies native inline expansion of an unquoted post whose expanded body fits unobscured within the viewport.
`XBrowser.read_more(observation)` and `act("read_more", observation)` expose the behavior while preserving the selected occurrence identity.
The new observation has the expanded native caption, its new content key, and `caption_expanded=True`.
An already complete caption is a verified no-op.

Milestone 2 remains partial: the separate native detail screen still omits its main author, body, and media.
Its `main_post=None` and `main_verified=False` remain unchanged, and bounded thread inspection never claims complete coverage.

## Evidence and implementation

Opening the post and activating its inline Show more span reach different native surfaces on X `12.42.0-prod.01`.
Show more expands the body inside the existing search results and preserves the independently readable author/header.
Opening the detail screen still produces empty main-content accessibility views.
Uncompressed hierarchy depths 50 and 100 and direct author, text-prefix, and author-description queries all failed to expose the main detail content in the OpenAI probe.
The same direct queries succeeded on the inline expanded source.

The inline control has no separate accessibility node.
The implementation locates a unique, high-confidence Show/more word pair at the end of the source body with the existing local Tesseract helper.
Both words must be inside the unobscured body, share a line, and avoid nested controls and other content.
OCR supplies only the control location; expanded text, authorship, media metadata, and visibility come from native XML.
The screenshot stays local and is never submitted to a model by this operation.

The source is refreshed after OCR and before the single tap.
The resulting native post must preserve the exact source prefix, author/header geometry, context, media content, and action states while exposing additional text.
The full expanded body must be observable, and a second read must confirm the selected result.
Browser identity retains the original occurrence key while `source_key` reflects the expanded content.
Existing media inspection frames are discarded after expansion because the media may have moved.
Search/workflow changes and advancement reset expansion state.

Clipped bodies, quoted posts, missing or ambiguous OCR targets, changed context, and uncertain execution fail explicitly without retrying the tap.
Failures invalidate browsing for explicit recovery.
This does not establish traversal of arbitrarily long expanded posts or full text behind shortened native links.

## Physical validation

The implementation run `20261117T134201.601008Z` used the existing coordinated Pixel 4a Phone session, verified the X account, searched Latest for `from:OpenAI -filter:replies`, and selected the healthcare post.
It called the implemented `X.read_more()`, verified the fully observable expanded body, called `inspect_thread(max_scrolls=0)`, and returned to the same expanded post and geometry.
The run passed, verified Taktik Keyboard during query entry, restored the initial keyboard, and completed Phone cleanup.
Existing controller reservations, persona/device locks, cancellation, and the 240-second session deadline remained in force.
No phone session remains active from this run.

The preceding discovery probe `20261117T133437.381266Z` recorded the equivalent inline expansion, deeper hierarchy/direct-node comparison, and native detail return.
Probe `20261117T133144.571820Z` captured a much longer Lunar post expanding inline; its XML retained offscreen text, which remained incomplete and unobservable under the existing reader contract.
That probe stopped for evidence review after discovering the inline surface and completed cleanup; it is not counted as an implementation round trip.

The first probe, `20261117T132929.954464Z`, stopped before tapping because the shared OCR parser swallowed subsequent TSV rows after a literal quotation mark.
The captured failure was reproduced with the real local Tesseract output, then minimized into regression cases.
Both OCR location and text extraction now treat quotes as literal TSV content.
The original captured OCR check passed after the fix.
Tesseract `5.3.4` and its English data were extracted into `/tmp` for these checks; system and consumer dependencies were not changed.

Raw captures, direct-query records, and events remain local under ignored `tests/smoke/x-expansion-probes/` and `tests/smoke/x-expansion-runs/`.
The [fixture package](../../tests/unit/social_media/x/fixtures/expansion/README.md) contains eight XML captures and the control word boxes, with source hashes.
The user reviewed five original screenshots through the requested private Lavish page on their Tailscale-connected phone.
The submitted OPENAI verdict was `looks_correct`, covering the implementation run's source, expanded, and return captures.
The submitted LUNAR verdict was `looks_correct`, covering the discovery probe's source and expanded captures.
Both submitted IDs and all five presented captures are accounted for in the local receipt `.lavish/feedback/expansion-verdicts.json`, with original source paths and hashes.
These approvals do not cover the separate OpenAI discovery/detail screenshots or earlier inspection/gallery captures, and do not establish visibility of the Lunar post below the screen.
Browser checks at 360, 390, 768, and 1280 pixel viewport settings verified image loading, control behavior, and absence of horizontal overflow; no screenshot was loaded into the coding conversation.

## Regression checks

The final shared/X/Instagram-service/TikTok-service suite passed **3,070 tests, with 2 skipped**, after the review fixes.
The new X expansion checks cover successful expansion and detail return, occurrence identity, stale metadata, caption-state reset, source/context/geometry changes, missing or duplicate controls, final reread drift, cancellation, deadlines, uncertainty, and clipped content.
Six shared OCR regression cases cover literal opening, closing, and standalone quotation marks.
Ruff lint/format checks, the tree-layout audit, and Git whitespace checks passed.
Standards and Spec reviews reproduced two exclusion defects: a control moving over the target during OCR, and a native control occupying exactly the body's rectangle.
Two new failing Phone replays locked down both cases before correction.
The implementation now rebuilds exclusions from the refreshed post and removes only one body-text rectangle, preserving any coincident control.
Standards follow-up: both defects are resolved, with no unresolved findings.
Spec follow-up: all 30 focused expansion/parser checks passed, with no remaining correctness findings within the supported inline-expansion scope.
Main-detail extraction and longer-than-viewport reading remain explicitly incomplete.
Publication status is recorded in the local `plan.md`.
