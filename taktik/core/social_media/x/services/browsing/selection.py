"""Fresh selected-post evidence and control-free action targets."""

from dataclasses import replace

from taktik.core.shared.phone_interaction import Result, Status

from .navigation import XError, _free_regions, _intersection


def _unsupported(message):
    raise XError(message, result=Result(Status.UNSUPPORTED, detail=message))


def _source(app):
    source = app.observe()
    if source is None:
        _unsupported("An X action requires a selected post.")
    if sum(p.content_key == source.content_key for p in app._screen.posts) != 1:
        _unsupported("The selected X action target is ambiguous.")
    return source


def _tap_visibility(target):
    control, glyph = target.visibility, target.glyph_visibility
    if glyph is None:
        return control
    if (
        not glyph.accessible
        or glyph.visible_bounds is None
        or _intersection(glyph.bounds, control.bounds) != glyph.bounds
        or _intersection(glyph.visible_bounds, glyph.bounds) != glyph.visible_bounds
        or _intersection(glyph.visible_bounds, control.visible_bounds)
        != glyph.visible_bounds
    ):
        _unsupported(f"No visible owned X {target.label} glyph.")
    return replace(
        glyph, overlaps=tuple(dict.fromkeys((*control.overlaps, *glyph.overlaps)))
    )


def _clipped_share_strip(target):
    control, glyph = target.visibility, target.glyph_visibility
    if (
        target.label != "Share"
        or glyph is None
        or glyph.visible_bounds != glyph.bounds
        or len(control.overlaps) != 1
        or control.visible_bounds[2] != control.bounds[2]
    ):
        return None
    left, top, right, bottom = glyph.bounds
    height = bottom - top
    cover = control.overlaps[0]
    if not (
        0 < right - left < height
        and cover[0] <= control.bounds[0]
        and cover[1] <= top < bottom <= cover[3]
        and cover[2] == left
    ):
        return None
    # The retained glyph edge and its full height bound the proven right strip.
    region = max(left, control.bounds[2] - height), top, control.bounds[2], bottom
    if region[0] >= right or _intersection(region, control.visible_bounds) != region:
        return None
    return region


def _control(targets, label):
    matches = [t for t in targets if t.label == label]
    if len(matches) != 1 or matches[0].visibility.visible_bounds is None:
        _unsupported(f"No unique visible X {label} control.")
    target = matches[0]
    visibility = _tap_visibility(target)
    candidates = [visibility.visible_bounds]
    strip = _clipped_share_strip(target)
    if strip is not None:
        candidates.append(strip)
    for candidate in candidates:
        regions = [
            r
            for r in _free_regions(candidate, visibility.overlaps, 12)
            if r[3] - r[1] >= 12
        ]
        if regions:
            return target, max(regions, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    _unsupported(f"No uncovered X {label} target.")


def _tap(app, targets, label):
    target, region = _control(targets, label)
    app.phone.tap(region, exclude=_tap_visibility(target).overlaps).require()


def _post(app, source, screen):
    if screen.kind == "unsupported":
        return None
    app._check_timeline(screen, app._screen)
    candidates = [
        p
        for p in screen.observable_posts
        if p.content_key == source.content_key
        and p.author == source.author
        and p.visibility.bounds == source.visibility.bounds
    ]
    if len(candidates) != 1:
        return None
    app._refresh_alignment(screen)
    if app._index is None or screen.posts[app._index] != candidates[0]:
        raise XError("The X action occurrence changed.")
    return candidates[0]
