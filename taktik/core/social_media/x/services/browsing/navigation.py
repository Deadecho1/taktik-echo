"""Account-verified X timeline browsing through a session-owned Phone.

This browsing seam returns parsed Posts for the persona adapter.
The caller owns device reservations, locks, the deadline, and Phone.close().
"""

from contextlib import contextmanager
from dataclasses import replace
from itertools import pairwise

from taktik.core.shared.phone_interaction import InteractionError, Phone
from taktik.core.social_media.x.ui.screen import (
    ACTION_LABELS,
    HANDLE,
    PACKAGE,
    PostFragment,
    Screen,
    TextSpan,
    read_screen,
)

TIMELINES = {"for_you": "For you", "following": "Following"}
READ_ATTEMPTS = 8
SCROLL_ATTEMPTS = 4
RESTORE_ATTEMPTS = 8
ADVANCE_SCROLL_ATTEMPTS = 8
ADVANCE_READ_ATTEMPTS = 3


class XError(InteractionError):
    """X could not establish a navigation or browsing outcome."""


def _intersection(a, b):
    result = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return result if result[0] < result[2] and result[1] < result[3] else None


def _free_regions(area, exclusions, minimum_width):
    """Continuous rectangles only; Phone remains responsible for path sampling."""
    boxes = [box for rect in exclusions if (box := _intersection(area, rect))]
    edges = sorted({area[0], area[2], *(x for box in boxes for x in (box[0], box[2]))})
    for i, left in enumerate(edges):
        for right in edges[i + 1 :]:
            if right - left < minimum_width:
                continue
            blocked = sorted(
                (b[1], b[3]) for b in boxes if b[0] < right and b[2] > left
            )
            top = area[1]
            for start, end in blocked:
                if start > top:
                    yield left, top, right, start
                top = max(top, end)
            if top < area[3]:
                yield left, top, right, area[3]


def scroll_region(screen):
    viewport = screen.content_viewport
    if screen.kind != "home" or viewport is None:
        raise XError("X scrolling requires a recognized Home viewport.")
    width, height = viewport[2] - viewport[0], viewport[3] - viewport[1]
    exclusions = (
        *screen.overlaps,
        *(rect for area in screen.scroll_areas for rect in area.exclusions),
    )
    regions = []
    for candidate in screen.scroll_areas:
        area = candidate.visibility.visible_bounds
        if area is None:
            continue
        regions.extend(
            rect
            for rect in _free_regions(area, exclusions, width * 0.08)
            if rect[3] - rect[1] >= width * 0.1
        )
    if not regions:
        raise XError(
            "No continuous X scroll region excludes nested controls and media."
        )
    region = max(regions, key=lambda r: (r[3] - r[1], r[2] - r[0]))
    distance = min(height * 0.3, (region[3] - region[1]) * 0.6)
    return region, distance, exclusions


def _position(post):
    if post.body_visibility is not None:
        return post.header_visibility.bounds[1], post.body_visibility.bounds[1]
    return (
        post.header_visibility.bounds[1],
        *(m.visibility.bounds[1] for m in post.media),
    )


def _fragment_media_content(media):
    return [
        (m.kind, m.description, m.source_label, m.preview_text)
        if m.kind in {"link_preview", "preview"}
        else (m.kind, m.description)
        for m in media
    ]


def _same_body(a, b):
    return a.body == b.body and a.body_annotations == b.body_annotations


def _same_content(a, b):
    if not isinstance(a, PostFragment) and not isinstance(b, PostFragment):
        return a.content_key == b.content_key
    return (
        (
            a.body is not None
            or (a.quoted_post is not None and b.quoted_post is not None)
        )
        and _same_body(a, b)
        and (
            a.translation is None
            or b.translation is None
            or a.translation == b.translation
        )
        and (
            a.body_visibility is None
            or b.body_visibility is None
            or a.body_visibility.bounds[::2] == b.body_visibility.bounds[::2]
        )
        and _quote_content(a.quoted_post) == _quote_content(b.quoted_post)
        and _fragment_media_content(a.media) == _fragment_media_content(b.media)
        and all(
            x.kind != "image" or x.visibility.bounds[::2] == y.visibility.bounds[::2]
            for x, y in zip(a.media, b.media)
        )
    )


def _quote_content(quote):
    if quote is None:
        return None
    return (
        quote.author,
        quote.body,
        quote.translation,
        _fragment_media_content(quote.media),
    )


def _video_tail_source(post):
    if getattr(post, "quoted_body", None) is not None:
        return PostFragment(
            post.quoted_body.text,
            post.media,
            post.visibility,
            post.quoted_body.visibility,
            post.actions,
        )
    quote = post.quoted_post
    if quote and not post.media:
        return PostFragment(
            quote.body,
            quote.media,
            post.visibility,
            quote.body_visibility,
            post.actions,
        )
    return post


def _anchor_pairs(a, b, before, after):
    if getattr(b, "quoted_body", None) is not None:
        a = _quoted_content_source(a)
        if a.body_visibility is None or len(a.media) != 1:
            return ()
        return [
            (x, y)
            for old, new in (
                (a.body_visibility, b.quoted_body.visibility),
                (a.media[0].visibility, b.media[0].visibility),
                *((x.visibility, y.visibility) for x, y in zip(a.actions, b.actions)),
            )
            for x, y in zip(old.bounds[1::2], new.bounds[1::2])
            if before.content_viewport[1] < x < before.content_viewport[3]
            and after.content_viewport[1] < y < after.content_viewport[3]
        ]
    if getattr(b, "preview_texts", ()):
        previous, current = _preview_spans(a), b.preview_texts
        if len(previous) < len(current):
            return ()
        return [
            (x, y)
            for old, new in zip(previous[-len(current) :], current)
            for x, y in zip(old.visibility.bounds[1::2], new.visibility.bounds[1::2])
            if before.content_viewport[1] < x < before.content_viewport[3]
            and after.content_viewport[1] < y < after.content_viewport[3]
        ] + [
            (x.visibility.bounds[1], y.visibility.bounds[1])
            for x, y in zip(a.actions, b.actions)
            if before.content_viewport[1]
            < x.visibility.bounds[1]
            < before.content_viewport[3]
            and after.content_viewport[1]
            < y.visibility.bounds[1]
            < after.content_viewport[3]
        ]
    if (
        isinstance(b, PostFragment)
        and b.body is None
        and not b.media
        and b.quoted_post is None
        and b.community_note is None
    ):
        return [
            (x, y)
            for old, new in zip(a.actions, b.actions)
            for x, y in zip(
                old.visibility.bounds[1:2]
                if old.label == "Share"
                else old.visibility.bounds[1::2],
                new.visibility.bounds[1:2]
                if new.label == "Share"
                else new.visibility.bounds[1::2],
            )
            if before.content_viewport[1] < x < before.content_viewport[3]
            and after.content_viewport[1] < y < after.content_viewport[3]
        ]
    if a.community_note is not None and b.community_note is not None:
        views = [
            (a.community_note.header_visibility, b.community_note.header_visibility),
            (a.community_note.body_visibility, b.community_note.body_visibility),
        ]
        if a.body_visibility is not None and b.body_visibility is not None:
            views.append((a.body_visibility, b.body_visibility))
        views.extend((x.visibility, y.visibility) for x, y in zip(a.media, b.media))
        return [
            (x, y)
            for old, new in views
            for x, y in zip(old.bounds[1::2], new.bounds[1::2])
            if before.content_viewport[1] < x < before.content_viewport[3]
            and after.content_viewport[1] < y < after.content_viewport[3]
        ]
    if isinstance(b, PostFragment) and b.body is None and b.quoted_post is None:
        a = _video_tail_source(a)
    if isinstance(a, PostFragment) or isinstance(b, PostFragment):
        if not (a.quoted_post or b.quoted_post) and any(
            m.kind == "image" for m in (*a.media, *b.media)
        ):
            if a.body_visibility is None or b.body_visibility is None:
                return ()
            return [
                (x, y)
                for old, new in (
                    (a.body_visibility, b.body_visibility),
                    *((x.visibility, y.visibility) for x, y in zip(a.media, b.media)),
                )
                for x, y in zip(old.bounds[1::2], new.bounds[1::2])
                if before.content_viewport[1] < x < before.content_viewport[3]
                and after.content_viewport[1] < y < after.content_viewport[3]
            ]
        if not (a.media or b.media or a.quoted_post or b.quoted_post):
            if a.body_visibility is None or b.body_visibility is None:
                return ()
            pairs = [
                (x, y)
                for x, y in zip(
                    a.body_visibility.bounds[1::2], b.body_visibility.bounds[1::2]
                )
                if before.content_viewport[1] < x < before.content_viewport[3]
                and after.content_viewport[1] < y < after.content_viewport[3]
            ]
            if a.actions and b.actions:
                if tuple(t.label for t in a.actions) != tuple(
                    t.label for t in b.actions
                ):
                    return ()
                pairs.extend(
                    (x.visibility.bounds[1], y.visibility.bounds[1])
                    for x, y in zip(a.actions, b.actions)
                    if before.content_viewport[1]
                    < x.visibility.bounds[1]
                    < before.content_viewport[3]
                    and after.content_viewport[1]
                    < y.visibility.bounds[1]
                    < after.content_viewport[3]
                )
            return pairs
        if a.quoted_post or b.quoted_post:
            pairs = []
            if a.body_visibility and b.body_visibility:
                pairs.extend(
                    zip(a.body_visibility.bounds[1::2], b.body_visibility.bounds[1::2])
                )
            pairs.extend(
                (x.visibility.bounds[1], y.visibility.bounds[1])
                for x, y in zip(a.media, b.media)
            )
            if a.quoted_post and b.quoted_post:
                pairs.extend(zip(_position(a.quoted_post), _position(b.quoted_post)))
            return pairs
        if a.body_visibility is None or b.body_visibility is None:
            return zip(
                (
                    a.media[0].visibility.bounds[3],
                    *(t.visibility.bounds[1] for t in a.actions),
                ),
                (
                    b.media[0].visibility.bounds[3],
                    *(t.visibility.bounds[1] for t in b.actions),
                ),
            )
        return zip(
            (a.body_visibility.bounds[1], *(m.visibility.bounds[1] for m in a.media)),
            (b.body_visibility.bounds[1], *(m.visibility.bounds[1] for m in b.media)),
        )
    pairs = list(zip(_position(a), _position(b)))
    if a.quoted_post and b.quoted_post:
        pairs.extend(zip(_position(a.quoted_post), _position(b.quoted_post)))
    return pairs


