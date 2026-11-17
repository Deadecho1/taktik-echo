# Native inline expansion captures

These eight hierarchies were captured on Nir's Pixel 4a, X `12.42.0-prod.01`, Android 13, English UI, at 1080 × 2340.
`manifest.json` records source paths and SHA-256 hashes for the raw and sanitized XML.
Public post text is preserved; external windows retain only their root geometry and empty content.
Screenshots remain local and human visual review is pending.

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
