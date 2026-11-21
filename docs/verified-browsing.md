# Verified native browsing

The browsing services expose account-verified Android interaction to consumers without depending on a persona engine.
Instagram and TikTok readers live in their respective `ui/posts.py` modules, with navigation and action verification under `services/browsing/`.
The readers reuse the existing selector catalogs, snapshot infrastructure, bounds parser, and Instagram framed-post interpretation.
Additional supported layouts and attribution checks are maintained in these platform modules.

`taktik.core.shared.browsing.PostObservation` carries the observed author, text, identity, media metadata, and optional frames.
Its elapsed time is supplied by the consumer that tracks time spent viewing the post.
Optional `native_post_id` and `post_url` fields carry independently verified native identity and remain separate from local observation and content keys.
The module also exposes supported workflows and actions so consumers can reject unavailable operations before execution.
It contains no model policy, learning, persona configuration, or retained history.

`taktik.core.shared.phone_interaction.Phone` owns a single device session and uses the existing Taktik device, gesture, and keyboard helpers.
Mutations return a result that must be checked, and uncertain execution must not be blindly retried.
Account and post-state verification remain the platform service's responsibility.
Explicit controlled scrolls honor the requested distance even below the calibrated swipe floor.
Vertical travel must be finite and at least one pixel, and sampled paths must satisfy the requested reach and usable-region checks before injection.
Explicit controlled requests and prepared paths must also meet a conservative minimum of 3.2% of full screen height, rounded up, using the existing drag-departure clearance.
This is a host policy rather than a queried Android touch-slop value; smaller requests fail without enlargement or tap-sized injection.
Path-validation failures retain their specific reason, while uncertain execution still prevents automatic retry.
Gesture execution alone does not establish movement of the application's content.
Pass deadlines and cancellation to the same Phone object and close it before releasing its device lock.
The device lock retains the established cross-process path under the system temporary directory.
Current text entry requires Taktik Keyboard and preserves its bounded typing and restoration behavior.
`Phone.enter_text` accepts a resource ID or `TextField(package, scope_resource_id)` for a native field without a resource ID.
The latter requires exactly one editable field in the foreground package and screen scope, checks its bounds through every ancestor, excludes nested controls from the focus tap, and rereads the hierarchy throughout typing.
Ambiguous fields, obscured targets, changed scope, lost focus, or inexact text prevent submission.

Platform evidence capture and public URL interpretation live in `taktik.core.shared.browsing_evidence` and `taktik.core.shared.post_urls`.
Evidence capture verifies the observed post before opening Share and restores the browsing context afterward.
Consumers own the resulting dataset, retention policy, and relevance decisions.

Future platform and device capabilities should reuse or extend these Taktik implementations.
Consumer applications should not duplicate selectors, screen parsing, or gesture execution.

The shared Phone implementation and verified Instagram/TikTok browsing are maintained on `main`.
The X extension builds on that shared implementation in `feature/x-platform`.
Consumers pin a tested complete commit hash; branch names describe the development line.
The [X operational guide](x-operations.md) records supported device/runtime versions, session ownership, recovery rules, and the reproducible compatibility and distribution checks.

## X extension

The `feature/x-platform` branch adds `taktik.core.social_media.x.ui.screen` and `taktik.core.social_media.x.services.browsing.XBrowser`.
The interpreter consumes captured XML and recorded screen dimensions.
The browser verifies the account, supports For you, Following, and search, and exposes post observations with separate quote and media metadata.
Watch, skip, explicit media inspection, verified inline text expansion, and native engagement are enabled; unsupported or ambiguous layouts stop browsing.
Native Paid partnership disclosures remain separate from authored text.
The captured leading name/Verified/age header without a handle can retain a body
and media as an unattributed fragment for ordered continuity. It requires an
unobscured header and body, a recognized layout, and independently verified
movement. Display names never supply an author or a new post observation.
Single-account and plural native media-tag labels are recognized beneath outer media and remain separate from caption and author attribution.
The reader checks their native structure, accessibility, geometry, and complete action-row boundary; tagged display names never supply an inferred handle.
Clipped or occluded tag labels remain excluded from observation context.
Promoted-placement recognition remains unfinished.
This feature builds on the shared browsing implementation on `main`.

Search starts with drawer account verification, opens Explore and the scoped query field, and submits only after exact text and X screen-context verification.
`XBrowser(phone, {"search"}).start(username, "search", target=query)` opens Top results.
The lower-level `X(phone).start(username, "search", query=query, result_tab="latest")` also supports Latest.
`X.search(query, tab="top")` starts another account-verified search from an active session.
Queries preserve Unicode and native X operators; empty queries and control characters are rejected before device interaction.

