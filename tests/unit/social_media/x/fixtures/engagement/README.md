# Native engagement captures

These XML fixtures come from direct Phone/X sessions on 19 November 2026, using X `12.42.0-prod.01`, Android 13, English UI, at 1080 × 2340.
`manifest.json` records each source path and both the source and fixture SHA-256 hashes.
External-window children are removed; window bounds, native X labels, public post content, and geometry are retained.
Screenshots remain local under ignored `tests/smoke/`; human visual review is pending.

The captures cover unselected/selected Like and Bookmark, Like animation, the transient Bookmark confirmation, search/Home menus, followed relationship state, and native Unfollow/Not interested replacement receipts.
Selected labels are normalized to canonical action names without changing post content identity.
The search menu omits recommendation feedback; the Home menu offers `Not interested in Post`.
The feedback receipt's optional refinement controls are preserved as evidence and are not activated by this milestone.

Replay cases mutate these captures to exercise stale targets, wrong authors, obscured controls, missing confirmations, transport failures, cancellation, and browser occurrence changes.
One successful immediate feedback-advance case removes the successor's clipped quote to model an already observable successor.
Such transformations are synthetic tests, not additional physical observations.
