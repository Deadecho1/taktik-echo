# Synthetic X browsing fixtures

These trimmed XML hierarchies retain the geometry and native English controls of
1080 × 2340 Android captures. Other post containers are removed, and author/body
text is replaced with fixture values. They are synthetic parser and continuity
inputs, not full live-feed evidence or proof of pixel visibility.

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
