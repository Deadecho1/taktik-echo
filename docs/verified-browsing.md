# Verified native browsing

The browsing services expose account-verified Android interaction to consumers without depending on a persona engine.
Instagram and TikTok readers live in their respective `ui/posts.py` modules, with navigation and action verification under `services/browsing/`.
The readers reuse the existing selector catalogs, snapshot infrastructure, bounds parser, and Instagram framed-post interpretation.
Additional supported layouts and attribution checks are maintained in these platform modules.

`taktik.core.shared.browsing.PostObservation` carries the observed author, text, identity, media metadata, and optional frames.
Its elapsed time is supplied by the consumer that tracks time spent viewing the post.
The module also exposes supported workflows and actions so consumers can reject unavailable operations before execution.
It contains no model policy, learning, persona configuration, or retained history.

`taktik.core.shared.phone_interaction.Phone` owns a single device session and uses the existing Taktik device, gesture, and keyboard helpers.
Mutations return a result that must be checked, and uncertain execution must not be blindly retried.
Account and post-state verification remain the platform service's responsibility.
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

## X extension

The `feature/x-platform` branch adds `taktik.core.social_media.x.ui.screen` and `taktik.core.social_media.x.services.browsing.XBrowser`.
The interpreter consumes captured XML and recorded screen dimensions.
The browser verifies the account, supports For you, Following, and search, and exposes post observations with separate quote and media metadata.
Watch, skip, explicit media inspection, and verified inline text expansion are enabled; unsupported or ambiguous layouts stop browsing.
Native Paid partnership disclosures remain separate from authored text.
The captured leading name/Verified/age header without a handle can retain a body
and media as an unattributed fragment for ordered continuity. It requires an
unobscured header and body, a recognized layout, and independently verified
movement. Display names never supply an author or a new post observation.
Engagement, promoted-placement recognition, and further physical validation remain unfinished.
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
The reviewed Top run ends at its last partly visible video, so it does not establish a subsequent physical scroll from that position.
An exact, unobscured native no-results panel establishes an empty search; missing result posts alone do not.
Consumer applications choose how to use these capabilities in their own workflows.
Their configuration, model policy, and integration schedules are independent of Taktik implementation and validation.

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
The source is reverified after OCR and the expanded result is read again before success.
Support requires an unquoted source, unchanged author/header position and media content, and an unobscured expanded body entirely inside the viewport.
Missing or ambiguous OCR targets are not tapped; clipped expansion, changed context, and uncertain execution invalidate browsing for explicit recovery.
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
