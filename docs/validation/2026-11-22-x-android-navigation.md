# X startup with Android navigation buttons

X 12.42.0-prod.01 on Android 16 exposed a bottom System UI navigation window
that the X reader incorrectly sent to the clipboard reader. At the existing
1440 × 3216 resolution and 640 density override, the X account drawer filled
the width and exposed no close scrim. These are supported layouts; device
settings do not need to change.

The reader now validates the native Back/Home/Overview navigation structure,
including the keyboard's optional input-method switcher, and excludes the
entire bottom band from X targets. Covered Back buttons are not exposed as
touch targets. Unknown or duplicate System UI windows still fail closed.
A full-width drawer requires its visible account header and menu structure.
Startup revalidates the account before dismissing it using the visible native
Back button, or the existing Phone Back command when no button is available.
The resulting Home screen must still be verified. Uncertain actions propagate
without repetition.

Sanitized captures in `tests/unit/social_media/x/fixtures/startup/` preserve
the native drawer, keyboard and navigation geometry. Public XBrowser tests
exercise real Phone/TaktikDevice dispatch, wrong or changing accounts, uncertain
touches, and failed dismissal. Existing scrim-based drawer behavior is preserved.

A live search-only check on the unchanged device verified the configured account,
entered a query, and returned a search observation. It performed no engagement.
