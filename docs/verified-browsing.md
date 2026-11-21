# Verified native browsing

The browsing services expose account-verified Android interaction to consumers without depending on a persona engine.
Instagram and TikTok readers live in their respective `ui/posts.py` modules, with navigation and action verification under `services/browsing/`.
The readers reuse the existing selector catalogs, snapshot infrastructure, bounds parser, and Instagram framed-post interpretation.
Additional supported layouts and attribution checks are maintained in these platform modules.

`taktik.core.shared.browsing.PostObservation` carries the observed author, text, identity, media metadata, and optional frames.
Its elapsed time is supplied by the consumer that tracks time spent viewing the post.
The module also exposes supported workflows and actions so consumers can reject unavailable operations before execution.
It contains no model policy, learning, persona configuration, or retained history.
`EmptySearchResults` identifies an explicit, stable empty-results screen during search navigation.
It is distinct from an unreadable screen, unavailable result controls, or uncertain phone execution.
Consumers may choose a different query after that outcome; Taktik does not choose search interests.

`taktik.core.shared.phone_interaction.Phone` owns a single device session and uses the existing Taktik device, gesture, and keyboard helpers.
Mutations return a result that must be checked, and uncertain execution must not be blindly retried.
Account and post-state verification remain the platform service's responsibility.
App startup and package-scoped URL opening check the installed version against the exact pins in `taktik/core/shared/device/apps.py`.
TikTok permits `43.1.4` and `47.0.3`; Instagram permits `410.0.0.53.71` and `447.0.0.55.81`.
Apps without a pin and unreadable or mismatched versions refuse automation with `APP_VERSION_REFUSED`.
The Phone API returns a failed result with that explanation before attempting the app command.
Version checks are fresh at startup and relaunch; selector overrides never grant permission for an unpinned build.
Stop, home, and session cleanup remain available after a refusal.
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
