# Operating and validating the native X extension

The extension supplies Android browsing and verified interaction through an existing `Phone` session.
Its detailed observation and action contracts are in [verified-browsing.md](verified-browsing.md).
Consumer policy, model calls, retained persona state, and dependency adoption remain outside Taktik.

## Supported environment and remaining evidence

Direct validation covers English X `12.42.0-prod.01` on a Pixel 4a running Android 13 at 1080 × 2340.
Older captured reader fixtures also cover `12.41.0-prod.01`; this does not establish complete physical support on other versions or devices.
The native reader's minimum Android API 26 is a binary requirement, not a claim that X browsing has been validated on every Android version since 8.0.
Host execution requires ADB access to the authorized phone and the existing Taktik Keyboard setup.
The shared session locks use `fcntl`; the browsing compatibility workflow runs on Linux.
Python compatibility is checked at the package's minimum 3.10 and the launcher's 3.14 runtime.

For you, Following, Top/Latest search, bounded profile/thread/media inspection, native detail text, engagement, and explicit native post-link capture have recorded physical evidence.
Paid partnership and media-tag labels remain separate from author and caption attribution.
Native promoted/ad recognition still lacks a captured source, and the absence of a disclosure does not establish organic content.
Inline `read_more` uses the existing optional local Tesseract locator; native detail reading provides the implemented path that reads content without OCR.
Long-caption completeness is reported separately from the visibility of the original detail snapshot.
Raw screenshots stay local for human review; XML and replay results do not replace that review.
See the [layout coverage record](validation/2026-11-20-x-layout-coverage.md) for the remaining ad evidence and [native detail record](validation/2026-11-17-x-detail-evidence.md) for caption limits.

## Session lifecycle

The consumer checks controller reservations and holds its account/persona lock together with `phone_interaction.locks.device_lock(serial)` before connecting.
Create one `Phone`, configure its deadline and cancellation callback, and pass that same object to the platform browser.
Close the phone and check its cleanup result before releasing those locks.
An uncertain cleanup requires operator attention; it is not evidence that the original keyboard or service was restored.

Within that already-owned session, a bounded read uses the public interface:

```python
from taktik.core.social_media.x.services.browsing import XBrowser

browser = XBrowser(phone, {"for_you", "following", "search"})
browser.start(account, "search", target="from:NASA -filter:replies")
observation = browser.observe()
# The consumer decides what to do with the structured observation.
browser.advance()
next_observation = browser.observe()
```

`start` verifies the account through the drawer and establishes a new browsing occurrence.
The reader supports the native "Bookmarks, Likes, and Offline videos moved here" drawer tip as a separately owned X window with narrowly validated structure and content.
The tip remains an exclusion for underlying visibility and tap geometry; unknown extra windows and conflicting overlays remain unsupported.
Startup verifies the unobscured account, uses the current native drawer-close target, and requires a verified return to Home before source selection.
A persistent tip or uncertain close outcome does not trigger another tap.
Home startup may reset its timeline once after exhausting four initial framing attempts, using only revealed native Home controls and independently reverified timeline/post evidence.
The second framing search has the same bound; failed or uncertain reset actions are not repeated.
The resulting `home_reset` navigation gap does not establish continuity through the abandoned content.
Search query entry verifies exact text and context before submission; the lower-level `X` also accepts `result_tab="latest"`.
Only a recognized native empty state produces `FeedEmpty`; a missing or unsupported post does not establish an empty feed.
Each action requires the current observation, and engagement may itself select a successor.
When `ActionResult.advanced` is true, observe that successor without advancing again or reusing the old observation.
Native IDs/URLs remain unknown until explicit `copy_link` succeeds and never replace local occurrence/content keys.
Profile, detail, media, and Share visits return only after verifying their source context.

Treat `Status.UNCERTAIN` as an unknown execution outcome, and do not replay the action automatically.
Recovery is explicit and rechecks account and browsing context; it starts a new position.
`InteractionCancelled` and `SessionExpired` escape retry loops and must still permit narrowly scoped cleanup.
The temporary native accessibility reader preserves these interruptions and prior transport uncertainty when restoration also fails.
Restoration still attempts removal of its temporary asset, and a new interruption during restoration remains an interruption.
The eight-attempt pending/no-progress bounds and 32-gesture advance limit also remain subject to the Phone deadline.

## Caption validation

The maintained caption-validation workflow is `scripts/eval/x_caption_validation.py`.
Call `check_caption(browser, observation, features=features, covered=covered)` on an observable, unquoted Show more source within the already-owned Phone session.
The `features` mapping holds successful evidence-event counts, and `covered(name, details)` increments that mapping and persists the supplied evidence.
The helper alternates inline attempts with bounded native-detail attempts until the corresponding coverage is established.
After a verified inline viewport limit it explicitly recovers, records both occurrence identities, and retains `original_text_complete=false` for the abandoned source.
It never marks that event as `read_more` or a successful native-text read.
Native-detail attempts use at most eight scrolls and award `native_main_text` or `native_long_caption` only from observed character coverage, independently of whether the initial detail snapshot fits the viewport.
Successful supported inline expansion remains a separate `read_more` requirement.
Other errors and interruptions propagate to the session owner's normal cleanup path.
The local all-feature soak calls this maintained helper and requires both `read_more` and `native_long_caption`; raw captures and device-specific orchestration remain local.
The [long-caption follow-up validation](validation/2026-11-20-x-long-caption-fix.md) records the replay evidence and remaining physical requirements.

## Reproducible compatibility checks

Run these commands from a clean checkout in a virtual environment using Python 3.10 or 3.14:

```bash
python -m pip install -c requirements.lock -r requirements-dev.txt build
python -m pytest -o addopts='' -q \
  tests/unit/shared tests/unit/social_media/x \
  tests/unit/social_media/instagram/services \
  tests/unit/social_media/tiktok/services tests/unit/scripts/build tests/unit/scripts/eval \
  tests/unit/test_package_metadata.py tests/unit/test_package_requirements.py
python scripts/audits/audit_tree_layout.py
python -m build --no-isolation
python scripts/build/verify_browsing_distribution.py dist/*.whl dist/*.tar.gz
```

The [Browsing compatibility workflow](../.github/workflows/browsing.yml) runs the same checks on pull requests and pushes to `main` or `feature/x-platform`.
These checks use fixtures and simulated device transports; they do not connect to a phone or call external models.
`python -m build` first creates the source distribution and then builds a wheel from that archive.
The archive therefore must include `requirements.txt`, which `setup.py` reads to declare runtime dependencies.
The artifact verifier checks exact browsing source bytes, the native Java/DEX/manifest files, package markers, and source-installation inputs against the checkout.
It rejects missing files, outdated archives, and native assets that disagree with their build manifest.

Before consumer adoption, publish the tested complete fork revision and pin that revision in the consumer's own plan.
The open native-ad and human-review requirements remain explicit merge/release considerations even when automated checks pass.
Preparing or publishing the extension branch does not update consumer pins or establish those missing evidence claims.
