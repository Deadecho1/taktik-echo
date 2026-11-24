# Android navigation compatibility

Ben's live check reported `Unrecognized Android navigation bar content.` with an extra empty `com.android.systemui:id/nav_bar_widget` container and a `recent_apps` button labeled `Recents`.
The reader previously accepted neither that container nor that label; Moria's `Overview` label remains supported.

Synthetic variants of the existing captured drawer reproduce each difference independently and together through `XBrowser.start`, the real `Phone`, and `TaktikDevice` with fake raw transport.
Before the fix, all three variants fail with the reported navigation-bar error.
After the fix, each verifies the account, dismisses the drawer through the visible Android Back target, and observes the feed.

The reader recognizes the additional empty container and accepts only `Overview` or `Recents` for `recent_apps`.
Existing package, geometry, required-button, duplicate-button, and Back-visibility checks remain in place.
Drawer and keyboard/search tests confirm that the entire bottom navigation band stays excluded from X controls.
Negative cases reject unexpected widget text, descriptions, packages, children, and button labels.

The focused Android navigation and startup tests pass (30 tests).
These regressions use synthetic OEM variations, not a new capture or a new live check on Ben's device.
