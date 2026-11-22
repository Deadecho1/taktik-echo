# Native inline expansion captures

`wrapped-source.xml`, `wrapped-expanded.xml`, and `wrapped-words.tsv` are synthetic fixtures with fictional text and a two-line Show more layout.
The source places Show at the right of the penultimate line and more at the left of the final line, with a lower glyph fringe inside the existing recognition context.
The expanded fixture supplies a synthetic successful continuation, not a historical phone outcome.
`wrapped-manifest.json` contains only synthetic fixture hashes; raw evidence and provenance remain local.

These thirteen hierarchies were captured on Nir's Pixel 4a, X `12.42.0-prod.01`, Android 13, English UI, at 1080 × 2340.
`manifest.json` records source paths and SHA-256 hashes for the raw and sanitized XML and selected OCR rows.
Public post text is preserved; external windows retain only their root geometry and empty content.
Screenshots remain local.
`crop-edge-source` preserves snapshot 375 from `20261120T201433.889306Z`, whose translated 288-character caption ends in Show more at body bounds `[176,1636,1047,2001]`.
`crop-edge-body.tsv` and `crop-edge-context.tsv` retain only the Show/more rows from the existing Tesseract reader on the saved failure frame, with crop-relative coordinates.
The body-only crop has height 365 and word confidences 66.541107/89.471870; the lower-context crop has height 376 and confidences 96.177139/96.734894.
The latter boxes end at y=2005 while the safe target ends at y=2001.
The eleven-pixel context comes from rounding up 1% of the 1080-pixel shorter screen side; it is a recognition budget, not a universal device calibration or permission to tap outside the body.
Both TSV crops start at `[176,1636]` and retain the existing confidence-70 filtering in maintained caller tests.
The raw image SHA-256 is `a426d5869a8c3f214e497a0ac4110b78a14d1a5687403d70aa13528752a0ef5e`.
It was saved roughly one second after localization failed, with no intervening tap or scroll; original-image equality and a physical expansion are not established by this fixture.
The unchanged post-tap XML in the replay deliberately fails outcome verification and earns no coverage.
`same-height-source` and `same-height-expanded` come from bounded physical check `20261120T203903.698494Z`, using the original source in Top search for `from:damsizcimcime -filter:replies`.
The native Show more tap reveals nine characters while replacing the ten-character control suffix, reducing the complete body from 288 to 287 characters without changing bounds `[176,605,1047,970]`.
The original verifier rejected this stable-height result, while the captured identity, context, media, and action fields remain unchanged.
Maintained workflow tests use the earlier crop-relative TSV rows with these equivalent word positions; the separate local shared-reader replay processes the physical source image directly.
Both images remain local and have not received visual approval.
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