def _tail_anchors_available(post, viewport):
    return (
        not getattr(post, "quoted_post", None)
        and len(post.media) == 1
        and post.media[0].kind in {"video", "gif"}
        and tuple(t.label for t in post.actions) == ACTION_LABELS
        and viewport[1] < post.media[0].visibility.bounds[3] < viewport[3]
        and all(
            viewport[1] < t.visibility.bounds[1] < viewport[3] for t in post.actions
        )
    )


def _tail_match(
    a, b, before, after, *, require_overlap=False, allow_hidden_source=False
):
    if (
        not isinstance(b, PostFragment)
        or b.body is not None
        or b.quoted_body is not None
    ):
        return False
    outer_quote = a.quoted_post
    a = _video_tail_source(a)
    if not all(
        _tail_anchors_available(p, s.content_viewport)
        for p, s in ((a, before), (b, after))
    ):
        return False
    old, new = a.media[0], b.media[0]
    old_rect, new_rect = old.visibility.bounds, new.visibility.bounds
    shift = new_rect[3] - old_rect[3]
    return (
        shift <= 0
        and old.kind == new.kind
        and old.description == new.description
        and (
            (old.source_label, old.source_prefix)
            == (new.source_label, new.source_prefix)
            or (
                allow_hidden_source
                and old.source_label is not None
                and new.source_label is None
                and new.source_prefix is None
            )
            or (
                isinstance(a, PostFragment)
                and old.source_label is not None
                and new.source_label is None
                and new.source_prefix is None
                and old_rect == new_rect
            )
        )
        and old_rect[::2] == new_rect[::2]
        and (
            not require_overlap
            or max(old_rect[1], new_rect[1], before.content_viewport[1])
            < min(old_rect[3], new_rect[3])
        )
        and (
            new_rect[1] < after.content_viewport[1]
            or (
                # The viewport edge can fall in the existing text/video gap.
                # Both video edges must retain their measured displacement;
                # an inset start cannot be explained by clamping or resizing.
                outer_quote is None
                and old_rect[1] >= before.content_viewport[1]
                and abs(new_rect[1] - old_rect[1] - shift) <= 2
                and (a.body_visibility is not None or isinstance(a, PostFragment))
                and (
                    isinstance(a, PostFragment)
                    or a.header_visibility.bounds[3] + shift
                    <= after.content_viewport[1]
                )
            )
        )
        and (
            a.body_visibility is None
            or a.body_visibility.bounds[3] + shift <= after.content_viewport[1]
        )
        and all(
            x.visibility.bounds[::2] == y.visibility.bounds[::2]
            and abs(y.visibility.bounds[1] - x.visibility.bounds[1] - shift) <= 2
            for x, y in zip(a.actions, b.actions)
        )
    )


def _quoted_content_source(post):
    quote = post.quoted_post
    if quote is not None:
        return PostFragment(
            quote.body,
            quote.media,
            post.visibility,
            quote.body_visibility,
            post.actions,
        )
    return _video_tail_source(post)


def _quoted_tail_match(a, b, before, after):
    current = getattr(b, "quoted_body", None)
    if current is None or b.body is not None or b.quoted_post is not None:
        return False
    quote = a.quoted_post
    if quote is not None:
        if quote.nested_quote is not None:
            return False
    elif getattr(a, "quoted_body", None) is None:
        return False
    source = _quoted_content_source(a)
    if (
        source.body != current.text
        or source.body_visibility is None
        or not all(
            len(p.media) == 1
            and p.media[0].kind in {"video", "preview"}
            and tuple(t.label for t in p.actions) == ACTION_LABELS
            and s.content_viewport[1]
            < p.media[0].visibility.bounds[3]
            < s.content_viewport[3]
            for p, s in ((source, before), (b, after))
        )
    ):
        return False
    old, new = source.media[0], b.media[0]
    shift = new.visibility.bounds[3] - old.visibility.bounds[3]
    lost = []
    if quote is not None:
        lost.append(quote.header_visibility)
        lost.extend(m.visibility for m in a.media)
        if a.body_visibility is not None:
            lost.append(a.body_visibility)
        if not isinstance(a, PostFragment):
            lost.append(a.header_visibility)
    return (
        shift <= 0
        and _fragment_media_content((old,)) == _fragment_media_content((new,))
        and (
            (old.source_label, old.source_prefix)
            == (new.source_label, new.source_prefix)
            or (new.source_label is None and new.source_prefix is None)
        )
        and all(v.bounds[3] + shift <= after.content_viewport[1] for v in lost)
        and all(
            (x is None and y is None)
            or (
                x is not None
                and y is not None
                and x.bounds[::2] == y.bounds[::2]
                and all(
                    abs(v - u - shift) <= 2 or (v == 0 and u + shift <= 0)
                    for u, v in zip(x.bounds[1::2], y.bounds[1::2])
                )
            )
            for x, y in (
                (source.body_visibility, current.visibility),
                (old.visibility, new.visibility),
                (old.description_visibility, new.description_visibility),
                (old.preview_text_visibility, new.preview_text_visibility),
                *(
                    (x.visibility, y.visibility)
                    for x, y in zip(source.actions, b.actions)
                ),
            )
        )
    )


