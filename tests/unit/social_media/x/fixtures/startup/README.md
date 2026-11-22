# Retained expanded-caption startup and Home reset

The twelve retained-caption/reset captures come from one bounded physical diagnostic on 20 November 2026.
The phone ran English X `12.42.0-prod.01` on Android 13 at 1080 × 2340.
`manifest.json` records canonical expanded-input hashes.
Original capture provenance remains in local migration diagnostics.
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

`short-scroll` comes from the subsequent three-hour revalidation attempt `20261120T135150.651075Z`, snapshot 3.
It records the unobservable source whose partly visible media/footer needs a 103.5-pixel framing scroll in the safe region `[0,598,137,2004]`.
The real shared Phone/backend replay exercises sampling, exact-reach checks, exclusions, and transport injection for that captured X request.
The screenshot remains local and visually unreviewed.

## Synthetic drawer-tip startup

`drawer-tip.xml` models the native drawer migration tip as a second X window over the account drawer.
`drawer-tip-home.xml` provides a reduced Home layout with a fictional post and synthetic account, author, list, and count text.
Native control labels and layout geometry are retained; the System UI window contains only root geometry.
`drawer-tip-manifest.json` records only these synthetic fixture hashes.
The tests model a successful return to Home after closing the drawer; this continuation is synthetic and does not establish how a physical tip routes an outside touch.
Caller regressions use the real Phone and TaktikDevice with fake raw transport to verify account checking, tip exclusions, source selection, and conservative failure outcomes.
