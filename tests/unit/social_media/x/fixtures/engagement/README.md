# Native engagement captures

These XML fixtures come from direct Phone/X sessions on 19 November 2026, using X `12.42.0-prod.01`, Android 13, English UI, at 1080 × 2340.
`manifest.json` records canonical expanded-input hashes.
Original capture paths and source hashes remain in local migration diagnostics.
External-window children are removed; window bounds, native X labels, public post content, and geometry are retained.
Screenshots remain local under ignored `tests/smoke/`; human visual review is pending.

The captures cover unselected/selected Like and Bookmark, Like animation, the transient Bookmark confirmation, search/Home menus, followed relationship state, and native Unfollow/Not interested replacement receipts.
Selected labels are normalized to canonical action names without changing post content identity.
The search menu omits recommendation feedback; the Home menu offers `Not interested in Post`.
The feedback receipt's optional refinement controls are preserved as evidence and are not activated by this milestone.

Replay cases mutate these captures to exercise stale targets, wrong authors, obscured controls, missing confirmations, transport failures, cancellation, and browser occurrence changes.
One successful immediate feedback-advance case removes the successor's clipped quote to model an already observable successor.
Such transformations are synthetic tests, not additional physical observations.

The repost-feedback regressions transform the existing synthetic `undo-*.xml` inputs covered by `undo-manifest.json`.
They add a display-only repost annotation and a distinct synthetic preference account to exercise the two-, three-, and four-text receipts.
The modeled Undo continuation comes from the separate synthetic restoration fixture and does not establish an Undo result in any stopped phone trace.
No new capture identifiers, content, hashes, or source mappings are included in these transformations.