def _quote_header_completed(a, b, before, after):
    old, new = a.quoted_post, b.quoted_post
    if (
        old is None
        or new is None
        or old.body is not None
        or old.media
        or (new.body is None and not new.media)
        or (new.body is not None and new.body_visibility is None)
        or old.header_visibility.bounds[1] < before.content_viewport[3]
        or old.header_visibility.bounds[3] > old.visibility.bounds[3]
        or old.author != new.author
        or old.labels != new.labels
        or old.translation != new.translation
        or a.body is None
        or not _same_body(a, b)
        or a.body_visibility is None
        or b.body_visibility is None
        or a.body_visibility.bounds[::2] != b.body_visibility.bounds[::2]
        or _fragment_media_content(a.media) != _fragment_media_content(b.media)
        or (
            not isinstance(b, PostFragment)
            and (isinstance(a, PostFragment) or a.author != b.author)
        )
    ):
        return False
    shifts = [
        y - x
        for x, y in zip(a.body_visibility.bounds[1::2], b.body_visibility.bounds[1::2])
        if before.content_viewport[1] < x < before.content_viewport[3]
        and after.content_viewport[1] < y < after.content_viewport[3]
    ]
    if not shifts or max(shifts) - min(shifts) > 2:
        return False
    shift = max(shifts)
    return (
        shift < -2
        and _header_loss_explained(a, b, shift, after)
        and old.header_visibility.bounds[::2] == new.header_visibility.bounds[::2]
        and new.header_visibility.bounds[1] - old.header_visibility.bounds[1] == shift
        and (
            new.header_visibility.bounds[3] - old.header_visibility.bounds[3] == shift
            or (
                old.header_visibility.bounds[3] == old.visibility.bounds[3]
                and new.header_visibility.bounds[3] - shift
                >= old.header_visibility.bounds[3]
            )
        )
        and (
            new.body_visibility is None
            or new.body_visibility.bounds[1] - shift >= old.visibility.bounds[3]
        )
        and all(
            m.visibility.bounds[1] - shift >= old.visibility.bounds[3]
            for m in new.media
        )
        and all(
            x.visibility.bounds[::2] == y.visibility.bounds[::2]
            and all(
                abs(v - u - shift) <= 2
                or (v == 0 and u + shift <= 0)
                or (u >= before.content_viewport[3] and v >= after.content_viewport[3])
                for u, v in zip(x.visibility.bounds[1::2], y.visibility.bounds[1::2])
            )
            for x, y in zip(a.media, b.media)
        )
    )


def _quote_media_revealed(a, b):
    if isinstance(a, PostFragment) or isinstance(b, PostFragment):
        return False
    old, new = a.quoted_post, b.quoted_post
    if not old or not new or old.body_visibility is None or new.body_visibility is None:
        return False
    shift = new.body_visibility.bounds[1] - old.body_visibility.bounds[1]
    return (
        a.author == b.author
        and _same_body(a, b)
        and [(m.kind, m.description) for m in a.media]
        == [(m.kind, m.description) for m in b.media]
        and old.author == new.author
        and old.body == new.body
        and old.translation == new.translation
        and not old.media
        and bool(new.media)
        and not old.body_visibility.unobscured
        and shift < -2
        and all(
            m.visibility.bounds[1] - shift >= old.visibility.bounds[3]
            for m in new.media
        )
    )


def _unseen_quote_header(quote):
    return quote is None or (
        quote.body is None
        and not quote.media
        and quote.visibility.visible_bounds is None
        and quote.header_visibility.visible_bounds is None
    )


def _revealed_content(a, b):
    if isinstance(a, PostFragment) or isinstance(b, PostFragment):
        return False
    same_media = [(m.kind, m.description) for m in a.media] == [
        (m.kind, m.description) for m in b.media
    ]
    return (
        a.author == b.author
        and _same_body(a, b)
        and a.quoted_post is None
        and a.body_visibility is not None
        and not a.body_visibility.unobscured
        and (
            (not a.media and bool(b.media) and _unseen_quote_header(b.quoted_post))
            or (same_media and b.quoted_post is not None)
        )
    )


def _media_revelation_anchored(a, b):
    if (
        isinstance(a, PostFragment)
        or isinstance(b, PostFragment)
        or a.author != b.author
        or a.body is None
        or not _same_body(a, b)
        or a.translation != b.translation
        or a.quoted_post is not None
        or not _unseen_quote_header(b.quoted_post)
        or a.media
        or a.actions
        or not b.media
        or not (
            all(m.kind == "image" for m in b.media)
            or (
                len(b.media) == 1
                and b.media[0].kind == "video"
                and b.media[0].description == "Video"
            )
        )
        or a.body_visibility is None
        or b.body_visibility is None
        or not a.body_visibility.clipped
        or not b.body_visibility.accessible
        or b.body_visibility.clipped
        or b.body_visibility.visible_bounds != b.body_visibility.bounds
        # The body start measures movement alongside the intact header. A
        # lower overlay still prevents observation, but cannot hide this anchor.
        or any(r[1] <= b.body_visibility.bounds[1] for r in b.body_visibility.overlaps)
        or a.body_visibility.bounds[::2] != b.body_visibility.bounds[::2]
        or a.visibility.visible_bounds is None
        or a.visibility.bounds[3] <= a.visibility.visible_bounds[3]
        or a.body_visibility.bounds[3] != a.visibility.bounds[3]
    ):
        return False
    shifts = [b.body_visibility.bounds[1] - a.body_visibility.bounds[1]]
    for old, new in (
        (a.header_visibility, b.header_visibility),
        (a.author_visibility, b.author_visibility),
    ):
        if (
            not old.unobscured
            or not new.unobscured
            or old.bounds[::2] != new.bounds[::2]
        ):
            return False
        shifts.extend(y - x for x, y in zip(old.bounds[1::2], new.bounds[1::2]))
    # Only the retained header and body start measure motion; the body end was clipped.
    return (
        max(shifts) < -2
        and max(shifts) - min(shifts) <= 2
        and all(
            m.visibility.bounds[1] - max(shifts) >= a.visibility.bounds[3]
            for m in b.media
        )
        and (
            b.quoted_post is None
            or b.quoted_post.visibility.bounds[1] - max(shifts)
            >= a.visibility.bounds[3]
        )
    )


def _header_loss_explained(a, b, shift, after):
    if not isinstance(b, PostFragment) or isinstance(a, PostFragment):
        return True
    if a.header_visibility.bounds[3] + shift <= after.content_viewport[1]:
        return True
    header = b.covered_header_visibility
    if header is None or header.bounds[::2] != a.header_visibility.bounds[::2]:
        return False
    if any(
        abs(y - x - shift) > 2
        for x, y in zip(a.header_visibility.bounds[1::2], header.bounds[1::2])
    ):
        return False
    x1, y1, x2, y2 = a.author_visibility.bounds
    projected = (x1, y1 + shift, x2, y2 + shift)
    partial = b.covered_handle
    if partial is not None:
        rect = partial.visibility.bounds
        # The retained left slice and the known cover must together account
        # for the entire prior handle. This is continuity evidence only.
        return (
            partial.text == a.author
            and partial.visibility.unobscured
            and rect[0] == projected[0]
            and rect[1::2] == projected[1::2]
            and rect[2] < projected[2]
            and any(
                cover in after.overlaps
                and rect[2] == cover[0]
                and _intersection(projected, cover)
                == (rect[2], projected[1], projected[2], projected[3])
                for cover in header.overlaps
            )
        )
    return any(
        cover in after.overlaps and _intersection(projected, cover) == projected
        for cover in header.overlaps
    )


