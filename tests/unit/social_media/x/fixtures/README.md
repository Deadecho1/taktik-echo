# Synthetic X browsing fixtures

These trimmed XML hierarchies retain the geometry and native English controls of
1080 × 2340 Android captures. Other post containers are removed, and author/body
text is replaced with fixture values. They are synthetic parser and continuity
inputs, not full live-feed evidence or proof of pixel visibility.

The `detail/` subdirectory contains sanitized native and ordinary captures, including character geometry needed for long-caption coverage.
Its manifest records canonical expanded-input hashes.
Original capture provenance remains in local migration diagnostics.
Those captures preserve public author/body text for independent comparison and replace the test account identity.
They establish native XML evidence; human visual review remains separate.

`partnership-before.xml` ends at the bottom-clipped video before the disclosure
enters XML. `partnership-probe-after.xml` retains the author and reveals the native
Paid partnership icon/text pair between video and actions.
`partnership-fragment.xml` loses the author header while its body begins one pixel
below the collapsed Home inset. The fragment must never supply a new author.

Tests cover authored-text separation, exact disclosure structure, geometry,
independent movement, and conservative rejection of malformed variants.

`quote-body-loss-before.xml` and `quote-body-loss-after.xml` retain the captured
geometry of simultaneous outer-body loss and quoted article revelation, with
synthetic author, body, title, and summary text.

`missing-handle-before.xml` and `missing-handle-after.xml` retain the complete
layout of an older video tail, a leading name/Verified/age post without a handle,
and an attributed neighbor. The first gesture removes the older tail and the
unattributed header. Body, media, and neighboring header anchors establish a
512-pixel upward displacement. Post text and profile names are synthetic; the
missing handle is never reconstructed. These inputs establish XML continuity,
not physical traversal or human visual review.

`video-inset-before.xml` and `video-inset-after.xml` isolate one outer video post
whose body disappears while its video still starts below the collapsed Home inset.
The retained video edges and complete action row move upward by 602 pixels.
The old body bottom projects to y=132, above the y=136 viewport edge, while the
video starts at y=154. The viewport edge lies in the existing 22-pixel gap.
Unrelated posts are removed and author/body/source text is synthetic. Tests cover
projected body/header loss, both video edges, action geometry, source consistency,
unique matching, refresh, and continued scrolling. No author is inferred.

`preview-tail-before.xml` and `preview-tail-after.xml` preserve a quoted article whose video and header leave the viewport while title, summary, and action row remain. The same endpoint includes a quoted video credit with native touch padding below the video, while its visible children remain inside.

`clipped-summary-before.xml` and `clipped-summary-after.xml` preserve a clipped title completing while its summary enters XML. Retained quote-header edges and the video bottom establish movement; the video top is clamped to zero. Both pairs use synthetic author, source, title, and body text with unchanged captured geometry.

`quote-tail-before.xml` and `quote-tail-after.xml` retain the full 1080 × 2340 layout with synthetic content. A previously incomplete quote completes and reveals an article while the outer body is retained in a headerless fragment. Stable body text, quote-header edges, and video geometry independently constrain movement.

`short-video-overlap-before.xml` and `short-video-overlap-after.xml` isolate a short video and footer, with synthetic author/body/source values. A 537-pixel displacement leaves no overlap between the two 490-pixel video rectangles. The endpoint remains rejected; the gesture test preserves overlap by bounding travel using video height.

`made-on-x-before.xml` and `made-on-x-after.xml` retain the captured native video-footer geometry at 1080 × 2340. The incomplete unrelated neighbor is removed and author/body/source text is synthetic. The exact Made on X button must follow its video and meet the complete action row.

`quote-body-summary-before.xml` and `quote-body-summary-after.xml` preserve simultaneous outer-body loss and quoted-summary revelation while the quoted body stays unchanged. Synthetic text replaces author/body/title/summary content. Retained quote-header/video movement, explained clipping, and projected disappearance are all required.

