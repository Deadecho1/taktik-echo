"""Account-verified X timeline browsing through a session-owned Phone.

This browsing seam returns parsed Posts for the persona adapter.
The caller owns device reservations, locks, the deadline, and Phone.close().
"""

from contextlib import contextmanager
from dataclasses import replace

from taktik.core.shared.phone_interaction import InteractionError, Phone
from taktik.core.social_media.x.ui.screen import (
    ACTION_LABELS,
    HANDLE,
    PACKAGE,
    PostFragment,
    Screen,
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
        and post.media[0].kind == "video"
        and tuple(t.label for t in post.actions) == ACTION_LABELS
        and viewport[1] < post.media[0].visibility.bounds[3] < viewport[3]
        and all(
            viewport[1] < t.visibility.bounds[1] < viewport[3] for t in post.actions
        )
    )


def _tail_match(
    a, b, before, after, *, require_overlap=False, allow_hidden_source=False
):
    if not isinstance(b, PostFragment) or b.body is not None:
        return False
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
        and new_rect[1] < after.content_viewport[1]
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
            (not a.media and bool(b.media) and b.quoted_post is None)
            or (same_media and b.quoted_post is not None)
        )
    )


def _image_revelation_anchored(a, b):
    if (
        isinstance(a, PostFragment)
        or isinstance(b, PostFragment)
        or a.author != b.author
        or a.body is None
        or not _same_body(a, b)
        or a.translation != b.translation
        or a.quoted_post is not None
        or b.quoted_post is not None
        or a.media
        or a.actions
        or not b.media
        or any(m.kind != "image" for m in b.media)
        or a.body_visibility is None
        or b.body_visibility is None
        or not a.body_visibility.clipped
        or not b.body_visibility.unobscured
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
    )


def _quote_preview_revealed(a, b, after):
    if (
        isinstance(a, PostFragment)
        or not isinstance(b, PostFragment)
        or not a.observable
        or a.body is None
        or not _same_body(a, b)
        or a.body_visibility is None
        or b.body_visibility is None
        or a.body_visibility.bounds[::2] != b.body_visibility.bounds[::2]
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
    return (
        old.author == new.author
        and old.body == new.body
        and old.translation == new.translation
        and old.body_visibility.bounds[::2] == new.body_visibility.bounds[::2]
        and old.header_visibility.bounds[::2] == new.header_visibility.bounds[::2]
        and shift < -2
        and a.header_visibility.bounds[3] + shift <= after.content_viewport[1]
        and old.visibility.visible_bounds is not None
        and old.visibility.bounds[3] > old.visibility.visible_bounds[3]
        and preview.kind == "preview"
        and preview.description_visibility is not None
        and preview.description_visibility.bounds[1] - shift >= old.visibility.bounds[3]
        and (not old.media or _preview_title_revealed(old, new, shift))
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


def _bodyless_quote_preview_revealed(a, b, after):
    old, new = a.quoted_post, b.quoted_post
    if (
        not old
        or not new
        or old.body is not None
        or new.body is not None
        or old.author != new.author
        or old.translation != new.translation
        or a.body is None
        or not _same_body(a, b)
        or a.body_visibility is None
        or b.body_visibility is None
        or a.body_visibility.bounds[::2] != b.body_visibility.bounds[::2]
        or a.translation != b.translation
        or _fragment_media_content(a.media) != _fragment_media_content(b.media)
        or old.header_visibility.bounds[::2] != new.header_visibility.bounds[::2]
    ):
        return False
    shift = new.header_visibility.bounds[1] - old.header_visibility.bounds[1]
    if not isinstance(a, PostFragment):
        if isinstance(b, PostFragment):
            if a.header_visibility.bounds[3] + shift > after.content_viewport[1]:
                return False
        elif a.author != b.author:
            return False
    elif not isinstance(b, PostFragment):
        return False
    return shift < -2 and _preview_title_revealed(old, new, shift)


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


def _alignment(before, after, *, scrolling=False):
    """Align overlapping ordered occurrences; repeated keys must be unambiguous."""
    old, new = (*before.fragments, *before.posts), (*after.fragments, *after.posts)
    if not old or not new:
        raise XError("Lost X post continuity: no overlapping candidates.")

    def matches(a, b):
        return (
            _same_content(a, b)
            or _tail_match(a, b, before, after, allow_hidden_source=scrolling)
            or _quoted_body_lost(a, b, after)
        )

    def compatible(a, b):
        return (
            matches(a, b)
            or _quote_media_revealed(a, b)
            or _quote_preview_revealed(a, b, after)
            or _bodyless_quote_preview_revealed(a, b, after)
            or _quote_below_video(a, b)
            or _revealed_content(a, b)
            or _link_preview_revealed(a, b)
        )

    def shifts_for(a, b):
        return [y - x for x, y in _anchor_pairs(a, b, before, after) if x > 0 and y > 0]

    def matches_movement(a, b, shifts):
        if not compatible(a, b) or not (candidate_shifts := shifts_for(a, b)):
            return False
        combined = shifts + candidate_shifts
        return max(combined) - min(combined) <= 2

    if not scrolling:
        if len(old) == len(new) and all(
            type(a) is type(b)
            and matches(a, b)
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
            for a, b in pairs
        )
        if not (
            anchored or any(_image_revelation_anchored(a, b) for a, b in pairs)
        ) or not all(compatible(a, b) for a, b in pairs):
            continue
        # Android can clamp offscreen anchors to zero; use the remaining anchors
        # only when they agree on the direction and amount of movement.
        shifts = [shift for a, b in pairs for shift in shifts_for(a, b)]
        if not shifts or max(shifts) > 0 or max(shifts) - min(shifts) > 2:
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
                for p in anchors
                if _tail_anchors_available(p, screen.content_viewport)
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