def _quote_preview_revealed(a, b, after):
    if (
        (
            not isinstance(b, PostFragment)
            and (isinstance(a, PostFragment) or a.author != b.author)
        )
        or (b.translation is not None and a.translation != b.translation)
        or _fragment_media_content(a.media) != _fragment_media_content(b.media)
    ):
        return False
    old, new = a.quoted_post, b.quoted_post
    if (
        not old
        or not new
        or len(new.media) != 1
        or old.body_visibility is None
        or new.body_visibility is None
    ):
        return False
    preview = new.media[0]
    shift = new.body_visibility.bounds[1] - old.body_visibility.bounds[1]
    observable_body = not isinstance(a, PostFragment) and a.observable
    retained_body = (
        not isinstance(a, PostFragment)
        and (observable_body or _quoted_video_motion(a, b, shift))
        and _same_body(a, b)
        and a.body_visibility is not None
        and b.body_visibility is not None
        and a.body_visibility.bounds[::2] == b.body_visibility.bounds[::2]
    )
    previously_lost_body = (
        isinstance(a, PostFragment)
        and isinstance(b, PostFragment)
        and a.body is None
        and b.body is None
        and a.body_visibility is None
        and b.body_visibility is None
        and _same_body(a, b)
        and a.translation == b.translation
        and _quoted_video_motion(a, b, shift)
    )
    if not (
        retained_body
        or previously_lost_body
        or _preview_body_scrolled_out(a, b, shift, after)
    ):
        return False
    # An incomplete quote can prevent observation even when the outer body
    # survives. Its retained header and video prove motion, while the new card
    # must itself project below the old quote, not merely its title.
    if (
        not observable_body
        and not old.media
        and (
            preview.visibility.bounds[1] - shift < old.visibility.bounds[3]
            or preview.visibility.bounds[::2] != new.visibility.bounds[::2]
            or old.visibility.bounds[::2] != new.visibility.bounds[::2]
        )
    ):
        return False
    return (
        old.author == new.author
        and old.body == new.body
        and old.translation == new.translation
        and old.body_visibility.bounds[::2] == new.body_visibility.bounds[::2]
        and old.header_visibility.bounds[::2] == new.header_visibility.bounds[::2]
        and shift < -2
        and _header_loss_explained(a, b, shift, after)
        and old.visibility.visible_bounds is not None
        and old.visibility.bounds[3] > old.visibility.visible_bounds[3]
        and preview.kind == "preview"
        and (
            (
                # The article image can enter before either text field. It
                # cannot measure motion: the retained quote/video must do so.
                not old.media
                and preview.description is None
                and preview.description_visibility is None
                and preview.preview_text is None
                and preview.preview_text_visibility is None
                and _quoted_video_motion(a, b, shift)
                and preview.visibility.bounds[::2] == new.visibility.bounds[::2]
                and old.visibility.bounds[::2] == new.visibility.bounds[::2]
                and preview.visibility.bounds[1] - shift >= old.visibility.bounds[3]
            )
            or (
                preview.description_visibility is not None
                and preview.description_visibility.bounds[1] - shift
                >= old.visibility.bounds[3]
                and (not old.media or _preview_title_revealed(old, new, shift))
            )
            or (
                _preview_summary_revealed(old, new, shift)
                and _quoted_video_motion(a, b, shift)
            )
        )
    )


def _preview_title_revealed(old, new, shift):
    if len(old.media) != 1 or len(new.media) != 1:
        return False
    previous, current = old.media[0], new.media[0]
    return (
        previous.kind == current.kind == "preview"
        and previous.description is None
        and previous.preview_text is None
        and previous.source_label == current.source_label
        and previous.description_visibility is None
        and old.visibility.visible_bounds is not None
        and old.visibility.bounds[3] > old.visibility.visible_bounds[3]
        and (
            previous.visibility.visible_bounds is None
            or previous.visibility.bounds[3] > previous.visibility.visible_bounds[3]
        )
        and previous.visibility.bounds[::2] == current.visibility.bounds[::2]
        and current.visibility.bounds[1] - previous.visibility.bounds[1] == shift
        and bool(current.description)
        and current.description_visibility is not None
        and current.description_visibility.bounds[1] - shift
        >= previous.visibility.bounds[3]
    )


def _preview_body_scrolled_out(a, b, shift, after):
    if (
        not isinstance(b, PostFragment)
        or a.body is None
        or a.body_visibility is None
        or b.body is not None
        or b.body_visibility is not None
        or b.body_annotations
        or a.translation != b.translation
        or a.body_visibility.bounds[3] + shift > after.content_viewport[1]
        or (
            not isinstance(a, PostFragment)
            and a.header_visibility.bounds[3] + shift > after.content_viewport[1]
        )
    ):
        return False
    return _quoted_video_motion(a, b, shift)


def _preview_summary_revealed(old, new, shift):
    if len(old.media) != 1 or len(new.media) != 1:
        return False
    previous, current = old.media[0], new.media[0]
    old_title, new_title = (
        previous.description_visibility,
        current.description_visibility,
    )
    return (
        previous.kind == current.kind == "preview"
        and previous.description is not None
        and previous.description == current.description
        and previous.preview_text is None
        and previous.preview_text_visibility is None
        and bool(current.preview_text)
        and current.preview_text_visibility is not None
        and previous.source_label == current.source_label
        and old.labels == new.labels
        and old_title is not None
        and new_title is not None
        and old.visibility.visible_bounds is not None
        and old.visibility.bounds[3] > old.visibility.visible_bounds[3]
        and previous.visibility.bounds[::2] == current.visibility.bounds[::2]
        and current.visibility.bounds[1] - previous.visibility.bounds[1] == shift
        and old_title.bounds[::2] == new_title.bounds[::2]
        and new_title.bounds[1] - old_title.bounds[1] == shift
        and (
            new_title.bounds[3] - old_title.bounds[3] == shift
            or (
                old_title.clipped
                and old_title.bounds[3] == previous.visibility.bounds[3]
                and new_title.bounds[3] - shift >= old_title.bounds[3]
            )
        )
        and current.preview_text_visibility.bounds[1] - shift
        >= previous.visibility.bounds[3]
    )


def _quoted_video_motion(a, b, shift):
    if (
        a.quoted_post is None
        or b.quoted_post is None
        or a.quoted_post.labels != b.quoted_post.labels
        or len(a.media) != 1
        or len(b.media) != 1
    ):
        return False
    old, new = a.media[0], b.media[0]
    old_header, new_header = (
        a.quoted_post.header_visibility,
        b.quoted_post.header_visibility,
    )
    # The retained quote header measures motion independently of the video tail.
    return (
        old_header.unobscured
        and new_header.unobscured
        and old.kind == new.kind == "video"
        and old.description == new.description
        and (old.source_label, old.source_prefix)
        == (new.source_label, new.source_prefix)
        and old_header.bounds[::2] == new_header.bounds[::2]
        and all(
            abs(q - p - shift) <= 2
            for p, q in zip(old_header.bounds[1::2], new_header.bounds[1::2])
        )
        and old.visibility.bounds[::2] == new.visibility.bounds[::2]
        and abs(new.visibility.bounds[3] - old.visibility.bounds[3] - shift) <= 2
        and (
            abs(new.visibility.bounds[1] - old.visibility.bounds[1] - shift) <= 2
            or (new.visibility.bounds[1] == 0 and old.visibility.bounds[1] + shift <= 0)
        )
    )


def _inset_quote_consistent(a, b, after):
    """All matching paths must justify a bodyless video below the viewport edge."""
    if not (
        isinstance(b, PostFragment)
        and b.body is None
        and b.quoted_post is not None
        and b.media
        and b.media[0].visibility.bounds[1] >= after.content_viewport[1]
    ):
        return True
    if a.quoted_post is None:
        return False
    shift = (
        b.quoted_post.header_visibility.bounds[1]
        - a.quoted_post.header_visibility.bounds[1]
    )
    if shift > 0:
        return False
    if a.body is not None:
        return _preview_body_scrolled_out(a, b, shift, after)
    return (
        isinstance(a, PostFragment)
        and a.body_visibility is None
        and b.body_visibility is None
        and a.body_annotations == b.body_annotations
        and a.translation == b.translation
        and _quoted_video_motion(a, b, shift)
    )


def _bodyless_quote_preview_revealed(a, b, after):
    old, new = a.quoted_post, b.quoted_post
    if (
        not old
        or not new
        or old.body is not None
        or new.body is not None
        or old.author != new.author
        or old.translation != new.translation
        or a.translation != b.translation
        or _fragment_media_content(a.media) != _fragment_media_content(b.media)
        or old.header_visibility.bounds[::2] != new.header_visibility.bounds[::2]
    ):
        return False
    shift = new.header_visibility.bounds[1] - old.header_visibility.bounds[1]
    retained_body = (
        a.body is not None
        and _same_body(a, b)
        and a.body_visibility is not None
        and b.body_visibility is not None
        and a.body_visibility.bounds[::2] == b.body_visibility.bounds[::2]
    )
    if not retained_body and not _preview_body_scrolled_out(a, b, shift, after):
        return False
    if not isinstance(a, PostFragment):
        if isinstance(b, PostFragment):
            if not _header_loss_explained(a, b, shift, after):
                return False
        elif a.author != b.author:
            return False
    elif not isinstance(b, PostFragment):
        return False
    return shift < -2 and (
        _preview_title_revealed(old, new, shift)
        or (
            _preview_summary_revealed(old, new, shift)
            and _quoted_video_motion(a, b, shift)
        )
    )


