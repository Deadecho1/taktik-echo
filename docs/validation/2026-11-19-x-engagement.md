# X milestone 3: native engagement

Milestone 3 adds likes, bookmarks, follow/unfollow, and available recommendation feedback to the existing account-verified browsing service.
Implementation and diagnostic evidence use native accessibility/XML without OCR or screenshots loaded into the coding conversation.
Consumer workflow integration remains separate.

## Contracts

`X.set_liked()` and `X.set_bookmarked()` set the desired state without toggling an existing selection.
Explicit `False` removes the corresponding state after verifying it.
`X.follow()` and `X.unfollow()` verify the selected outer author and native relationship menu.
`X.not_interested()` uses only the offered `Not interested in Post` action.
The browser exposes the same capabilities through `act("like" | "save" | "follow" | "unfollow" | "not_interested", observation)`.

Every mutation is issued once, with a fresh source/menu check beforehand, bounded native outcome reads, and a final reread afterward.
Transport uncertainty, ambiguous targets, lost account/context, and missing confirmations stop the operation without another engagement tap.
Like/Bookmark animation and temporary toast overlays can be polled without retrying the action.
Native state visibility is separate from the labels retained for scrolling continuity.
An offscreen or obscured state remains unknown in observations even when its native label is retained for movement verification.
Selected-state labels are normalized in ordinary posts, clipped footer fragments, covered Bookmark rows, and native detail reads.

Unfollow and Not interested remove the selected occurrence on the installed version.
Success requires the exact native receipt, matching author, original header position, and absence of the selected post on two reads.
The next post is parsed independently; `navigation_gaps` records the removal, and `ActionResult.advanced` prevents an extra caller advance.
The original observation becomes stale.
An unavailable feedback menu is dismissed without engagement and returns unsupported.

## Device and discovery

Physical runs use the configured Pixel 4a and verify `@NirGalel` through the drawer under the established device/persona locks and reservation checks.
The device reports Android 13, X `12.42.0-prod.01`, and 1080 × 2340 dimensions.
All diagnostics are under ignored `tests/smoke/x-engagement-probes/` and `tests/smoke/x-engagement-runs/`.
The versioned fixture manifest preserves their provenance without publishing screenshots or account/device configuration.

Native selected states are `Undo Like` and `Delete Bookmark`.
The search menu omits recommendation feedback; the captured Home menu offers `Not interested in Post`.
Follow produces a temporary `You followed @NASA` toast, and a reread of the selected author's menu proves the relationship.
Unfollow produces an inline `You unfollowed @NASA` receipt with Undo and removes the source post.
Not interested produces `Thanks. X will use this to make your timeline better.`, Undo, an author-specific optional refinement, and an optional relevance refinement.
The refinements are not submitted.

Direct probes found that X's advertised Post options hitbox includes left padding that opens Grok and bottom padding that opens the post.
The safe target is restricted to the right half within the native author-header band, with all current overlapping controls excluded.
The dismissal backdrop can also report full-screen bounds while the sheet covers it; the entire sheet panel is excluded from dismissal taps.
Nested clickable and long-clickable controls are excluded from menu-row targets, and covered labels cannot authorize engagement.
Unexpected navigation stops before a follow or feedback tap.
Source captures and diagnostic tap coordinates preserve both failures and their corrected geometry.
Returning from a verified removal retains the already verified Home/search context, including collapsed headers.
The captured feedback continuation reaches its successor through three independently verified forward scrolls without reversing to restore a known header.

## Validation status

The final X suite passed **1,446 tests**, including **55 new engagement and compatibility cases**.
The broader X/shared Phone/Instagram-service/TikTok-service run passed **3,179 tests with 2 skipped** before the last eight X observation/alias regressions were added.
All **12 packaging checks** passed with temporary build dependencies; the shared Python environment was not modified.
Wheel and source-distribution checks verified both new engagement modules, their reader/browser integration, and the native source/DEX/manifest payloads against this checkout.
All **18 fixture/source hash pairs** match their manifest.
Ruff lint/format, the tree-layout audit, and Git whitespace checks pass.

The Standards review has no unresolved findings after the nested menu-control fix.
The Spec review has no unresolved findings after offscreen states were left unknown and selected-label normalization was extended to every clipped-footer path.
The focused cases cover native labels, no-ops, explicit state restoration, stale decisions, menu attribution, receipts, uncertainty, cancellation, cleanup, and continued browsing after engagement.

Final combined run `20261119T133552.883606Z` passed Like/Bookmark creation, already-selected no-ops, explicit removal, Follow/Unfollow transitions, native removal/advancement, and relationship re-verification from the next post.
The NASA post finished unliked and unbookmarked, and its author finished unfollowed, matching the pre-test states.
Direct feedback run `20261119T132909.224116Z` passed Not interested, native receipt verification, successor framing, and restoration through Undo.
Both runs verified `@NirGalel`, completed cleanup, and restored the original keyboard.
The combined run verified Taktik Keyboard during query entry and restored Gboard.
The final feedback run also restored the preceding failed-run feedback before exercising and undoing the same action.
The earlier astronomy discovery feedback was separately submitted; its receipt was no longer visible during final validation, so its reversal is not claimed.
`tests/smoke/x-engagement-runs/evidence-audit.json` independently checks the final native states, replacement receipts, source removal/restoration, and cleanup records.
No phone session remains active from these runs.

Human screenshot review remains pending and is separate from XML and replay validation.
Supported behavior is limited to the observed English layouts and positively verified native states.
These checks do not claim general recommendation-policy effects, promoted-placement detection, native post IDs/URLs, or completion of other milestones.
