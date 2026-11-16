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
The browser verifies the account, supports For you and Following, and exposes text-only post observations with separate quote and media metadata.
Only watch and skip are enabled; unsupported or ambiguous layouts stop browsing.
Native Paid partnership disclosures remain separate from authored text.
The captured leading name/Verified/age header without a handle can retain a body
and media as an unattributed fragment for ordered continuity. It requires an
unobscured header and body, a recognized layout, and independently verified
movement. Display names never supply an author or a new post observation.
Search, engagement, promoted-placement recognition, and further physical validation remain unfinished.
This feature builds on the shared browsing implementation on `main`.
