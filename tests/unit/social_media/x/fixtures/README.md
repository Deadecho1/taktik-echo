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
