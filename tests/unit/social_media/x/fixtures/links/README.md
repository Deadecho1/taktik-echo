# Native post link captures

These eight XML fixtures come from direct Phone/X sessions on 19 November 2026, using X `12.42.0-prod.01`, Android 13, English UI, at 1080 × 2340.
The manifest records source paths and SHA-256 hashes for both the original captures and sanitized fixtures.
Status-bar children are removed; native X geometry, public content, and the Android clipboard receipt are preserved.
Screenshots remain local under ignored `tests/smoke/`.
On 19 November 2026, the user approved all nine presented captures, including the screenshot counterparts of these eight XML fixtures.
The local receipt is `.lavish/x-link-review/review-receipt.json`; other captures remain outside this approval.

The initial Latest discovery supplied `source`, `share`, `copied`, and `copy-stable`.
That discovery copied a URL but could not verify return until the new clipboard-overlay reader was implemented.
The successful Top implementation run supplied `top-source`, `top-share`, `top-receipt`, and `top-return`.
It verified two independent copies of the same native URL and returned to the original browsing occurrence each time.

The Share sheet presents an X Chat setup prompt and a separate action row containing Share via and Copy link.
Only Copy link and sheet dismissal are exposed as targets; no recipient or external sharing action is invoked.
The Android clipboard preview retains the copied URL as native metadata, even though its narrow visual preview does not establish that every character is visible.
Its entire window remains an occlusion for post extraction and gestures.

Synthetic mutations test hidden, disabled, nested, ambiguous, and changed controls, unknown overlays, wrong authors, stale receipts, transport uncertainty, cancellation, and explicit recovery.
These mutations do not establish additional physical layout coverage.