def _link_preview_revealed(a, b):
    if (
        isinstance(a, PostFragment)
        or isinstance(b, PostFragment)
        or a.author != b.author
        or a.body is None
        or not _same_body(a, b)
        or a.translation != b.translation
        or a.media
        or len(b.media) != 1
        or a.quoted_post is not None
        or b.quoted_post is not None
        or a.visibility.visible_bounds is None
    ):
        return False
    preview = b.media[0]
    shift = b.body_visibility.bounds[1] - a.body_visibility.bounds[1]
    return (
        preview.kind == "link_preview"
        and preview.preview_text_visibility is not None
        and a.body_visibility.bounds[::2] == b.body_visibility.bounds[::2]
        and shift < -2
        and a.visibility.bounds[3] > a.visibility.visible_bounds[3]
        and preview.preview_text_visibility.bounds[1] - shift >= a.visibility.bounds[3]
    )


def _quote_below_video(a, b):
    if isinstance(a, PostFragment):
        return False
    if (
        a.quoted_post is not None
        or b.quoted_post is None
        or not a.observable
        or len(a.media) != 1
        or len(b.media) != 1
        or a.body_visibility is None
    ):
        return False
    old, new = a.media[0], b.media[0]
    old_rect, new_rect = old.visibility.bounds, new.visibility.bounds
    shift = new_rect[1] - old_rect[1]
    return (
        (isinstance(b, PostFragment) or a.author == b.author)
        and _same_body(a, b)
        and old.kind == new.kind == "video"
        and old.description == new.description
        and old.source_label == new.source_label
        and old.source_prefix == new.source_prefix
        and old_rect[::2] == new_rect[::2]
        and shift < -2
        and b.body_visibility is not None
        and b.body_visibility.bounds[3] - a.body_visibility.bounds[3] == shift
        and old.visibility.visible_bounds is not None
        and old_rect[3] > old.visibility.visible_bounds[3]
        and new_rect[3] - shift >= old_rect[3]
        and b.quoted_post.visibility.bounds[1] >= new_rect[3]
        and a.visibility.visible_bounds is not None
        and b.quoted_post.visibility.bounds[1] - shift >= a.visibility.visible_bounds[3]
    )


def _quoted_body_lost(a, b, after):
    if (
        not isinstance(b, PostFragment)
        or b.body is not None
        or a.quoted_post is None
        or b.quoted_post is None
    ):
        return False
    old_anchor = a.quoted_post.body_visibility or a.quoted_post.header_visibility
    new_anchor = b.quoted_post.body_visibility or b.quoted_post.header_visibility
    shift = new_anchor.bounds[1] - old_anchor.bounds[1]
    return (
        _quote_content(a.quoted_post) == _quote_content(b.quoted_post)
        and shift < -2
        and (
            a.body_visibility is None
            or a.body_visibility.bounds[3] + shift <= after.content_viewport[1]
        )
        and (
            [(m.kind, m.description) for m in a.media]
            == [(m.kind, m.description) for m in b.media]
            or (
                not b.media
                and all(
                    m.visibility.bounds[3] + shift <= after.content_viewport[1]
                    for m in a.media
                )
            )
        )
    )


def _advertising_continuity(a, b, shift, before, after):
    """Disclosures constrain movement established by existing content anchors."""
    old, new = a.advertising_visibility, b.advertising_visibility
    if a.advertising == b.advertising:
        if old is None or new is None:
            return old is None and new is None
        return old.bounds[::2] == new.bounds[::2] and all(
            abs(y - x - shift) <= 2 for x, y in zip(old.bounds[1::2], new.bounds[1::2])
        )
    if shift >= -2:
        return False
    if a.advertising == "unknown" and b.advertising == "paid_partnership":
        return (
            old is None
            and new is not None
            and not a.actions
            and a.visibility.bounds[3] >= before.content_viewport[3]
            and new.bounds[1] - shift >= a.visibility.bounds[3]
        )
    if a.advertising == "paid_partnership" and b.advertising == "unknown":
        return (
            old is not None
            and new is None
            and old.bounds[3] + shift <= after.content_viewport[1]
        )
    return False


def _note_content(note):
    return (note.title, note.body, note.translation) if note else None


def _footer_media_lost(media, actions, shift, viewport):
    view = media.visibility
    if view.bounds[3] + shift <= viewport[1]:
        return True
    if media.kind != "video" or view.visible_bounds is None or not actions:
        return False
    rows = [a.visibility.bounds for a in actions]
    top = rows[0][1]
    cover = (rows[0][0], top, rows[-1][2], min(r[3] for r in rows))
    padding = (view.bounds[0], top, view.bounds[2], view.bounds[3])
    return (
        view.visible_bounds[::2] == view.bounds[::2]
        and view.visible_bounds[3] == top
        and top + shift <= viewport[1]
        and all(r[1] == top for r in rows)
        and all(left[2] == right[0] for left, right in pairwise(rows))
        and _intersection(padding, cover) == padding
    )


def _footer_match(a, b, after):
    if (
        not isinstance(b, PostFragment)
        or b.body is not None
        or b.media
        or b.quoted_post
        or b.community_note
        or b.preview_texts
        or tuple(t.label for t in a.actions) != ACTION_LABELS
        or tuple(t.label for t in b.actions) != ACTION_LABELS
        or [(t.count, t.selected) for t in a.actions]
        != [(t.count, t.selected) for t in b.actions]
    ):
        return False
    shift = b.actions[0].visibility.bounds[3] - a.actions[0].visibility.bounds[3]
    return (
        shift <= 0
        and (
            a.body_visibility is None
            or a.body_visibility.bounds[3] + shift <= after.content_viewport[1]
        )
        and all(
            _footer_media_lost(m, a.actions, shift, after.content_viewport)
            for m in a.media
        )
        and all(
            t.visibility.bounds[3] + shift <= after.content_viewport[1]
            for t in getattr(a, "preview_texts", ())
        )
        and (
            getattr(a, "quoted_body", None) is None
            or a.quoted_body.visibility.bounds[3] + shift <= after.content_viewport[1]
        )
        and (
            a.quoted_post is None
            or a.quoted_post.visibility.bounds[3] + shift <= after.content_viewport[1]
        )
        and (
            a.community_note is None
            or a.community_note.visibility.bounds[3] + shift
            <= after.content_viewport[1]
        )
        and all(
            x.visibility.bounds[::2] == y.visibility.bounds[::2]
            and all(
                abs(v - u - shift) <= 2
                for u, v in zip(
                    x.visibility.bounds[1:2]
                    if x.label == "Share"
                    else x.visibility.bounds[1::2],
                    y.visibility.bounds[1:2]
                    if y.label == "Share"
                    else y.visibility.bounds[1::2],
                )
            )
            for x, y in zip(a.actions, b.actions)
        )
    )


def _preview_spans(post):
    if getattr(post, "preview_texts", ()):
        return post.preview_texts
    quote = post.quoted_post
    source = (
        quote
        if quote is not None
        else post
        if getattr(post, "quoted_body", None) is not None
        else None
    )
    if source is None or len(source.media) != 1:
        return ()
    media = source.media[0]
    if media.kind != "preview":
        return ()
    return tuple(
        TextSpan(text, view)
        for text, view in (
            (media.description, media.description_visibility),
            (media.preview_text, media.preview_text_visibility),
        )
        if text is not None and view is not None
    )


def _preview_tail_match(a, b, before, after):
    current = getattr(b, "preview_texts", ())
    previous = _preview_spans(a)
    if (
        not current
        or len(previous) < len(current)
        or b.body is not None
        or b.media
        or b.quoted_post
        or b.community_note
    ):
        return False
    if [p.text for p in previous[-len(current) :]] != [p.text for p in current]:
        return False
    pairs = _anchor_pairs(a, b, before, after)
    shifts = [y - x for x, y in pairs]
    if (
        len({x for x, y in pairs}) < 2
        or not shifts
        or max(shifts) > 0
        or max(shifts) - min(shifts) > 2
    ):
        return False
    shift = max(shifts)
    lost = [p.visibility for p in previous[: -len(current)]]
    if getattr(a, "quoted_body", None) is not None:
        lost.append(a.quoted_body.visibility)
    else:
        lost.extend(m.visibility for m in a.media)
    if a.body_visibility is not None:
        lost.append(a.body_visibility)
    if a.quoted_post is not None:
        lost.append(a.quoted_post.header_visibility)
        if a.quoted_post.body_visibility is not None:
            lost.append(a.quoted_post.body_visibility)
    if not isinstance(a, PostFragment):
        lost.append(a.header_visibility)
    return (
        all(v.bounds[3] + shift <= after.content_viewport[1] for v in lost)
        and all(
            x.visibility.bounds[::2] == y.visibility.bounds[::2]
            for x, y in zip(previous[-len(current) :], current)
        )
        and tuple(t.label for t in a.actions)
        == tuple(t.label for t in b.actions)
        == ACTION_LABELS
        and all(
            x.visibility.bounds[::2] == y.visibility.bounds[::2]
            and abs(y.visibility.bounds[1] - x.visibility.bounds[1] - shift) <= 2
            for x, y in zip(a.actions, b.actions)
        )
    )


