# Synthetic X disclosure fixtures

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
