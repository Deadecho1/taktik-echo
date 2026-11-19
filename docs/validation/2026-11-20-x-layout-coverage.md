# Native X layout and traversal coverage

Milestone 5 now has direct phone coverage for pending long text followed by video, current search results with a relevance prompt above a clipped video, and the previously unsupported single-account media-tag layout.
Native promoted/ad placement coverage remains incomplete: no native ad label appeared in the sampled feeds.
The milestone remains open for that requirement, and unknown advertising status remains unknown.

## Reader changes

The native media-tag reader accepts a single label beneath recognized outer image, video, or GIF media and immediately above a complete action row.
It verifies the label's native type, interaction state, accessibility, sibling order, containment, and observed touch-padding overlap with the media.
Single-account labels and the existing plural label remain separate from authored text, account labels, and the outer author.
Display names never supply an account handle or native post ID.
Only unobscured tag labels enter observation context; clipped labels remain recognized controls without supplying unseen text.
Malformed, hidden, disabled, duplicated, nested, or misplaced labels remain unsupported.

Physical long-text discovery reproduced a search transition where X retained name, badge, and handle but removed the age label after the entire header had scrolled behind the toolbar.
The former reader discarded the post and its retained passage, causing `Lost X post continuity: no overlapping candidates.`
The reader now recognizes the captured fully hidden header, avatar, controls, and translation prefix and retains only the clipped native text as an unattributed fragment.
The existing pending-text verifier still requires exact unique text and matching geometry, and does not treat clamped text edges as proof of movement.
Visible or malformed prefixes remain rejected.
No scrolling, retry, deadline, cancellation, or observation-completeness limits changed.

## Physical evidence

All sessions used Nir's Pixel 4a `0A031JEC221805`, Android 13, X `12.42.0-prod.01`, English UI, and 1080 × 2340 dimensions.
Successful browsing runs verified `@NirGalel` through the drawer and checked the selected query and tab.
The harness checked controller reservations and held the existing device and account locks through Phone cleanup.
Every session, including the failed discovery, restored the original input method and reported successful cleanup.
No session remains active.
Raw XML, screenshots, events, and results are local under ignored `tests/smoke/x-coverage-runs/`.
Run IDs below are UTC.

- `20261119T215455.763044Z`: Latest search combined the known NASA stellar-merger source, the captured long-text author/query, and older NASA successors.
  The first advance took 23 gestures and traversed two pending phases before selecting a real successor.
  The final 104-line passage exposed its lower edge, independently reverified that edge on the following movement, and continued past its video tail.
  A second advance also passed; the run recorded 24 movement attempts, including 12 pending reads that explicitly do not claim measured motion.
  The full first advance is replayed through the shared Phone interface, including a cancellation regression.
- `20261119T215228.824472Z`: Top search for `astronomy filter:videos` passed six advances and recorded 22 movement checks.
  Snapshots 034 through 037 preserve the relevance prompt above `@slash1sol`'s partly visible video and three outgoing movements to `@NightSkyToday`.
  The caption is itself collapsed, and its visible bounds remain separate from the clipped video bounds.
  This covers the physical layout concern raised for T3 using current results; the original T3 occurrence was not restored.
- `20261119T215921.286755Z`: Targeted Latest search observed `@NASASolarSystem` with the separate `NASA JPL` label and completed two advances.
  One measured scroll retained ordered-post continuity as the tagged source left view.
  An earlier discovery opened the label's native `@NASAJPL` profile and returned to search; that raw probe lives under `tests/smoke/x-media-tag-probes/20261119T214950.710181Z/`.
  The probe's first source capture was still loading, so it is not used as a verified source-return pair.
- `20261119T214542.707801Z`: For you passed 20 advances with 66 recorded movement checks and 21 observations.
  No native Ad, Promoted, or Sponsored label appeared in its XML.
  This does not establish that every sampled post was organic, that ads cannot appear on the account, or that unsupported ad layouts are recognized.
- `20261119T214412.623099Z` and `20261119T215720.047354Z`: Additional Top astronomy and unrestricted Latest NASA runs passed six and three advances respectively.
  They supplement layout coverage without establishing native advertising detection.

Discovery run `20261119T215055.429097Z` stopped on the hidden incomplete header and completed cleanup.
Its exact failure pair now passes both the pure-reader and navigation replay checks.
The successful long-text run subsequently exercised the corrected path physically.

## Regression and publication status

The initial X suite passed 1,486 tests.
The broader shared/X/Instagram-service/TikTok-service run passed 3,293 tests with 2 skipped before the final fixture and test-organization follow-ups.
New regressions cover native tag separation and malformed geometry, hidden search-header rejection, captured long-text and video traversal, cancellation while pending, and continuation after the relevance prompt.
Fixture manifests preserve source provenance; XML/replay checks do not establish pixel visibility or human visual approval.
The final X and packaging checks passed all 1,537 tests: 1,525 X cases and 12 packaging checks, using temporary build dependencies.
Standards and Spec review identified clipped-tag exposure and unexplained passage-wrapper content; both reproduced in captured regressions and are fixed.
Independent Standards and Spec follow-ups report no unresolved implementation findings; native-ad coverage remains the outstanding requirement.
All 37 fixture/source hash pairs and 169 transition checks across seven runs were independently replayed, covering 54 observations.
The transition audit includes the deliberately rejected final movement in the additional discovery sample.
Wheel and source-distribution audits verify all 22 X/native source and asset files against the checkout.
Ruff lint/format, the tree-layout audit, Markdown links, and whitespace checks pass.
The reviewed continuation is published on `feature/x-platform`; milestone 5 remains open for native-ad coverage.

## Remaining limits

Native promoted/ad placements still need a captured source and direct validation on a supported account/device.
Paid-partnership disclosure support remains a separate capability.
The user confirmed that the test account does not have an ad-free subscription.
Additional For you run `20261119T220838.413049Z` completed eight advances and nine observations before stopping at an unlabeled inline element.
Its native View has neither text nor a content description; the reader rejects that unsupported body and cannot verify the next movement once its usable anchors disappear.
The two final snapshots now protect this conservative stop in the navigation-evidence regression suite.
The run recorded 35 accepted transition checks and one rejected transition, found no native ad label, restored the input method, and completed cleanup.
This captured limitation does not authorize interpreting the unlabeled element or treating the failed movement as verified.
Remaining unrecognized content keeps its existing rejection behavior; native-text movement may select a later independently observable post only with an explicit continuity gap.
New screenshots remain pending separate human review under milestone 6.
Consumer dependency adoption and workflow integration remain outside this fork's milestone.
