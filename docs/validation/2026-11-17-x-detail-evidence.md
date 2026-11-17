# Native X main-detail reads

The main detail author, caption, media, and supported quoted content are now independently available through native accessibility on the tested X version.
No OCR content extraction was added.
The ordinary XML reader stays pure; it can also interpret the enhanced native hierarchy and its character geometry.

## Native evidence and execution

Ordinary, deep, compressed, and Android view dumps omitted the main author and body in probe `20261117T142420.457883Z`.
Probe `20261117T170521.661567Z` isolated the missing setting: requesting touch exploration exposed native author, body, and media nodes; changing spoken feedback alone did not.
The shared reader temporarily requests accessibility flags, reuses UIAutomator2's hierarchy writer, restores the original flags, and disconnects.
The host restarts its owned UIAutomator server, restores its configurator, removes the temporary DEX, and rechecks cancellation and the deadline before returning data.
An existing server owned by another session is not stopped.
Transport uncertainty is preserved, and actions are never blindly retried.

The enhanced hierarchy groups replies differently from ordinary XML.
The X reader retains ordinary reply subtrees only when the main timestamp, thread controls, and geometry agree across reads.
Loaded reply actions cannot be attributed to the main post.
Main and quoted authorship remain separate, and unsupported layouts retain an explicit reason.

## Interfaces and visibility

`X.inspect_thread()` and `XBrowser.inspect_thread()` return the independent main snapshot in `detail.main_post`, separate reply posts, and the original source content key.
`main_verified` requires matching source identity/content and an observable native main snapshot.
A complete, independently read expanded caption can differ from the collapsed source while retaining the verified source prefix and occurrence.
The main snapshot has its own local content key; it does not acquire an invented post ID or URL.

`main_text` is the observed contiguous caption prefix.
`main_text_complete` reports complete caption coverage independently of the initial snapshot's visibility.
The native reader requests Android character rectangles and retains only unambiguous node matches with unchanged text and bounds.
The parser excludes characters clipped by the viewport or covered by controls, handles Android UTF-16 offsets, and uses complete visible lines as independent movement anchors.
Missing or malformed character metadata cannot establish coverage.
The native character request is bounded to 20,000 UTF-16 units per node.
Longer captions remain partial when this evidence is unavailable.

Full text coverage does not prove visibility of offscreen media or quoted content, and it never changes the clipped initial `Post.body_complete` flag.
A bounded thread report always retains `complete=False`; it does not assert exhaustive replies or conversation coverage.
Inline `read_more` retains its previously published interface and visibility limits.
Its existing control-location OCR is separate from this native content path.

## Physical validation

All runs used the coordinated Pixel 4a, X `12.42.0-prod.01`, Android 13, English, 1080 × 2340, UIAutomator2 `3.3.3`, and verified account `@NirGalel`.
Reservations, both persona locks, the device lock, deadlines, cancellation, keyboard restoration, and cleanup remained in force.

- `20261117T171446.947726Z`: independent NASA image detail, shared native reader restoration, and verified source return.
- `20261117T174624.305743Z`: OpenAI detail exposed 551 caption characters from a 276-character collapsed source and returned to the same occurrence.
- `20261117T174803.087286Z`: captured separate outer and quoted OpenAI content with quoted video; the captured Play-overlay regression now parses and verifies source attribution.
- `20261117T175019.447060Z`: complete video workflow passed main verification, two thread scrolls, toolbar restoration, source return, media capture, and cleanup.
- `20261117T175808.997895Z`: video workflow also passed a second inspection of the same occurrence after the scrolled visit.
- `20261117T181258.383790Z`: image workflow passed main verification, two thread scrolls, repeated inspection, gallery capture, and verified returns.
- `20261117T182456.960908Z`: quoted OpenAI main content was independently verified; a forward scroll hid its author, bounded reverse movement restored the observable native author header, and the visit returned to its source.
- `20261117T175510.213811Z`: Android's character-location API returned visible rectangles and null entries for the unexposed part of the 1,857-character caption.
- `20261117T180025.178556Z`: the packaged native reader exposed character geometry; only 727 characters were observed inside the initial content viewport.
- `20261117T180307.995384Z`: eight verified forward scrolls covered all 1,857 caption characters, restored Back, and returned to the original source occurrence.
  `main_text_complete=True` while the initial snapshot correctly retained `main_verified=False` and `body_complete=False`.

Short reverse gestures were consumed by the collapsed toolbar and snapped closed without moving content.
The isolated comparison ruled out the temporary reader as the cause.
Probe `20261117T174217.456654Z` restored Back with one 300-pixel control-free gesture and independently measured 312 pixels of timestamp movement.
The return planner now selects a sufficiently long continuous region, retaining its existing eight-attempt bound.
A retained detail position is restored until the native author header is positively visible before inspection.
Reverse movement must be verified whenever the header remains unavailable.
X's missing backward accessibility action is not treated as proof that the list is at its beginning.

Raw XML, events, and local screenshots remain under ignored `tests/smoke/x-detail-probes/` and `tests/smoke/x-inspection-runs/`.
Sanitized captured regression fixtures and source SHA-256 records are versioned under `tests/unit/social_media/x/fixtures/detail/`.
No live-feed screenshot was loaded into the coding conversation.
Human visual review of these new captures remains separate and pending.

## Build and checks

The wheel includes the native Java source, DEX, and a manifest linking the source, artifact, and supplied R8 compiler hashes.
Rebuild with `scripts/build/build_accessibility_reader.py --java-home JDK --r8 R8_JAR`.
The asset targets Android API 26 or newer and uses the installed UIAutomator2 library.
The wheel's native assets were compared byte-for-byte with the working source.

The broad shared/X/Instagram-service/TikTok-service suite passed 3,131 tests with 2 skipped.
The final X, Phone, and file-transfer focused suite passed 1,505 tests after the header-restoration refinement.
The file-transfer guard now allows only MediaStore publication and the native reader's private temporary DEX; reader tests enforce the exact temporary path pattern.
Review and final publication results are recorded with the published revision.
