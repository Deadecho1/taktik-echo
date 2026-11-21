"""Main-post attribution on the native screen-reader detail layout."""

import hashlib
import json
from dataclasses import replace

from lxml import etree

from .screen import (
    ACTION_ALIASES,
    ACTION_LABELS,
    HANDLE,
    PACKAGE,
    VERIFICATION_LABELS,
    Post,
    Visibility,
    _actions,
    _body_annotations,
    _body_complete,
    _clickable,
    _intersect,
    _media,
    _one,
    _plain_annotation,
    _quote_bundle,
    _rect,
    _Unsupported,
    _visibility,
)


def combine_hierarchies(ordinary, native):
    """Keep ordinary reply nodes when both reads show the same thread position.

    Screen-reader mode expands the main post but groups replies into summaries.
    The timestamp and thread controls must agree before joining those layouts.
    """
    roots = [
        etree.fromstring(xml.encode(), parser=etree.XMLParser(resolve_entities=False))
        for xml in (ordinary, native)
    ]
    scopes = [root.xpath('.//*[@resource-id="PostDetail"]') for root in roots]
    if any(len(scope) != 1 for scope in scopes):
        raise _Unsupported("No unique detail context across native reads.")
    if roots[1].get("taktik-reader") == "screen-reader":
        roots[0].set("taktik-reader", "screen-reader")
    has_main_header = roots[1].xpath(
        './/*[@resource-id="PostDetail"]/node[@scrollable="true"]/node/node[@resource-id="timeline_post_avatar"]'
    )
    fallback = (
        etree.tostring(roots[0], encoding="unicode")
        if not has_main_header
        and roots[0].xpath(
            './/*[@resource-id="PostDetail"]/node[@scrollable="true"]/node/node[@resource-id="timeline_post"]'
        )
        else native
    )
    lists, cuts, signatures = [], [], []
    for scope in scopes:
        listing = _one(scope[0].xpath('./node[@scrollable="true"]'), "detail list")
        markers = [n for n in listing if n.xpath('./node[@text="View quotes"]')]
        if not markers:
            return fallback
        marker = _one(markers, "thread boundary")
        cut = list(listing).index(marker) + 1
        timestamps = [
            n
            for n in listing[:cut]
            if " • " in n.get("text", "") and n.get("text", "").endswith(" Views")
        ]
        if len(timestamps) != 1:
            return fallback
        stamp = timestamps[0]
        controls = tuple(
            (n.get("text") or n.get("content-desc"), _rect(n))
            for child in listing[list(listing).index(stamp) + 1 : cut]
            for n in child.iter()
            if n.get("content-desc") in (*ACTION_LABELS, *ACTION_ALIASES)
            or n.get("text") in {"Relevant", "Most recent", "Most liked", "View quotes"}
        )
        signatures.append(
            (
                _rect(scope[0]),
                _rect(listing),
                stamp.get("text").rsplit(" • ", 1)[0],
                _rect(stamp)[1::2],
                controls,
            )
        )
        lists.append(listing)
        cuts.append(cut)
    if signatures[0] != signatures[1]:
        raise _Unsupported("The thread changed position across native reads.")
    for node in list(lists[1])[cuts[1] :]:
        lists[1].remove(node)
    for node in list(lists[0])[cuts[0] :]:
        lists[1].append(node)
    return etree.tostring(roots[1], encoding="unicode")


def _author_column(node):
    return (
        node.get("class") == "android.view.View"
        and not node.get("text")
        and not node.get("content-desc")
        and not node.get("resource-id")
        and all(
            node.get(flag) != "true"
            for flag in ("clickable", "long-clickable", "focusable", "scrollable")
        )
    )


