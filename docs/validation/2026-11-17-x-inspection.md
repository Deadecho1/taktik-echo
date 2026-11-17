# X inspection continuation

Profile visits, bounded thread inspection, image-gallery capture, visible video/GIF capture, and verified return are implemented in the standalone Taktik fork.
Milestone 2 remains partial because native main-post detail extraction and text expansion are unavailable on the tested X version.
The browser does not advertise `read_more` or fill missing detail content from the source feed or a reply.

## Interface and evidence

`X.visit_profile()` reads the selected author's direct profile handle, header text, selected tab, and independently observable profile posts.
It rejects a different handle and explicit own-profile account evidence that conflicts with the verified session.
The profile's first post can have a different author, including a repost.

`X.inspect_thread(max_posts=10, max_scrolls=4)` opens the selected post through a free region outside text, links, media, and nested controls.
It returns a source content key, native detail metadata, independently parsed thread posts, a scroll count, and a stop reason.
The returned posts are observations from the opened thread; no parent/reply relationship or complete thread enumeration is inferred.
`main_post=None`, `main_verified=False`, and `complete=False` preserve the main-post and coverage limits.
`max_scrolls=0` reads only the initial detail surface.
The hard limits are 50 observed content keys, 8 forward gestures, and 8 gestures to restore a hidden Back header.
No-progress, insufficient geometry, or unverified movement ends collection without claiming completion.
Unknown screens and changed thread context fail the operation.

`X.inspect_media(index=0, frame_count=1, interval=1.0)` opens a supported image gallery or captures the visible part of an inline video/GIF.
Gallery verification requires the exact source author, native caption metadata, unique image description, stable crop, and uncovered identity/Back controls.
The gallery's full accessibility caption is used for matching only; it does not establish visibly expanded text.
Video/GIF frames exclude controls and carry a `partial` flag when the visible crop does not cover the media bounds.
Every frame is bracketed by fresh source or gallery verification, with at most six frames and five seconds between frames.
Screenshots stay local; capturing a frame does not send it to a model.

Each successful visit returns through the native Back control and rechecks the prior workflow, query/tab, selected content, and geometry.
Collapsed detail headers are restored through bounded downward scrolling before Back is tapped.
An uncertain action is not retried, and errors invalidate browsing for explicit recovery.
The caller retains the existing Phone, reservation checks, device/persona locks, deadline, cancellation, keyboard lifecycle, and cleanup ownership.

`XBrowser.visit_profile(observation)` and `inspect_thread(observation, ...)` additionally reject stale observation identities.
`XBrowser.inspect(observation, ...)` and `act("inspect", observation)` retain verified frames for the next observation of the same occurrence.
The observation identity and caption remain unchanged; `post_context.media_inspection` records the index, view, crop, and partial status.
Ordinary observation remains text-only until explicit media inspection.

## Direct device validation

Both successful runs used Nir's Pixel 4a, X `12.42.0-prod.01`, Android 13, English UI, and 1080 × 2340 dimensions.
They verified `@NirGalel`, held the existing persona/device locks, checked controller reservations, and ran with a 240-second Phone deadline.

- Image run `20261117T130331.439962Z` completed profile, initial detail, and two-frame gallery inspection from Latest results for `from:NASA filter:images -filter:replies`.
  Every visit returned to the original selected search post.
  The gallery crop was `(0, 724, 1080, 1617)`.
- Video/thread run `20261117T130556.304837Z` completed a profile visit and two verified forward thread movements from Latest results for `from:NASA`.
  Native text measured 358 and 309 pixels of forward movement, and a downward gesture restored Back before returning to the original post.
  It then advanced to the next source post and captured two inline video frames from `(176, 1358, 1047, 2076)`, explicitly marked partial.

Both runs verified Taktik Keyboard during query entry, restored Gboard, completed Phone cleanup successfully, and exited zero.
No phone session from these runs remains active.
Raw hierarchies, local screenshots/frames, events, and result records are under `tests/smoke/x-inspection-runs/RUN_ID/`.
Screenshots and frame pixels have not received human visual review.

Earlier probes established that rereading and scrolling do not expose the main detail author/body/media.
A native long press did not yield a reliable text-selection surface and can follow an inline link.
That diagnostic path is not part of the implementation.
Two probes stopped on uncertain Android Back results without retries; the implemented return uses native Back and bounded header restoration.
The resulting capture-only observations are not counted as successful implementation validation.

## Regression and review

The [inspection fixture package](../../tests/unit/social_media/x/fixtures/inspection/README.md) records sixteen XML sources and hashes.
Captured Phone replays cover source identity, query/tab restoration, Home return, profile account contradictions, gallery occlusion, hidden Back restoration, bounded thread progress, media capture, uncertainty, cancellation, deadlines, and explicit recovery.
The original X suite passed 1,261 tests before implementation.
The shared/X/Instagram-service/TikTok-service regression run passed **3,034 tests, with 2 skipped**.
The X suite passed **1,320 tests**, including 59 focused inspection checks.
Ruff lint/format, the tree-layout audit, fixture/source hashes, local image dimensions, and Git whitespace checks passed.
The existing oversized X test root was filed into reader, browsing, and mixed cases without changing test assertions; the audit's 40-file ceiling and baseline remain intact.
Publication status is recorded in the local `plan.md`.

Standards and Spec reviews found gallery-control occlusion, unsafe exclusion of nested unreadable main content, conflicting profile account evidence, and an overly strict Back-padding check.
Captured mutations reproduced each issue before the fixes.
Follow-up reviews report no unresolved correctness findings; the duplicate avatar-cover calculation now uses the shared inspection helper.
The remaining expansion requirement is recorded as incomplete, rather than treated as a review pass for the whole milestone.

Unsupported gallery variants, fully obscured media, absent safe touch regions, unverified return positions, and unavailable main detail content remain explicit limits.
Engagement and native post IDs/URLs remain separate milestones.