Expanded search screens verify the exact query and selected result tab.
When scrolling hides the query header, the reader leaves the query unknown and the browser retains its prior verified context only across its own movement-verified scrolls.
The selected result tab remains visible and checked, and refresh preserves the selected post's identity, content, and geometry.
Startup restores a retained collapsed header through bounded downward scrolling and rereads the exact query before observation.
Result scrolling reuses the existing post-continuity, native-text movement, exclusion geometry, and bounded-advance checks.
Search observations retain `search_query` and `search_tab` separately in `post_context`.
Explicit recovery repeats account verification and the query; it establishes a new position.
Returning to a Home workflow also establishes a new position and does not claim restoration of the previous post.

Search is covered by captured XML and Phone replays from X `12.41.0-prod.01` and `12.42.0-prod.01`, Android 13, English UI, at 1080 × 2340.
The no-resource-ID typing path additionally covers keyboard restoration, cancellation, deadlines, ambiguity, focus loss, and uncertain execution through the real shared keyboard helpers with a simulated device.
Direct physical runs on `12.42.0-prod.01` passed Top and Latest search with two advances each, plus a native empty-result search; each run verified Taktik Keyboard and restored Gboard during cleanup.
The local search validation record is `docs/validation/2026-11-17-x-search.md`; the user visually confirmed all twelve presented search screenshots on 17 November 2026.
That review covers the seven successful result captures and five entry/layout references; the additional expanded-header fixture was not presented and remains outside visual sign-off.
Post text can be observable while its video extends below the viewport; `body_complete` describes authored text and does not assert complete media visibility.
The original reviewed Top run ends at its last partly visible video.
A subsequent direct `astronomy filter:videos` run covered the same relevance-prompt/partial-video layout and three verified outgoing movements to an independently observed successor, using current search results.
Direct Latest browsing also traversed two pending long-text phases and their video tails, reaching a real successor after 23 gestures.
A fully hidden native header that has lost its age label can retain its clipped text as an unattributed passage; it supplies no new author or post observation.
Collapsed Home also retains the exact native body/GIF structure before its footer appears, including the offscreen placeholder and captured inert renderer.
The unique unchanged caption can enter pending continuity when the GIF is offscreen or appears with the first visible lower text edge.
Pending continuity does not prove movement or complete the caption; two usable lower-edge frames and independent ordered alignment are required before selecting an observable successor.
The physical caption/GIF continuation completed seven gestures with a reverified exit and a new observable successor.
The eight-attempt pending/no-progress bounds and 32-gesture total bound remain unchanged.
Verified ordered removal of a preceding post resets the no-progress counter only while the selected source remains uniquely aligned by its exact content key.
Moving within that source or losing it alone does not earn this reset, and successor selection still requires an independently observable post.
The [layout coverage record](validation/2026-11-20-x-layout-coverage.md) documents these runs, native media tags, and the outstanding ad-placement and visual-review limits.
An exact, unobscured native no-results panel establishes an empty search; missing result posts alone do not.
Consumer applications choose how to use these capabilities in their own workflows.
Their configuration, model policy, and integration schedules are independent of Taktik implementation and validation.

`XBrowser.act(action, observation)` supports `like`, `save` (Bookmark), `follow`, `unfollow`, and `not_interested`.
The lower-level `X` exposes `set_liked(selected=True)`, `set_bookmarked(selected=True)`, `follow()`, `unfollow()`, and `not_interested()`.
The setters also accept `False` for explicit removal; an already matching native state is a verified no-op.
Low-level operations return `EngagementResult` with the source content key, whether the state changed, the verified selected state when applicable, and whether browsing advanced.
Observations expose `post_context.engagement.liked` and `post_context.engagement.bookmarked`; missing native evidence remains unknown.

Like and Bookmark states come from native `Like`/`Undo Like` and `Bookmark`/`Delete Bookmark` labels.
The reader retains their canonical action names for post continuity and requires visible native state evidence before engagement.
Follow/unfollow opens the selected outer author's menu and requires its exact handle and relationship state before acting.
The installed version's options hitbox includes padding that opens adjacent Grok or the post, so taps use its right half within the observed author-header band.
Mutations are issued once, followed by bounded rereads and a final verification.
Temporary animation and confirmation overlays do not prove success.

