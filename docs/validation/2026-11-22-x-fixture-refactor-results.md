# X fixture and test reduction results

The refactor starts at main `dfad5ddc1cbd2533543660548c1f1c1bcac1fe4e`, whose tree equals the assessed feature revision `2615fe66641d43031f6597c42f0a7127ea7fd152`.
GitHub main had no subsequent changes when the work began.
The original workspace remains on its feature branch, with the user's validation edit preserved byte-for-byte and never staged.
Implementation and verification use isolated checkouts under `/tmp`.
No production code, consumer dependency pins, or live-phone state changed.
No merge was performed.

## Review stack

Each PR targets the preceding branch and is independently checked by the Python 3.10/3.14 browsing workflow.
Merge order, if separately authorized, is the table order.

| PR | Scope | Published implementation revision |
| --- | --- | --- |
| [#2](https://github.com/Deadecho1/taktik-echo/pull/2) | Loader, fixed inventory, expansion/comparison tools | `393676ef8920e56a00925d9e78cdf1eb81c16b34` |
| [#3](https://github.com/Deadecho1/taktik-echo/pull/3) | Expansion pilot | `36c704ed2ab1b8c1569256250855f3d2e4c48f05` |
| [#4](https://github.com/Deadecho1/taktik-echo/pull/4) | Header fixtures and XML reader migration | `f5abd12bdc270f9b57a1fff52799f35564fa3a6d` |
| [#5](https://github.com/Deadecho1/taktik-echo/pull/5) | Quote and preview fixtures | `39a76fccb40ca9244c034db0b5d25c34a68e025a` |
| [#6](https://github.com/Deadecho1/taktik-echo/pull/6) | Media and scrolling fixtures | `4fa98ee3fe3dfa9cd0a52b124aa89e87f4724ab9` |
| [#7](https://github.com/Deadecho1/taktik-echo/pull/7) | Detail, coverage, and inspection fixtures | `7faacba2288272a7dcd55ace6475b868c553d38a` |
| [#8](https://github.com/Deadecho1/taktik-echo/pull/8) | Action and navigation fixtures | `2b4f7642a15f8122e042aa1ab4b811b7773defc0` |
| [#9](https://github.com/Deadecho1/taktik-echo/pull/9) | Shared helpers, replay checks, results | `8e0324d5e4fa2755e9322eb43fe7118a1ab2444d` (implementation; later commits finalize this report) |

## Maintained size

The table counts complete stored files, including readable recipes, manifests, the new inventory, loaders, tests, helpers, tooling, workflow, and supporting documentation.
It includes relocated helper code once, in its final category.
It excludes only temporary migration evidence and private capture provenance.

| Category | Lines before | Lines after | Bytes before | Bytes after |
| --- | ---: | ---: | ---: | ---: |
| Native XML and recipes | 86,595 | 60,864 | 24,817,688 | 16,863,514 |
| Fixture metadata and hash inventory | 2,230 | 2,382 | 90,051 | 109,355 |
| Fixture guides and other assets | 367 | 403 | 36,211 | 38,744 |
| X and evaluator Python | 18,847 | 18,503 | 671,876 | 667,968 |
| Shared harness and shared tests | 959 | 1,345 | 35,141 | 48,749 |
| Comparison tool and CI workflow | 49 | 89 | 1,552 | 2,872 |
| Supporting documentation | 63 | 311 | 2,894 | 19,256 |
| **Total measured scope** | **109,110** | **83,897** | **25,655,413** | **17,750,458** |

Actual net savings are **25,213 maintained lines and 7,904,955 bytes (7.54 MiB)** after all infrastructure and this report.
That is 23.1% of the complete measured scope.
The fixture directory itself falls from 89,192 to 63,649 lines (28.6% smaller), including its new hash inventory, manifests, and guides.

All 580 original case names remain: 272 full XML layouts, 258 explicit derived cases, 50 direct aliases, and zero removed cases.
XML/recipe data alone falls from 86,595 to 60,864 lines, a 25,731-line or 29.7% reduction, and saves 7,954,174 bytes.
The reduction is deliberately below the sizing prototype: bases stay within coherent named sequences, and large or unclear edits retain complete XML.
Four duplicates across separate families remain independent rather than adding distant base dependencies.
The 59 unread candidates and six integrity-only candidates remain retained; there is no removal rationale to infer from the corrected use audit alone.
The local review includes scripts, documentation, dynamic family references, native file reads, and diagnostic/provenance consumers.
No required input moved into ignored storage.

New files include 371 lines / 13,137 bytes of loader and loader tests, a 580-line / 56,054-byte canonical inventory, and 39 lines / 1,280 bytes of comparison tooling.
Fifteen new replay/input helper modules contain 928 lines / 31,552 bytes, mostly relocated from tests; the category totals include both their addition and the removed definitions.
The representation guide adds 37 lines / 2,709 bytes, and this results report and all other documentation changes are included above.
X/evaluator Python shrinks by 344 lines; the combined Python footprint grows slightly once the new checked loader, its tests, and comparison tooling are included.
The net savings therefore come from fixture representation, with simpler shared test infrastructure rather than a lower behavioral test count.

## Equivalence and scenarios

All 580 retained inputs compare equal to the frozen originals after removing only formatting indentation.
The comparison preserves attribute values, semantic text and whitespace, windows, hierarchy, sibling order, selected states, native character metadata, and geometry.
Complete real parser results also match for every case.
Independent Spec reviews repeated the comparisons for the cumulative scrolling conversion and each subsequent feature-family migration.
The fixed input inventory is checked in normal CI without an old checkout, private files, network downloads, or a phone.
Base hashes check stored full XML bytes; manifest/input hashes describe expanded canonical XML, and original capture provenance stays local.

Every original one of the 2,196 X/evaluator scenario and parameter IDs is retained.
The final suite adds three raw replay cases rejecting a covered handle, the system bar, and an unrelated sheet area.
The root harness adds 610 fixture/loader checks, including five malformed-manifest cases introduced during review.
The earlier assessment's 122 native-file-read tests were an instrumentation rerun of existing scenarios, not additional scenarios to add to 2,196.
Ninety-two repeated root fixture-loading functions are removed, and X/evaluator cross-test-module imports fall from 34 to zero.
Phone-operation replays retain their existing seam; raw Android replays still execute through real Phone/TaktikDevice.
The raw Share/Close-sheet oracle uses explicit captured uncovered regions independently of production selection.

## Verification

The final implementation passes the complete browsing workflow selection on Python 3.10 and 3.14: 4,707 passed and two existing shared-test skips on each interpreter.
The offline runs took 330.50 seconds and 276.38 seconds respectively.
The selection includes shared browsing, X, Instagram services, TikTok services, evaluator/build tests, package metadata/requirements, and the 610 loader/input checks.
Wheel and source builds, distribution verification, and repository layout pass on both versions.
These layout/build/distribution checks also passed locally for every preceding published implementation revision.
All eight implementation revisions in the table have successful hosted Python 3.10/3.14 browsing jobs, including full suites, layout, builds, and distribution verification.
The final report-only commit is checked again before delivery; its exact head is recorded in PR metadata and the delivery message.
No normal CI check needs the migration baseline or a live phone.

The supplemental legacy screen-shape audit has pre-existing findings for hand-written minimal trees and native capture formats that omit ordinary dump attributes.
Its original seven findings become six stored-file findings because `badge-ordinary` is now a recipe; the expanded input is unchanged and remains covered by canonical integrity and parser-equivalence checks.
These findings are outside the browsing CI gate, and no native attributes were invented to silence them.
The repository-layout audit, scoped Ruff and formatting checks, whitespace checks, and changed-document link checks pass.

The isolated X/evaluator run used the same installed Python 3.12 environment before and after migration.
Original main passed 2,196 tests in 171.36 seconds; the final implementation passed 2,199 tests in 166.13 seconds.
The three added rejection cases are included in the latter count.
This single-run comparison shows no significant runtime regression; the small difference is within normal run-to-run variation.
Compatibility matrices were also run concurrently during development, so those wall times are not used as a performance comparison.

## Standards

The code-review skill's Standards reviews have no outstanding findings.
The shared manifest checker initially permitted a missing inventory; it now requires exactly one nonempty inventory and has focused rejection cases.
The other infrastructure and family reviews reported no material Standards findings.

## Spec

The code-review skill's Spec reviews have no outstanding findings.
Review fixes reject unexpected recipe-wrapper text, correct family provenance/hash descriptions, reject missing manifest inventories, and preserve the captured uncovered Close-sheet boundary.
Behavioral assertions, no-op and negative cases, restoration, bounded progress, cancellation, uncertainty, and cleanup remain protected.
Standards: zero open findings; Spec: zero open findings.

## Inspection and local evidence

See the [representation guide](x-fixture-representation.md) and [test harness guide](../../tests/README.md).
Expand any case with `PYTHONPATH=tests:. python -m unit.x_fixtures expansion/wrapped-expanded.xml`.
The local evidence directory `/tmp/x-refactor-evidence/` contains original fixtures and manifests, frozen scenario IDs, per-case conversion inventories, corrected use/reference review, equivalence outputs, measurements, offline logs, and hosted revision/CI records.
Private capture/provenance mappings are not published.
Further reduction of retained full layouts or removal candidates is deferred where it would complicate review or require a separate behavioral/provenance decision.

## Deferred removal candidates

These are the baseline corrected-audit classifications.
Every listed case remains maintained, pending a separate behavioral and provenance decision.
No case is removed or renamed.

Unread in the audited X/evaluator suites:

```text
ai-covered-footer-selected.xml
ai-label-footer-ready.xml
ai-label-footer-selected.xml
article-play-control-ready.xml
article-play-control-selected.xml
bodyless-clipped-grok-first.xml
bodyless-clipped-grok-ready.xml
bodyless-clipped-grok-selected.xml
captionless-credit-entry-selected.xml
captionless-credit-fade-selected.xml
clipped-handle-age-loss-selected.xml
clipped-name-only-ready.xml
clipped-name-only-selected.xml
clipped-name-overhang-selected.xml
covered-header-credit-quote-selected.xml
covered-unbadged-header-first.xml
covered-unbadged-header-ready.xml
covered-unbadged-header-second.xml
covered-unbadged-header-selected.xml
covered-unbadged-header-third.xml
footer-gif-padding-ready.xml
footer-gif-padding-selected.xml
gif-quote-video-padding-ready.xml
gif-quote-video-padding-selected.xml
hidden-credit-quote-entry-selected.xml
live-badge-tail-selected.xml
market-quote-entry-ready.xml
market-quote-entry-selected.xml
nested-quote-tail-first.xml
nested-quote-tail-reread.xml
nested-quote-tail-selected.xml
offscreen-quote-count-selected.xml
offscreen-quote-padding-before.xml
offscreen-quote-translation-before.xml
offscreen-quote-translation-selected.xml
offscreen-quote-video-selected.xml
optional-quote-play-selected.xml
parallel-video-row-first.xml
parallel-video-row-selected.xml
progressing-unobservable-posts-ready.xml
quote-missing-handle-ready.xml
quote-missing-handle-selected.xml
quoted-reply-annotation-before.xml
quoted-reply-annotation-selected.xml
scheduled-sports-card-selected.xml
sports-card-first.xml
sports-card-second.xml
sports-card-selected.xml
translated-body-video-gap-first.xml
translated-body-video-gap-selected.xml
translated-quote-text-tail-first.xml
translated-quote-text-tail-fourth.xml
translated-quote-text-tail-ready.xml
translated-quote-text-tail-second.xml
translated-quote-text-tail-selected.xml
translated-quote-text-tail-third.xml
translated-quoted-reply-selected.xml
video-only-quote-ready.xml
video-only-quote-selected.xml
```

Read only by baseline integrity checks:

```text
detail/long-ordinary.xml
engagement/follow-toast.xml
expansion/expanded-reread.xml
inspection/thread-initial.xml
links/copy-stable.xml
links/top-return.xml
```
