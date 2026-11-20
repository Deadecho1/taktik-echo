# Retained expanded-caption startup and Home reset

These captures come from one bounded physical diagnostic on 20 November 2026.
The phone ran English X `12.42.0-prod.01` on Android 13 at 1080 × 2340.
`manifest.json` records original and fixture hashes from run `20261120T133655.284102Z`.
The owner is anonymized as `Fixture Owner` / `@fixture_owner`, and external windows retain only empty root geometry.
Public post text and native geometry remain unchanged.
Screenshots remain local and have not received human review.

`source` precedes one Show more tap at `[568,1478,660,1500]`.
`expanded` records the correctly rejected 3,143-character inline caption.
`launch`, `drawer`, and `returned` capture recovery with that same expanded state retained.
`frame-1` through `frame-4` exhaust the original initial framing budget.
`reveal-1` and `reveal-2` expose the native Home controls through two downward gestures.
One Home tap at `[0,2120,199,2274]` produces `reset`, where an independently observable post is available.
This establishes a new browsing position and does not read the abandoned caption or prove continuity of intervening posts.
Unlike the earlier workflow replay against a separate startup fixture, the expansion and recovery here were captured in the same physical diagnostic.
Repeated frames, wrong accounts/tabs, interruptions, and failed resets in tests are explicitly synthetic variants of this sequence.