On X `12.42.0-prod.01`, Unfollow and Not interested replace the selected post with a native receipt and an Undo control.
The receipt must identify the selected author at the original header position, and the selected post must be absent.
The service rereads that evidence before selecting another independently observable post, recording an engagement removal in `navigation_gaps`.
`ActionResult.advanced` is then true; callers must not advance again for the completed action, and the old observation cannot authorize another engagement.
Successor framing can scroll the receipt out of view, so callers cannot assume Undo remains available after this action returns.
The maintained evaluation helper `check_feedback_roundtrip` shares native feedback confirmation, verifies a fresh unique Undo receipt, and restores the original occurrence before successor framing.
It credits only a verified feedback/Undo round trip; it does not change the public action's advancement contract.
Not interested is offered by the captured For you menu; the captured search menu does not offer it.
The service dismisses an unavailable menu without engaging and reports `Status.UNSUPPORTED`.
Unknown outcomes invalidate browsing and raise `Status.UNCERTAIN`; recover explicitly without replaying the engagement.
Account verification, deadlines, cancellation, reservations, locks, keyboard restoration, and cleanup use the existing Phone session.
The [engagement validation record](validation/2026-11-19-x-engagement.md) records physical evidence and remaining review limits.

`X.copy_link()` returns the selected outer post's native `PostLink(source_key, author, post_id, url)` after a verified Share/Copy link round trip.
`XBrowser.copy_link(observation)` also checks the observation identity and supplies `native_post_id` and `post_url` on subsequent observations of that occurrence.
The operation is explicit; ordinary observations leave these fields unknown.
It copies to the Android clipboard, requires a fresh native clipboard receipt after an independently checked Share sheet, matches the outer author, and verifies the original post and browsing context again.
Repeated copies of the same URL require a new receipt; a retained clipboard string alone is insufficient.
Share keeps its native clickable wrapper and glyph geometry separately, and uses the owned glyph's uncovered area when it meets the existing minimum tap dimensions.
The supported horizontally clipped Share glyph can instead use a narrow right-hand strip only when a single native cover meets its exact left edge and spans its full height; the strip stays inside the wrapper, within the glyph's vertical band, at most one glyph-height wide, and includes retained glyph pixels.
Malformed geometry, ambiguous or inconsistent cover relationships, and insufficient uncovered space reject before tapping; opening Share is never retried after an unverified outcome.
Only Copy link and sheet dismissal are used, with no OCR, network URL resolution, recipient selection, or external sharing.
The native ID never replaces a local content or occurrence key, and advancing, starting again, successor selection, or caption expansion clears the retained link.
Missing or obscured Share controls, unrecognized clipboard receipts, changed sources, and uncertain execution invalidate the attempt without blind retries.
Explicit startup can dismiss a retained recognized Share sheet and reverify the account.
The clipboard preview value is receipt metadata, and its window remains an occlusion for underlying post text and gestures.
If that preview covers the selected source, Copy link retains the validated receipt and checks source return up to eight times with one-second readiness waits between checks.
Receipt disappearance does not discard the captured URL; a changed URL or source/context rejects the operation.
Success still requires an independently observable source and a final reread of the original occurrence.
The wait uses Phone cancellation and deadlines; timeout invalidates browsing and preserves single-attempt, exception-preserving cleanup.
After an observed receipt, a stationary refresh can wait through its captured empty-window dismissal shape for up to eight reads with 0.3-second readiness intervals.
Every read checks the original source and browsing context; the empty window keeps its occlusion and supplies no receipt, observation, or action target.
The refresh succeeds only after an independent read establishes that the window is gone and the selected post is observable.
Unknown windows, changed evidence, and exhausted bounds invalidate browsing, while unsupported hierarchies retain their reader diagnostics.
The [native link validation record](validation/2026-11-19-x-links.md) documents the successful repeated-copy phone run, supported device/version, regression checks, and completed human review of all nine presented screenshots.

