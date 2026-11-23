# Native reader startup on Android 16

A live X search session could browse results but stopped progressing after opening
post detail. The isolated public `Phone.read("screen_reader_hierarchy")` call
reproduced a killed Android process. Its crash buffer recorded a null main Looper
in `AccessibilityInteractionClient` during the UiAutomation service callback.

The installed UIAutomator bridge prepares the main Looper when its context is
first resolved. The native reader now requests that context before constructing
UiDevice, ensuring initialization precedes accessibility callbacks. Preparing a
second Looper directly is incorrect because the bridge owns that initialization.
The existing temporary service flags, server restoration, watchdog, deadlines,
cancellation propagation and file cleanup remain in place.

`test_native_entrypoint.py` compiles and executes the real Java entry point
against a small Android API fixture. It checks both a fresh and initialized
context, successful hierarchy delivery, and cleanup after a failed native read.
The missing-initialization cases fail before the fix. Run with a JDK on PATH,
or set `TAKTIK_TEST_JDK` to a JDK directory. The packaged source and DEX hashes
are verified by the existing Phone accessibility tests.

The DEX was rebuilt with `javac --release 8` and D8 `--min-api 26`. The exact
compiler URL and SHA-256 are recorded in the native manifest. Compile the Java
source into an empty classes directory, pass all resulting `.class` files to
D8, and copy the resulting `classes.dex` to `hierarchy-reader.dex`; update the
source and DEX hashes in the manifest together.

The rebuilt native reader successfully returned the screen-reader hierarchy
from the same connected Android device and X detail screen that crashed before.

A live XBrowser check also restored from the original post detail, verified the
configured account, opened a search result for thread inspection, returned to
the same search, and continued to subsequent observations. Unsupported detail
content remained unverified rather than being fabricated.