def _note_continuity(a, b, shift, before, after):
    old, new = a.community_note, b.community_note
    if old is None and new is None:
        return True
    if old is None:
        return (
            shift < -2
            and not a.actions
            and a.visibility.bounds[3] >= before.content_viewport[3]
            and new.visibility.bounds[1] - shift >= a.visibility.bounds[3]
        )
    if new is None:
        return (
            shift < -2 and old.visibility.bounds[3] + shift <= after.content_viewport[1]
        )
    if _note_content(old) != _note_content(new):
        return False
    for name in ("visibility", "header_visibility", "body_visibility"):
        x, y = getattr(old, name).bounds, getattr(new, name).bounds
        if x[::2] != y[::2]:
            return False
        if shift == 0:
            if x != y:
                return False
            continue
        for index, boundary in ((1, 1), (3, 3)):
            old_visible = (
                before.content_viewport[1] < x[index] < before.content_viewport[3]
            )
            new_visible = (
                after.content_viewport[1] < y[index] < after.content_viewport[3]
            )
            if old_visible and new_visible and abs(y[index] - x[index] - shift) > 2:
                return False
            if (
                old_visible
                and not new_visible
                and index == 1
                and x[index] + shift > after.content_viewport[boundary]
            ):
                return False
            if (
                new_visible
                and not old_visible
                and index == 3
                and y[index] - shift < before.content_viewport[boundary]
            ):
                return False
    return True


def _nested_quote_continuity(a, b, shift, before, after):
    old = a.quoted_post.nested_quote if a.quoted_post is not None else None
    new = b.quoted_post.nested_quote if b.quoted_post is not None else None
    if old is None and new is None:
        return True
    if old is None:
        return (
            a.quoted_post is not None
            and shift < -2
            and not a.actions
            and a.quoted_post.visibility.bounds[3] >= before.content_viewport[3]
            and new.visibility.bounds[1] - shift >= a.quoted_post.visibility.bounds[3]
        )
    if new is None:
        return (
            shift < -2 and old.visibility.bounds[3] + shift <= after.content_viewport[1]
        )
    if _quote_content(old) != _quote_content(new) or old.labels != new.labels:
        return False
    for name in ("visibility", "header_visibility", "body_visibility"):
        x, y = getattr(old, name), getattr(new, name)
        if x is None or y is None:
            if x != y:
                return False
            continue
        if x.bounds[::2] != y.bounds[::2]:
            return False
        for u, v in zip(x.bounds[1::2], y.bounds[1::2]):
            if (
                abs(v - u - shift) > 2
                and not (v == 0 and u + shift <= 0)
                and not (
                    u >= before.content_viewport[3] and v >= after.content_viewport[3]
                )
            ):
                return False
    return True


def _quote_footer_continuity(a, b, shift, before, after):
    old = (
        a.quoted_post.footer_annotations
        if a.quoted_post
        else getattr(a, "quoted_footer_annotations", ())
    )
    new = (
        b.quoted_post.footer_annotations
        if b.quoted_post
        else getattr(b, "quoted_footer_annotations", ())
    )
    if old and new:
        return len(old) == len(new) and all(
            x.text == y.text
            and x.visibility.bounds[::2] == y.visibility.bounds[::2]
            and all(
                abs(v - u - shift) <= 2
                for u, v in zip(x.visibility.bounds[1::2], y.visibility.bounds[1::2])
            )
            for x, y in zip(old, new)
        )
    if not old and not new:
        return True
    if shift >= -2:
        return False
    if new:
        quote = a.quoted_post
        return (
            quote is not None
            and not a.actions
            and quote.visibility.bounds[3] >= before.content_viewport[3]
            and len(new) == 1
            and new[0].text == "Paid partnership"
            and new[0].visibility.bounds[1] - shift >= quote.visibility.bounds[3]
        )
    return all(v.visibility.bounds[3] + shift <= after.content_viewport[1] for v in old)


def _metadata_continuity(a, b, shift, before, after):
    return (
        _advertising_continuity(a, b, shift, before, after)
        and _note_continuity(a, b, shift, before, after)
        and _nested_quote_continuity(a, b, shift, before, after)
        and _quote_footer_continuity(a, b, shift, before, after)
    )


def _alignment(before, after, *, scrolling=False):
    """Align overlapping ordered occurrences; repeated keys must be unambiguous."""
    old, new = (*before.fragments, *before.posts), (*after.fragments, *after.posts)
    if not old or not new:
        raise XError("Lost X post continuity: no overlapping candidates.")

    def matches(a, b):
        return _inset_quote_consistent(a, b, after) and (
            _same_content(a, b)
            or _tail_match(a, b, before, after, allow_hidden_source=scrolling)
            or _quoted_body_lost(a, b, after)
            or _footer_match(a, b, after)
            or _preview_tail_match(a, b, before, after)
            or _quoted_tail_match(a, b, before, after)
        )

    def compatible(a, b):
        return _inset_quote_consistent(a, b, after) and (
            matches(a, b)
            or _quote_media_revealed(a, b)
            or _quote_preview_revealed(a, b, after)
            or _bodyless_quote_preview_revealed(a, b, after)
            or _quote_below_video(a, b)
            or _revealed_content(a, b)
            or _link_preview_revealed(a, b)
            or _quote_header_completed(a, b, before, after)
        )

    def shifts_for(a, b):
        return [y - x for x, y in _anchor_pairs(a, b, before, after) if x > 0 and y > 0]

    def matches_movement(a, b, shifts):
        if not compatible(a, b) or not (candidate_shifts := shifts_for(a, b)):
            return False
        combined = shifts + candidate_shifts
        return max(combined) - min(combined) <= 2 and _metadata_continuity(
            a, b, max(combined), before, after
        )

    if not scrolling:
        if len(old) == len(new) and all(
            type(a) is type(b)
            and matches(a, b)
            and _metadata_continuity(a, b, 0, before, after)
            and all(x == y for x, y in _anchor_pairs(a, b, before, after))
            for a, b in zip(old, new)
        ):
            return 0, False
        raise XError("X posts changed outside adapter scrolling; restart verification.")
    alignments = []
    for offset in range(-len(new) + 1, len(old)):
        pairs = [
            (old[j + offset], b)
            for j, b in enumerate(new)
            if 0 <= j + offset < len(old)
        ]
        # Content entering XML needs an anchor that predates the reveal.
        anchored = any(
            _same_content(a, b)
            or _quote_media_revealed(a, b)
            or _quote_preview_revealed(a, b, after)
            or _bodyless_quote_preview_revealed(a, b, after)
            or _quote_below_video(a, b)
            or _quoted_body_lost(a, b, after)
            or _tail_match(a, b, before, after, require_overlap=True)
            or _preview_tail_match(a, b, before, after)
            or _quoted_tail_match(a, b, before, after)
            or _quote_header_completed(a, b, before, after)
            for a, b in pairs
        )
        if not (
            anchored or any(_media_revelation_anchored(a, b) for a, b in pairs)
        ) or not all(compatible(a, b) for a, b in pairs):
            continue
        # Android can clamp offscreen anchors to zero; use the remaining anchors
        # only when they agree on the direction and amount of movement.
        shifts = [shift for a, b in pairs for shift in shifts_for(a, b)]
        if not shifts or max(shifts) > 0 or max(shifts) - min(shifts) > 2:
            continue
        if not all(
            _metadata_continuity(a, b, max(shifts), before, after) for a, b in pairs
        ):
            continue
        # A revealed neighbor cannot bypass a preceding post that became unreadable.
        if not anchored and any(
            post.visibility.bounds[3] + max(shifts) > after.content_viewport[1]
            for post in old[: max(offset, 0)]
        ):
            continue

        if any(
            (isinstance(a, PostFragment) or isinstance(b, PostFragment))
            and (
                sum(matches_movement(p, b, shifts) for p in old) != 1
                or sum(matches_movement(a, p, shifts) for p in new) != 1
            )
            for a, b in pairs
        ):
            continue
        moved = min(shifts) < -2
        if not moved and (
            offset != 0
            or len(old) != len(new)
            or len(before.fragments) != len(after.fragments)
        ):
            continue
        alignments.append(
            (offset + len(after.fragments) - len(before.fragments), moved)
        )
    if len(alignments) != 1:
        raise XError(
            "Cannot uniquely verify X advancement from ordered posts and movement."
        )
    return alignments[0]