def _author_badges(identity, name):
    badges = list(identity)[1:-1]
    if len(badges) > 2 or (
        badges and badges[0].get("content-desc") not in VERIFICATION_LABELS
    ):
        raise _Unsupported("Unrecognized main-post author badge.")
    previous = _rect(name)
    for badge in badges:
        rect = _rect(badge)
        if (
            badge.get("class") != "android.view.View"
            or badge.get("package") != PACKAGE
            or badge.get("text")
            or badge.get("resource-id")
            or not badge.get("content-desc", "").strip()
            or len(badge)
            or any(
                badge.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "focusable", "scrollable")
            )
            or badge.get("enabled") == "false"
            or badge.get("visible-to-user") == "false"
            or rect[0] < previous[2]
            or not previous[1] <= rect[1] < rect[3] <= previous[3]
            or _intersect(rect, _rect(identity)) != rect
        ):
            raise _Unsupported("Unrecognized main-post author badge.")
        previous = rect
    if len(badges) == 2:
        verification, affiliation = badges
        left, top, right, bottom = _rect(affiliation)
        verified = _rect(verification)
        # This slot is an affiliation icon, not another verification label.
        if (
            affiliation.get("content-desc") in VERIFICATION_LABELS
            or right - left != bottom - top
            or right - left > verified[2] - verified[0]
        ):
            raise _Unsupported("Unrecognized main-post affiliation badge.")
    return badges


def _identity(listing):
    avatars = listing.xpath('./node/node[@resource-id="timeline_post_avatar"]')
    if not avatars:
        return None
    avatar = _one(avatars, "main-post avatar")
    header = avatar.getparent()
    if len(header) != 2 or header[0] is not avatar:
        raise _Unsupported("Unrecognized main-post author layout.")
    identity = header[1]
    texts = [n for n in identity if n.get("text")]
    if (
        len(texts) != 2
        or not _author_column(identity)
        or identity[0] is not texts[0]
        or identity[-1] is not texts[1]
        or not all(_plain_annotation(n) for n in texts)
        or not HANDLE.fullmatch(texts[1].get("text"))
        or avatar.get("content-desc") != texts[0].get("text")
        or _rect(texts[0])[3] > _rect(texts[1])[1]
        or _rect(texts[0])[0] != _rect(texts[1])[0]
        or _rect(avatar)[2] > _rect(identity)[0]
    ):
        raise _Unsupported("Unrecognized main-post name and handle.")
    badges = _author_badges(identity, texts[0])
    return header, identity, texts[0], texts[1], badges


def main_header_visible(listing, viewport, overlays):
    from .inspection import _control_covers

    try:
        identity = _identity(listing)
    except _Unsupported:
        if _clipped_name(listing, viewport):
            return False
        raise
    if identity is None:
        return (
            False
            if listing.getroottree().getroot().get("taktik-reader") == "screen-reader"
            else None
        )
    _, _, name, handle, badges = identity
    return all(
        _visibility(
            node, viewport, (*overlays, *_control_covers(listing, node))
        ).unobscured
        for node in (name, handle, *badges)
    )


def _clipped_name(listing, viewport):
    """A scrolled native header can omit the name above its clipped handle."""
    avatars = listing.xpath('./node/node[@resource-id="timeline_post_avatar"]')
    if len(avatars) != 1:
        return False
    avatar = avatars[0]
    header = avatar.getparent()
    if len(header) != 2 or header[0] is not avatar or len(header[1]) != 1:
        return False
    handle = header[1][0]
    return (
        bool(avatar.get("content-desc"))
        and _author_column(header[1])
        and _plain_annotation(handle)
        and bool(HANDLE.fullmatch(handle.get("text", "")))
        and _rect(avatar)[2] <= _rect(header[1])[0] <= _rect(handle)[0]
        and _rect(header)[1] < _rect(handle)[1] < viewport[1]
    )


def _action_root(node, listing):
    icons = [
        d
        for d in node.iter()
        if d.get("content-desc") in (*ACTION_LABELS, *ACTION_ALIASES)
    ]
    return len(icons) == 1 and _clickable(icons[0], listing) is node


def _content(listing, header, timestamp):
    children = list(listing)
    index = children.index(header)
    options = [
        n for n in children[index + 1 :] if n.get("content-desc") == "Post options"
    ]
    options = _one(options, "main-post options")
    start = children.index(options) + 1
    endings = [
        i
        for i, n in enumerate(children[start:], start)
        if n is timestamp
        or n.xpath('./node[@resource-id="timeline_post"]')
        or _action_root(n, listing)
        or any(
            d.get("text") in {"Relevant", "Most recent", "Most liked", "View quotes"}
            for d in n.iter()
        )
    ]
    return tuple(children[start : min(endings, default=len(children))])


