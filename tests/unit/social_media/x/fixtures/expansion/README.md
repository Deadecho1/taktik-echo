# Native inline expansion captures

These ten hierarchies were captured on Nir's Pixel 4a, X `12.42.0-prod.01`, Android 13, English UI, at 1080 × 2340.
`manifest.json` records source paths and SHA-256 hashes for the raw and sanitized XML.
Public post text is preserved; external windows retain only their root geometry and empty content.
Screenshots remain local.
`soak-source` and `soak-expanded` retain the 20 November run's 288-character Show more source and 3,143-character clipped expansion.
They correspond to snapshots 449 and 450 from `20261120T110248.963317Z`, with the single recorded tap at `[568,1647,660,1669]`.
Their companion screenshots have not received visual review.
Workflow tests compose this captured rejection with the separate existing startup/account fixtures to verify a new occurrence; no physical recovery or native-detail read of this source was captured.
The user approved the two Lunar companion captures; OpenAI discovery/detail companion screenshots remain outside visual sign-off.
Three separate OpenAI screenshots from implementation run `20261117T134201.601008Z` were also explicitly approved.

`source`, `expanded`, `expanded-reread`, `detail`, `detail-depth-100`, and `return` come from probe `20261117T133437.381266Z`.
The OpenAI post expands inline within Latest results, retains its author, and has its complete expanded body inside the viewport.
Opening its detail still omits the main author/body/media at hierarchy depths 50 and 100, and direct node queries also fail to find them.
Native Back returns to the expanded source at the same geometry.
`words.json` records the local Tesseract word boxes used to locate the inline Show more span in `source.png` from that run.
Earlier occurrences of the word more in the authored text are not expansion targets.

`long-source` and `long-expanded` come from probe `20261117T133144.571820Z`.
The Lunar post expands inline and its XML contains text beyond the viewport.
That text remains incomplete and unobservable under the existing visibility contract.
The probe stopped for evidence review when it discovered the inline surface, then restored the keyboard and closed the Phone session.
It is discovery evidence, not a successful implementation round trip.