`covered-partial-handle-before.xml` and `covered-partial-handle-after.xml` preserve a leading footer, a covered name/badge/partial-handle row, and an independently retained neighboring post. Text is synthetic; the clipped handle cannot supply an author.

`quote-preview-budget-before.xml` isolates the retained bodyless quoted article, with synthetic title/summary text and the rejected neighbor removed. The title/summary must supply the scroll budget after the quote header reaches the inset.

`retained-author-preview-before.xml` and `retained-author-preview-after.xml` preserve quoted-title revelation while the outer post keeps its native author header. Author/body/title/summary text is synthetic. Matching author and independent quote/video movement remain mandatory.

`unbadged-header-before.xml` and `unbadged-header-after.xml` retain an unbadged name/age row with different text heights and no handle. Display names/body/source text are synthetic; the incomplete unrelated neighbor is removed. The row can supply only unattributed translated-body/video continuity.

`compact-quote-video-before.xml` and `compact-quote-video-after.xml` preserve the native square video thumbnail beside quoted text, with synthetic content. `footer-video-padding-before.xml` and `footer-video-padding-after.xml` preserve the following transition where the preceding video padding disappears under its complete action row, while the neighboring quote independently measures movement.

`nested-quote-tail-*.xml` retain the original geometry with synthetic author/body/source text. A quoted video body remains after the quote header leaves the viewport, while an independent neighbor reveals `nested_quote_preview` with its own author and body. The fragment remains unattributed.

`composer-video-entry-before.xml` and `composer-video-entry-after.xml` use synthetic text at the captured 1080 × 2340 geometry. New neighbor video appears while the composer covers only the bottom of its body; clear author/header and body-start positions still prove motion. Observation remains unavailable.

`quote-header-entry-before.xml` and `quote-header-entry-after.xml` preserve a quote header entering entirely below the viewport with its bottom clipped to the capture boundary. Body/media remain unknown until a later verified reveal; text is synthetic.

`quoted-article-body-tail-before.xml` and `quoted-article-body-tail-after.xml` preserve quoted body and article content after the outer video and quote header leave the viewport. Author/body/preview text is synthetic. Tests cover exact content, independent geometry, projected disappearance, stationary rereads, and a synthetic subsequent body-loss step.

`header-controls-gap-before.xml` and `header-controls-gap-after.xml` preserve a headerless post with native Grok/options controls ending at a body that begins three pixels below the viewport. Captured geometry remains intact; post text is synthetic. The controls explain the header gap without reconstructing an author.

`preview-header-gap-before.xml` and `preview-header-gap-after.xml` preserve a gap between the clipped card top and article preview after the quote header disappears. Width/bottom edges remain equal; text is synthetic and movement/loss remain independently checked.

`covered-quote-reveal-*.xml` retain the known New posts cover over an outer handle while article text enters its quote. `gif-tail-*.xml` retain native GIF geometry after the outer body/header leave. `quote-header-body-edge-*.xml` and `video-and-quote-entry-*.xml` preserve previously verified transitions that newly recognized offscreen quote headers must not obstruct. All use synthetic post/author text at the captured 1080 × 2340 geometry.

`header-control-padding-*.xml` preserve shared native control padding above the container. `retained-quoted-summary-*.xml` preserve quoted-summary revelation after the outer body has already left. Content is synthetic; retained text, movement, and projected revelation are required.


The engagement `undo-*.xml` fixtures are synthetic text versions of native X layouts, preserving control structure and geometry.
The source/options/receipt/framing/successor sequence exercises a caller that waits until successor framing before looking for Undo, when the complete receipt is no longer visible.
The evaluator test models restoration by returning the saved synthetic source after its verified Undo tap.
The separate `undo-complete-*.xml` sequence includes a native transition, receipt, and restored-source layout for a complete round trip.
Both sequences use the real Phone/TaktikDevice boundary with fake raw transport; successful restoration performs no successor-framing scroll.
All author/display names, post captions, profile-image descriptions, counts, ages, and custom-list labels in these fixtures are synthetic.
External system-window children are absent while their geometry remains, and native control labels retain their required semantics.
For these fixtures `engagement/undo-manifest.json` records only synthetic fixture hashes; private source provenance remains in local diagnostics.