def _text_continuation(before, after, *, entering=False):
    """Match a pending text passage without treating clipped bounds as movement."""
    if (
        not before.collapsed
        or not after.collapsed
        or before.content_viewport != after.content_viewport
        or after.rejected_posts
        or len(after.fragments) != 1
    ):
        raise XError("Lost pending X text continuity.")
    fragment = after.fragments[0]
    old = (*before.fragments, *before.posts)
    new = (*after.fragments, *after.posts)
    matches = [i for i, p in enumerate(old) if _same_body(p, fragment)]
    if (
        fragment.body is None
        or len(matches) != 1
        or sum(_same_body(p, fragment) for p in new) != 1
    ):
        raise XError("Cannot uniquely match pending X text.")
    index = matches[0]
    source = old[index]
    a, b = source.body_visibility, fragment.body_visibility
    if entering and (
        a is None
        or b is None
        or a.bounds[3] < before.content_viewport[3]
        or b.bounds[3] < after.content_viewport[3]
        or source.media
        or fragment.media
        or source.quoted_post
        or fragment.quoted_post
    ):
        raise XError("X text has no clipped passage to verify.")
    if (
        a is None
        or b is None
        or not a.accessible
        or not b.accessible
        or a.bounds[::2] != b.bounds[::2]
        or b.bounds[1] > after.content_viewport[1]
        or not (
            _same_content(source, fragment)
            or (
                not source.media
                and source.quoted_post is None
                and a.bounds[3] >= before.content_viewport[3]
                and all(m.visibility.bounds[1] >= b.bounds[3] for m in fragment.media)
                and (
                    fragment.quoted_post is None
                    or fragment.quoted_post.visibility.bounds[1] >= b.bounds[3]
                )
            )
        )
        or any(
            p.visibility.bounds[1] < fragment.visibility.bounds[3] for p in after.posts
        )
        or (a.bounds[3] < before.content_viewport[3] and b.bounds[3] > a.bounds[3])
    ):
        raise XError("Pending X text changed or moved inconsistently.")
    return index + len(after.fragments) - len(before.fragments)


def _text_edge_visible(screen):
    if len(screen.fragments) != 1:
        return False
    body = screen.fragments[0].body_visibility
    return (
        body is not None
        and screen.content_viewport[1] < body.bounds[3] < screen.content_viewport[3]
    )