def read_main(listing, viewport, overlays, timestamp):
    from .inspection import _control_covers

    identity = _identity(listing)
    if identity is None:
        return None
    header, column, name, handle, badges = identity
    roots = _content(listing, header, timestamp)
    markers = [
        n for root in roots for n in root.iter() if n.get("content-desc") == "Quote"
    ]
    quote = card = None
    if markers:
        card = _clickable(_one(markers, "main-post quote"), listing)
        quote, card = _quote_bundle(card, viewport, overlays)
    outside = tuple(n for n in listing if n not in roots)
    excluded = (*outside, *((card,) if card is not None else ()))
    media, known = _media(listing, viewport, overlays, excluded)
    if card is not None:
        known.update(card.iter())
    bodies = [
        n
        for n in roots
        if n.get("class") == "android.widget.TextView" and n not in known
    ]
    if len(bodies) > 1:
        raise _Unsupported("Ambiguous main-post body.")
    body = bodies[0] if bodies else None
    annotations, _ = _body_annotations(body)
    if body is not None:
        if (
            not body.get("text")
            or body.get("content-desc")
            or any(
                body.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable")
            )
            or roots[0] is not body
            or _rect(body)[1] < _rect(header)[3]
        ):
            raise _Unsupported("Unrecognized main-post body.")
        known.update(body.iter())
    for root in roots:
        if any(
            n not in known and (n.get("text") or n.get("content-desc"))
            for n in root.iter()
        ):
            raise _Unsupported("Unrecognized main-post content.")
        if root is not body and not any(n in known for n in root.iter()):
            raise _Unsupported("Unreported main-post content.")
    if body is None and not media and quote is None:
        return None
    action_roots = set()
    if timestamp is not None:
        for node in list(listing)[list(listing).index(timestamp) + 1 :]:
            if not _action_root(node, listing):
                break
            action_roots.add(node)
    actions, _ = _actions(
        listing,
        viewport,
        overlays,
        tuple(n for n in listing if n not in action_roots),
    )
    body_view = (
        _visibility(body, viewport, (*overlays, *_control_covers(listing, body)))
        if body is not None
        else None
    )
    rects = [_rect(header), *(_rect(n) for n in roots)]
    rect = (
        min(r[0] for r in rects),
        min(r[1] for r in rects),
        max(r[2] for r in rects),
        max(r[3] for r in rects),
    )
    text = body.get("text") if body is not None else None
    key = [
        "detail",
        handle.get("text").lower(),
        text,
        [(m.kind, m.description) for m in media],
    ]
    if quote is not None:
        key.append(
            [quote.author, quote.body, [(m.kind, m.description) for m in quote.media]]
        )
    header_view = _visibility(
        column, viewport, (*overlays, *_control_covers(listing, column))
    )
    text_rects = [_rect(n) for n in (name, handle, *badges)]
    text_rect = (
        min(r[0] for r in text_rects),
        min(r[1] for r in text_rects),
        max(r[2] for r in text_rects),
        max(r[3] for r in text_rects),
    )
    header_view = replace(
        header_view,
        bounds=text_rect,
        visible_bounds=_intersect(text_rect, header_view.visible_bounds),
        overlaps=tuple(r for r in header_view.overlaps if _intersect(text_rect, r)),
    )
    return Post(
        author=handle.get("text"),
        display_name=name.get("text"),
        body=text,
        body_complete=body is not None and _body_complete(text, body_view),
        age=timestamp.get("text").rsplit(" • ", 1)[0] if timestamp is not None else "",
        content_key=hashlib.sha256(
            json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        visibility=Visibility(
            rect,
            _intersect(rect, viewport),
            tuple(r for r in overlays if _intersect(rect, r)),
        ),
        header_visibility=header_view,
        author_visibility=_visibility(
            handle, viewport, (*overlays, *_control_covers(listing, handle))
        ),
        body_visibility=body_view,
        media=media,
        quoted_post=quote,
        labels=tuple(n.get("content-desc") for n in badges),
        actions=actions,
        body_annotations=annotations,
    )
