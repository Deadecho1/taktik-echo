# Inspection captures

These seventeen hierarchies retain native X profile, detail, gallery, and return geometry at 1080 × 2340.
The current captures use X `12.42.0-prod.01`, Android 13, English UI, on 17 November 2026.
The two legacy captures come from the original `12.41.0-prod.01` inspection package.
Public account and post text remain intact; external windows retain only their root geometry.
No active-account drawer, private messages, keyboard suggestions, or screenshots are included.

`manifest.json` records canonical expanded-input hashes for each capture.
Original capture paths and source hashes remain in local migration diagnostics.
The raw sources remain under ignored `tests/smoke/` or in the original persona fixture package.
XML checks do not establish pixel visibility; no new human screenshot review is claimed.

`text-source`, `text-detail`, `profile`, and `text-return` preserve a visit from an exact Latest search to a reply's detail and the selected author's profile.
`image-source`, `image-detail`, `image-detail-scrolled`, `image-gallery`, and `image-return` preserve an image post, the gallery's independent author/caption/alt-text evidence, and restoration.
The main detail author/body/media remain absent even when related thread posts are readable.
The gallery caption node retains text beyond its visibly shortened caption; its metadata does not establish expanded text.

`thread-initial`, `thread-ready`, `thread-first-scroll`, `thread-second-scroll`, and `thread-header-restored` come from the successful direct inspection run `20261117T130556.304837Z`.
The two forward movements measure 358 and 309 pixels using exact native text.
A downward restoration reveals the Back control before returning to the original search occurrence.

Tests also mutate these captures to exercise wrong handles, changed queries, occlusion, nested unreadable content, uncertain actions, cancellation, deadlines, and bounded restoration.
Those mutations are synthetic regression cases, not additional physical evidence.

`ambiguous-image-source` comes from soak run `20261120T141911.022052Z`, snapshot 162, on 20 November 2026.
It retains the selected post's two `Image` descriptions, original media indices, visible targets, and control overlaps.
External System UI children were removed while preserving root geometry.
The workflow regression skips both images without injecting actions or crediting image coverage.
Synthetic continuation combines this source with the existing independently captured image/gallery fixtures; it does not claim a physical continuation of the stopped soak.
