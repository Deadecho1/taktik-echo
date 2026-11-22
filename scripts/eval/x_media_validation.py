"""Keep unsupported media pending without dispatching invalid inspections."""

from functools import partial

from taktik.core.shared.behavior.tap import free_tap_zone
from taktik.core.social_media.x.services.browsing.navigation import _free_regions


def _skip_reason(source, index, screen):
    media = source.media[index]
    if index > 3:
        return "unsupported_index"
    visibility = media.visibility
    if not visibility.accessible or visibility.visible_bounds is None:
        return "unavailable_media"
    if not any(_free_regions(visibility.visible_bounds, visibility.overlaps, 1)):
        return "covered_media"
    if media.kind != "image":
        return None
    if sum(p.content_key == source.content_key for p in screen.posts) != 1:
        return "ambiguous_source"
    if not media.description:
        return "missing_description"
    if sum(m.description == media.description for m in source.media) != 1:
        return "ambiguous_description"
    targets = [t for t in source.targets if t.label == f"Open media {index}"]
    if len(targets) != 1:
        return "missing_or_ambiguous_target"
    target = targets[0].visibility
    if not target.accessible or target.visible_bounds is None:
        return "unavailable_target"
    viewport = screen.content_viewport
    minimum = (viewport[2] - viewport[0]) * 0.04
    regions = [
        region
        for region in _free_regions(target.visible_bounds, target.overlaps, minimum)
        if region[3] - region[1] >= minimum
    ]
    if not regions:
        return "covered_target"
    region = max(regions, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    if free_tap_zone(region, target.overlaps) is None:
        return "covered_target"
    return None


def select_media_check(browser, observation, *, features, skipped):
    """Return one named inspection; the caller credits it only after it returns."""
    browser.observe(previous=observation)
    app = browser.browser
    source = app.observe()
    for index, media in enumerate(source.media):
        if media.kind not in {"image", "video", "gif"} or media.kind in features:
            continue
        reason = _skip_reason(source, index, app._screen)
        if reason is not None:
            skipped(
                {
                    "source_identity": observation.identity,
                    "source_key": source.content_key,
                    "kind": media.kind,
                    "index": index,
                    "reason": reason,
                }
            )
            continue
        return media.kind, partial(
            browser.inspect, observation, index=index, frame_count=2, interval=1
        )
    return None
