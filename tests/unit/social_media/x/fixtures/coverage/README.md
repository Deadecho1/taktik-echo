# Native layout and traversal coverage

These XML fixtures preserve native geometry and public post content at 1080 × 2340.
The November 2026 captures use Android 13 and English X.
The manifest records source paths, original hashes, fixture hashes, and the app version for each capture.
The older plural media-tag reference uses X `12.41.0-prod.01`; the new direct sessions use `12.42.0-prod.01`.
Owner names are replaced and external system-window children are removed while retaining their bounds.
Screenshots remain local and have not received new human visual approval.

`media-tag-single.xml` preserves the earlier unsupported NASA capture.
The current tag fixtures cover normal account-verified search, the raw `NASA JPL` label, and subsequent scrolling.
The plural reference retains the existing `Air Dot Show Tour and 3 others` layout.
Tagged display names never supply a post author or an inferred handle.

The two `pending-search` fixtures reproduce a retained text passage whose author header loses its age label behind the collapsed search toolbar.
The header and translation controls are fully outside the content viewport.
The body may supply an unattributed pending passage, but it cannot supply a new post observation or establish movement while both text edges are clipped.

The 24 `long-text` fixtures and `long-text-traversal.json` replay the first advance of the successful physical run.
They cover two pending phases, independently reverified lower text edges, video tails, and a real observable successor after 23 gestures.
None of the endpoints is synthetic.
The four `search-video` fixtures cover the relevance prompt above a partly visible video and three verified outgoing movements to the next observed post.
They extend the T3 layout coverage using current search results; they do not recreate the original historical feed position.

The two `unlabeled-inline` fixtures retain a later discovery stop where an inline View exposes neither text nor a description.
They preserve rejection of that unknown body and refusal of movement without usable native anchors.
Malformed variants in tests are synthetic and establish rejection behavior only.
No fixture establishes native promoted/ad detection or complete visual review.
See the [validation record](../../../../../../docs/validation/2026-11-20-x-layout-coverage.md).
