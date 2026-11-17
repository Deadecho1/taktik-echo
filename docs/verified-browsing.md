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
The latter requires exactly one editable field in the foreground package and screen scope, excludes nested controls from the focus tap, and rereads the hierarchy throughout typing.
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
The browser verifies the account, supports For you, Following, and search, and exposes text-only post observations with separate quote and media metadata.
Only watch and skip are enabled; unsupported or ambiguous layouts stop browsing.
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
The local search validation record is `docs/validation/2026-11-17-x-search.md`; raw captures and screenshots remain local for human visual review.
An exact, unobscured native no-results panel establishes an empty search; missing result posts alone do not.
Consumer applications choose how to use these capabilities in their own workflows.
Their configuration, model policy, and integration schedules are independent of Taktik implementation and validation.
