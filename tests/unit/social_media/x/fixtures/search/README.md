# Search replay captures

The initial seven XML hierarchies are copied from the persona workspace's original X inspection fixture package.
The captures used X `12.41.0-prod.01`, Android 13, English UI, and 1080 × 2340 dimensions on 8 November 2026.
`manifest.json` retains the source hashes and capture provenance for this subset.
The owner is anonymized as `Fixture Owner` / `@fixture_owner`; public post text and geometry remain intact.
System and keyboard windows retain their root geometry without notification or suggestion contents.
The initial seven captures were visually reviewed during the original inspection.
The six captures from 17 November were verified through XML; their human visual review remains pending.

The tests replay account verification, Explore, query entry, Top/Latest selection, observation, and result navigation through Phone.
The 350-pixel displacement, changed queries, keyboard variants, and failure cases are synthetic transformations of these captures.
They verify code behavior and XML evidence, not a physical search run or current device versions.
`search-empty.xml` is an empty query field, not evidence of a no-results state.

`explore-new-feature.xml` retains the chrome from the 17 November 2026 physical search stop on X `12.42.0-prod.01`, Android 13, at 1080 × 2340.
The native Settings label is `Explore Settings. New feature available`.
Trend-list children and external-window contents are removed; screen markers, navigation, tabs, header controls, and their geometry are unchanged.
The source is `tests/smoke/x-search-runs/20261117T084343.636064Z/failure.xml`.

`search-standalone.xml` captures the same installed version's standalone `SearchQuery` screen, without a `MainLanding` wrapper.
Recent-search content and external-window contents are removed; the empty editable field, scope, focus, keyboard bounds, and header geometry remain captured evidence.
The source is `tests/smoke/x-search-runs/20261117T084620.764097Z/failure.xml`.

`results-standalone.xml` captures Top results after Taktik Keyboard verified and submitted `astronomy` on X `12.42.0-prod.01`.
It retains the standalone `Search` scope, native Back control, result tabs, posts, and floating composer; there is no Home navigation bar.
The source is `tests/smoke/x-search-runs/20261117T084833.406082Z/failure.xml`.
External-window contents are removed and public result content is retained.

`results-expanded-before-scroll.xml` and `results-collapsed-after-scroll.xml` retain the result-header collapse from physical run `20261117T085143.842001Z`.
Back and query disappear while the selected Top tab remains visible; the reader reports no query in the collapsed snapshot.
The captured tab indicator extends beneath the row to y=331, so the content viewport excludes that entire strip.
Tests require independently measured post movement before retaining the previously verified query and reject uncommanded collapse, a different tab/query, or absent account verification.

`no-results.xml` retains the native query-specific empty-result title and explanation from physical run `20261117T090208.981499Z` on X `12.42.0-prod.01`.
The noninteractive pair belongs to the single native ScrollView in the result surface.
Tests require the exact displayed query, explanation, structure, and unobscured labels; absent posts alone never establish emptiness.