class X:
    name = "x"

    def __init__(self, phone: Phone):
        self.phone = phone
        self.verified_account = None
        self.timeline = None
        self._expected = None
        self._screen = None
        self._index = None

    def _invalidate(self):
        self.verified_account = None
        self._screen = None
        self._index = None

    @contextmanager
    def _operation(self):
        try:
            yield
        except BaseException:
            self._invalidate()
            raise

    def _snapshot(self):
        if self.phone.read("app").get("package") != PACKAGE:
            return Screen("unsupported", reason="X is not the foreground app.")
        size = self.phone.read("size")
        result = read_screen(self.phone.read("hierarchy"), size)
        if self.phone.read("app").get("package") != PACKAGE:
            return Screen(
                "unsupported", reason="Foreground app changed while reading X."
            )
        return result

    def _wait_for(self, predicate, description):
        for attempt in range(READ_ATTEMPTS):
            screen = self._snapshot()
            if screen.kind == "drawer":
                self._verify_account(screen)
            if predicate(screen):
                return screen
            if attempt < READ_ATTEMPTS - 1:
                self.phone.wait(0.3, purpose="readiness")
        raise XError(f"Cannot verify {description}: {screen.reason or screen.kind}.")

    def _tap(self, screen, label):
        targets = [target for target in screen.controls if target.label == label]
        if len(targets) != 1 or targets[0].visibility.visible_bounds is None:
            raise XError(f"Cannot locate one visible X {label} control.")
        target = targets[0].visibility
        self.phone.tap(target.visible_bounds, exclude=target.overlaps).require()

    def _verify_account(self, screen):
        handle = screen.active_account
        if (
            screen.kind != "drawer"
            or handle is None
            or handle.lower() != self._expected
        ):
            raise XError("The active X handle does not match the configured account.")
        return handle

    def _reach_home(self, screen):
        for attempt in range(RESTORE_ATTEMPTS + 1):
            if screen.kind == "home" and any(
                target.label == "Show navigation drawer"
                and target.visibility.unobscured
                for target in screen.controls
            ):
                return screen
            if attempt == RESTORE_ATTEMPTS:
                break
            if screen.kind == "home":
                self._gesture(screen, "down")
                screen = self._wait_for(lambda s: s.kind == "home", "Home expansion")
            elif screen.kind == "drawer":
                self._verify_account(screen)
                self._tap(screen, "Close navigation menu")
                screen = self._wait_for(
                    lambda s: s.kind not in {"drawer", "unsupported"},
                    "drawer dismissal",
                )
            elif screen.kind == "post_options":
                self._tap(screen, "Close sheet")
                screen = self._wait_for(
                    lambda s: s.kind not in {"post_options", "unsupported"},
                    "post-options dismissal",
                )
            elif screen.kind in {"profile", "detail", "explore", "search_results"}:
                self._tap(screen, "Home")
                screen = self._wait_for(lambda s: s.kind == "home", "Home navigation")
            elif screen.kind == "search_input":
                self.phone.command("back").require()
                self.phone.wait(0.3, purpose="readiness")
                screen = self._snapshot()
            else:
                raise XError(
                    f"Cannot recover an unrecognized X screen: {screen.reason}."
                )
        raise XError("Cannot reach X Home within the navigation limit.")

    def start(self, username, timeline="for_you"):
        """Launch, verify the exact drawer account, and select a Home timeline."""
        with self._operation():
            self._invalidate()
            handle = "@" + username.removeprefix("@")
            if not HANDLE.fullmatch(handle) or timeline not in TIMELINES:
                raise ValueError(
                    "A valid X handle and for_you/following timeline are required."
                )
            self._expected, self.timeline = handle.lower(), timeline
            self.phone.command("launch", PACKAGE).require()
            screen = self._wait_for(lambda s: s.kind != "unsupported", "X launch")
            screen = self._reach_home(screen)
            self._tap(screen, "Show navigation drawer")
            drawer = self._wait_for(lambda s: s.kind == "drawer", "X account drawer")
            account = self._verify_account(drawer)
            self._tap(drawer, "Close navigation menu")
            screen = self._wait_for(lambda s: s.kind == "home", "return to X Home")
            screen = self._reach_home(screen)
            if screen.tab != TIMELINES[timeline]:
                self._tap(screen, TIMELINES[timeline])
            screen = self._wait_for(self._on_timeline, "selected X timeline")
            self.verified_account = account
            return self._first_post(screen)

    def _on_timeline(self, screen):
        return screen.kind == "home" and screen.tab == TIMELINES[self.timeline]

    def _require_started(self):
        if self.verified_account is None or self._screen is None:
            raise XError("Start X and verify its account before browsing.")

    def _check_timeline(self, screen, before=None, *, scrolling=False):
        if (
            before is not None
            and before.collapsed != screen.collapsed
            and not scrolling
        ):
            raise XError("X Home controls changed outside adapter scrolling.")
        if screen.kind == "home" and screen.collapsed and before is not None:
            if (
                self.verified_account is None
                or not (self._on_timeline(before) or before.collapsed)
                or (screen.tab is not None and screen.tab != TIMELINES[self.timeline])
            ):
                raise XError("Collapsed X Home has no verified timeline continuity.")
            return
        if not self._on_timeline(screen):
            raise XError(
                f"X left the verified timeline: {screen.reason or screen.kind}."
            )

    def _timeline_snapshot(self, before=None, *, scrolling=False):
        screen = self._snapshot()
        self._check_timeline(screen, before, scrolling=scrolling)
        if screen.collapsed and before is not None:
            _, moved = _alignment(before, screen, scrolling=scrolling)
            if not before.collapsed and not moved:
                raise XError("Cannot verify movement into collapsed X Home.")
        return screen

    def _advance_snapshot(self, before, pending):
        for attempt in range(ADVANCE_READ_ATTEMPTS):
            screen = self._snapshot()
            if screen.waiting_for != "home_composer":
                result = self._advance_alignment(before, screen, pending)
                if result[2] is not False or attempt == ADVANCE_READ_ATTEMPTS - 1:
                    return result
            elif attempt == ADVANCE_READ_ATTEMPTS - 1:
                self._check_timeline(screen, before, scrolling=True)
            self.phone.wait(0.3, purpose="readiness")

    def _advance_alignment(self, before, screen, pending):
        self._check_timeline(screen, before, scrolling=True)
        if pending:
            offset = _text_continuation(before, screen)
            if not (_text_edge_visible(before) and _text_edge_visible(screen)):
                return screen, offset, None
            # A returned lower edge needs a second snapshot with matching
            # movement of the surrounding posts before advancement can resume.
            aligned, moved = _alignment(before, screen, scrolling=True)
            if aligned != offset:
                raise XError("Pending X text lost its ordered position.")
            return screen, offset, True if moved else None
        try:
            offset, moved = _alignment(before, screen, scrolling=True)
        except XError as error:
            try:
                offset = _text_continuation(before, screen, entering=True)
            except XError:
                raise error from None
            return screen, offset, None
        if screen.collapsed and not before.collapsed and not moved:
            raise XError("Cannot verify movement into collapsed X Home.")
        return screen, offset, moved

    def _select(self, screen, index):
        self._screen, self._index = screen, index
        return screen.posts[index] if index is not None else None

    def _gesture(self, screen, direction):
        region, distance, exclusions = scroll_region(screen)
        if direction == "down":
            distance = min(
                distance,
                (screen.content_viewport[3] - screen.content_viewport[1]) * 0.1,
            )
        if direction == "up" and (anchors := (*screen.fragments, *screen.posts)):
            # Retain a text anchor or an unclipped video tail with action edges.
            edges = [p.body_visibility.bounds[3] for p in anchors if p.body_visibility]
            edges.extend(
                p.header_visibility.bounds[3]
                for p in screen.posts
                if p.body_visibility is None
            )
            edges.extend(
                (
                    p.quoted_post.body_visibility or p.quoted_post.header_visibility
                ).bounds[3]
                for p in anchors
                if p.quoted_post
            )
            edges.extend(
                p.media[0].visibility.bounds[3]
                # A short video must overlap its prior position after the
                # gesture. Empty space above it is not a retained anchor.
                - max(0, p.media[0].visibility.bounds[1] - screen.content_viewport[1])
                for p in anchors
                if _tail_anchors_available(p, screen.content_viewport)
            )
            edges.extend(
                p.community_note.body_visibility.bounds[3]
                for p in anchors
                if p.community_note is not None
            )
            edges.extend(
                t.visibility.bounds[3] for p in anchors for t in _preview_spans(p)
            )
            remaining = max(edges, default=0) - screen.content_viewport[1]
            if remaining <= 1:
                raise XError("No remaining X content anchor for verified scrolling.")
            distance = min(distance, remaining * 0.75)
        self.phone.gesture(
            "scroll", direction, region, distance=distance, exclude=exclusions
        ).require()
        self.phone.wait(0.3, purpose="readiness")

    def _scroll(self, screen):
        self._gesture(screen, "up")
        return self._timeline_snapshot(screen, scrolling=True)

    def _frame(self, screen, verified):
        self._gesture(screen, "up")
        after = self._snapshot()
        if after.kind == "home" and after.collapsed:
            if verified:
                try:
                    _, moved = _alignment(screen, after, scrolling=True)
                except XError:
                    pass
                else:
                    if screen.collapsed or moved:
                        return after, True
            return after, False
        if not self._on_timeline(after):
            raise XError("Cannot verify the X timeline after initial framing.")
        return after, True

    def _reveal_timeline(self, screen):
        for attempt in range(RESTORE_ATTEMPTS + 1):
            if self._on_timeline(screen):
                return screen
            if screen.kind != "home" or not screen.collapsed:
                raise XError("Cannot verify the X timeline after initial framing.")
            if attempt == RESTORE_ATTEMPTS:
                break
            self._gesture(screen, "down")
            screen = self._snapshot()
        raise XError("Cannot reveal the X timeline after initial framing.")

    def _first_post(self, screen):
        verified = self._on_timeline(screen)
        for attempt in range(SCROLL_ATTEMPTS + 1):
            if not verified and screen.observable_posts:
                # Rejected content cannot prove timeline continuity. Keep moving
                # forward until a candidate appears, then reveal only the tabs.
                screen = self._reveal_timeline(screen)
                verified = True
            if screen.empty:
                return self._select(screen, None)
            for index, post in enumerate(screen.posts):
                if post.observable:
                    return self._select(screen, index)
            if attempt < SCROLL_ATTEMPTS:
                if not screen.scroll_areas:
                    screen = self._wait_for(
                        lambda s: self._on_timeline(s) and bool(s.posts or s.empty),
                        "X timeline content",
                    )
                    verified = True
                else:
                    screen, verified = self._frame(screen, verified)
        raise XError("No observable X post within the framing limit.")

    def observe(self):
        """Refresh the selected occurrence without silently selecting a new post."""
        with self._operation():
            self._require_started()
            screen = self._snapshot()
            self._check_timeline(screen, self._screen)
            if self._screen.empty and screen.empty:
                return self._select(screen, None)
            self._refresh_alignment(screen)
            if self._index is None or not screen.posts[self._index].observable:
                raise XError("The selected X post is no longer observable.")
            return self._select(screen, self._index)

    def _refresh_alignment(self, screen):
        try:
            _alignment(self._screen, screen)
            return
        except XError:
            if self._index is None:
                raise
        selected = self._screen.posts[self._index]
        rejected = {
            item.bounds
            for item in self._screen.rejected_posts
            if item.bounds and item.bounds[1] >= selected.visibility.bounds[3]
        }
        revealed = [
            post
            for index, post in enumerate(screen.posts)
            if index > self._index and post.visibility.bounds in rejected
        ]
        if not revealed or len({p.visibility.bounds for p in revealed}) != len(
            revealed
        ):
            raise XError(
                "X posts changed outside adapter scrolling; restart verification."
            )
        # Only parsing availability may change inside an already known later
        # container. The selected index and all prior anchors must stay fixed.
        stable = replace(
            screen, posts=tuple(p for p in screen.posts if p not in revealed)
        )
        _alignment(self._screen, stable)

    def advance(self):
        """Select the next visible occurrence, scrolling with bounded verification."""
        with self._operation():
            self.observe()
            if self._screen.empty:
                return None
            screen, index = self._screen, self._index
            pending = False
            for attempt in range(ADVANCE_SCROLL_ATTEMPTS + 1):
                for next_index, post in enumerate(screen.posts):
                    if not pending and next_index > index and post.observable:
                        return self._select(screen, next_index)
                if attempt == ADVANCE_SCROLL_ATTEMPTS:
                    break
                self._gesture(screen, "up")
                after, offset, moved = self._advance_snapshot(screen, pending)
                pending = moved is None
                index -= offset
                screen = after
            raise XError("Cannot verify a next X post within the scrolling limit.")

    def recover(self):
        """Reverify startup after context loss; this establishes a new position."""
        if self._expected is None or self.timeline is None:
            raise XError("No previous X account and timeline to recover.")
        return self.start(self._expected, self.timeline)