The `links/share-glyph-*.xml` fixtures contain synthetic text and identities with native Share wrapper, glyph, sheet, and clipboard geometry.
They cover an unobscured glyph inside non-activating wrapper padding and a complete Share/copy/source-return sequence through the real Phone/TaktikDevice boundary with fake raw transport.
The existing covered-footer sequence separately verifies a successful edge-clipped Share strip; it is not a continuation of the new sequence.
The synthetic fixture integrity hashes are recorded in `links/share-glyph-manifest.json`; raw source provenance stays in local diagnostics.

The `navigation/preceding-posts-*.xml` fixtures use synthetic identities and text to exercise verified removal of preceding posts while the selected source remains aligned.
The terminal layout contains an incomplete next post; repeating it must stop after the unchanged no-progress allowance without selecting a successor.
The test's separate 500-pixel continuation is explicitly synthetic.
The `navigation/preceding-complete-*.xml` fixtures provide a complete native layout sequence through two successive selections, including explicit movement-only continuity gaps.
These fixtures preserve native control semantics and geometry; all personalized text, counts, ages, custom labels, and system labels are synthetic.
`navigation/manifest.json` contains only synthetic fixture integrity hashes.
Private source provenance remains in ignored local diagnostics.

The `navigation/successor-approach-*.xml` fixtures isolate a unique selected source approaching a successor covered by a floating control, with no change in post index.
All identities, captions, image descriptions, counts, ages, and system labels are synthetic.
The stopped sequence has no observable successor; its separate 114-pixel continuation is explicitly synthetic.
The public browser regression retains real Phone/TaktikDevice execution and verifies the unchanged stationary and total gesture bounds, visibility, continuity, interruption, and exclusion checks.
`navigation/successor-approach-manifest.json` contains only synthetic fixture integrity hashes.

The `links/fullscreen-dismissal-*.xml` fixtures use synthetic identities, post text, clipboard URLs, counts, ages, and system labels while preserving native window geometry and required control semantics.
The sequence covers Share, Copy link, the receipt, an inert empty full-screen System UI window, and its disappearance with unchanged X content.
The empty window contributes full occlusion and no actionable or observable evidence.
It is not itself a clipboard receipt; only a preceding observed receipt permits the bounded stationary verification path.
No next-post capture is present, and the separate unchanged-frame test preserves the existing advance limit without inventing a successor.
`links/fullscreen-dismissal-manifest.json` records only synthetic fixture hashes; private source provenance remains in ignored local diagnostics.

`detail/badge-*.xml` contain a synthetic feed source and paired ordinary/native detail layouts with a verification badge followed by an affiliation icon.
The author, organization, body, counts, and timestamp are fictional.
The public Phone/TaktikDevice regression uses the source fixture again for its synthetic successful return.
`detail/badge-manifest.json` records synthetic fixture hashes only.

## One-step scrolling variants

The 322 root-level scrolling and visibility cases retain their original names and native inputs.
They now use 147 full XML layouts, 154 explicit variants, and 21 direct aliases, with no removals.
Bases stay within each named scenario sequence; a case with an unclear or larger recipe remains full XML.
This removes 11,887 lines and 3,723,341 bytes from the root XML/recipe data.
Every retained case matches the original complete native hierarchy and real parser result.

Load case names with `unit.x_fixtures.xml_fixture` or use the expansion command described in [the representation guide](../../../../../docs/validation/x-fixture-representation.md).
A `.case` stores the recipe for the corresponding `.xml` name; tests and diagnostics should use the loader for either representation.
The input inventory hashes expanded canonical XML, while recipe base hashes check stored full XML bytes.

The detail, coverage, and inspection families retain every case while removing another 5,688 XML/recipe lines.
Their 73 converted cases comprise 58 explicit variants and 15 direct aliases, with bases kept inside each detail, caption traversal, or inspection sequence.
