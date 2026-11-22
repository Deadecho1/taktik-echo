# X gallery controls and search recovery

A search debug session repeatedly failed with `Gallery controls cover its image`.
Inspection had opened an image whose native bounds overlapped X's gallery chrome.
The reader rejected the whole screen, including its verified Back control, so
every subsequent startup failed on the same gallery.

Gallery recognition now keeps independently verified identity and Back controls.
Capture selects the largest continuous rectangle outside native chrome using the
same rectangle-exclusion helper as inline media and navigation. Crops reduced by
chrome carry `partial=True` through the browser's media-inspection report.
A fully covered image provides no frames but retains the verified return target
for explicit recovery. Obscured identity, external overlays, changed accounts,
uncertain actions, cancellation and deadlines retain their existing behavior.

The captured Android 16 gallery and Phone replays cover partial capture, source
continuity, startup recovery with account verification, full occlusion, changing
crop geometry, and an uncertain Back response without a repeated action.
See the inspection fixture README and manifest for sanitized capture provenance.

Validation: the X and shared-phone suites passed 3,455 tests with six skips.
The final inspection suite additionally covers the captured 1440 × 3216 gallery
and propagation of partial capture into persona observations. Persona Engine's
ownership checks and Echoseek's dispatch tests passed 65 tests. Ruff, whitespace,
and the repository tree-layout audit passed.

The existing live debug job recovered through its normal retry path, verified
the account, and resumed observing search posts. Its original deadline, query
assignment, device reservation and manual intent were retained.