`X.visit_profile()` visits the selected author's verified profile and returns header text and observable profile posts separately from the source post.
`X.inspect_thread(max_posts=10, max_scrolls=4)` returns bounded, independently attributed thread observations and native detail metadata, retaining the original source content key separately.
The detail reader independently extracts the main author, caption, media, and supported quoted content from native accessibility.
`detail.main_post` remains separate from reply `posts` and from the source content key.
`main_verified` requires a source match and an observable main-post snapshot; missing or clipped content remains explicit.
The result never claims complete thread coverage.
`main_text` contains the observed caption prefix, and `main_text_complete` becomes true only when the complete caption fits visibly or its native character positions have been covered across verified scrolls.
A long caption can therefore be completely read while `detail.main_post.body_complete` and `main_verified` remain false for its clipped initial snapshot.
This preserves the snapshot visibility contract without presenting offscreen text as observed.
`max_scrolls=0` performs an initial detail visit without forward scrolling.
The temporary `Phone.read("screen_reader_hierarchy")` operation uses the session-owned UIAutomator service, requests native screen-reader semantics, and restores the service and configuration before returning.
Ordinary reply nodes are retained only when the paired detail timestamp, controls, and geometry agree.
This content-reading path does not use OCR.
The [native detail validation record](validation/2026-11-17-x-detail-evidence.md) documents supported layouts, long-text evidence, packaging, and limits.

`X.read_more()` activates the native inline Show more span and returns the independently parsed expanded post.
`XBrowser.read_more(observation)` and `act("read_more", observation)` retain the observation identity across the verified text change and mark the next caption expanded.
The content key changes with the expanded text, and previously captured media frames are discarded because their geometry may have changed.
Local Tesseract OCR locates the inline control; authored text and attribution still come from native XML.
Recognition includes lower context capped at 1% of the screenshot's shorter side, rounded up and clipped to the image.
Each confident word must retain at least three quarters of its height inside the native body, with full horizontal and upper containment, consistent line geometry, and clearance from the recognition crop's lower edge.
The unique pair must belong near the body's lower edge; only the intersection of `more` with the unchanged native body is actionable, subject to fresh control exclusions.
The source is reverified after OCR and the expanded result is read again before success.
Verified added text may replace the Show more label without increasing body height; a shrinking body, changed prefix, or absence of added text still fails verification.
Support requires an unquoted source, unchanged author/header position and media content, and an unobscured expanded body entirely inside the viewport.
Missing or ambiguous OCR targets are not tapped; clipped expansion, changed context, and uncertain execution invalidate browsing for explicit recovery.
`XInlineExpansionLimit`, exported with `XBrowser`, identifies the narrower case where the source header, prefix, body origin, context, controls, and overlays remain verified while the expanded body extends below the viewport.
It permits missing media/footer evidence only when those elements followed the original body and the expanded body now pushes them below view.
The body must remain accessible and its visible bounds must equal its intersection with the content viewport; unexpected ancestor clipping does not qualify.
The exception does not establish full text or offscreen media completeness.
Other clipping, changed content, or uncertain execution retains its existing failure semantics.
`XBrowser.recover()` rechecks the saved account, timeline, query, and result tab through the same Phone, clears retained caption/link/media state, and creates a new occurrence.
If Home startup exhausts its four initial framing attempts, it can reveal the verified timeline controls, tap Home once, and repeat the same bounded framing search.
The returned observation records `home_reset` in `navigation_gaps`, with post continuity explicitly unestablished.
This can abandon a retained expanded caption; it does not complete that caption or restore its original occurrence.
Search startup, engagement successor selection, and unexpected framing errors do not use this reset.
An ineffective reset, uncertain tap, cancellation, or deadline still terminates the operation without another reset attempt.
An observation from before recovery cannot be used to act on that new occurrence, even if the same post reappears.
An already complete caption is a verified no-op.
The [expansion validation record](validation/2026-11-17-x-expansion.md) documents the physical inline expansion/detail-return run and the remaining visibility limits.

`X.inspect_media(index=0, frame_count=1, interval=1.0)` captures a verified native image gallery or the uncovered, visible part of an inline video/GIF.
It verifies source or gallery evidence around each frame and reports the crop and whether the inline media is partial.
The gallery's caption metadata can retain text beyond the visibly shortened caption and is never presented as expanded text.
`XBrowser.visit_profile(observation)`, `inspect_thread(observation, ...)`, and `inspect(observation, ...)` also validate the source observation identity.
Explicit media inspection supplies frames and `post_context.media_inspection` on the next observation while retaining its identity and caption.

Successful visits verify the prior browsing context and selected occurrence after native Back navigation.
A retained detail position is first framed until its native main-author header is visible.
Missing Back headers are restored within a fixed gesture bound using a continuous control-free path long enough to expand the collapsed toolbar.
Uncertain actions are not retried, and failed verification requires explicit recovery.
Direct profile/detail/gallery and thread/video round trips passed on X `12.42.0-prod.01`, Android 13, at 1080 × 2340, with keyboard restoration and cleanup.
The [inspection validation record](validation/2026-11-17-x-inspection.md) documents limits, captured evidence, and pending human visual review.
