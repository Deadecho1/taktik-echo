"""Pure evidence and safe targets for temporary X inspection surfaces."""

from dataclasses import dataclass

from .detail_text import DetailText, read_text
from .screen import (
    HANDLE,
    Post,
    Rect,
    RejectedPost,
    Screen,
    ScrollArea,
    Target,
    TextSpan,
    _clickable,
    _desc,
    _header_bar,
    _intersect,
    _one,
    _post,
    _rect,
    _scroll_area,
    _scroll_container,
    _target,
    _Unsupported,
    _visibility,
)


@dataclass(frozen=True)
class Profile:
    handle: str
    display_name: str
    text: tuple[TextSpan, ...]


@dataclass(frozen=True)
class Detail:
    main_post: Post | None
    main_reason: str | None
    timestamp: TextSpan | None
    sort_order: TextSpan | None
    text: DetailText | None = None
    main_header_visible: bool | None = None


@dataclass(frozen=True)
class Gallery:
    author: str
    display_name: str
    caption: TextSpan
    description: str
    crop: Rect
    # The native node retains text beyond the gallery's visibly shortened caption.
    caption_complete: bool = False


def _control_covers(root, node):
    ancestors = set(node.iterancestors())
    return tuple(
        _rect(n)
        for n in root.iter()
        if n is not node and n not in ancestors and n.get("clickable") == "true"
    )


def back_target(scope, area, overlays):
    back = _one(_desc(scope, "Back"), "inspection Back")
    clickable = _clickable(back, scope)
    chrome = _header_bar(back, scope)
    covers = (*overlays, *_control_covers(chrome, clickable))
    if not _visibility(back, area, covers).unobscured:
        raise _Unsupported("Inspection Back label is obscured.")
    return _target(back, "Back", scope, area, covers)


def post_targets(header, media, viewport, overlays):
    container = header.getparent()
    area = _scroll_container(container, viewport, overlays)
    # Native inline links need not have separate clickable accessibility nodes.
    texts = tuple(_rect(n) for n in container.iter() if n.get("text"))
    targets = [
        Target(
            "Open post",
            _visibility(container, viewport, (*overlays, *area.exclusions, *texts)),
        )
    ]
    avatars = [
        n
        for child in list(container)[: list(container).index(header)]
        for n in child.iter()
        if n.get("class") == "android.widget.ImageView"
        and n.get("clickable") == "true"
        and n.get("content-desc") == header[0].get("text")
        and _rect(n)[2] <= _rect(header)[0]
        and _rect(n)[1] <= _rect(header)[3] <= _rect(n)[3]
    ]
    if len(avatars) == 1:
        avatar = avatars[0]
        covers = _control_covers(container, avatar)
        targets.append(
            Target("Visit author", _visibility(avatar, viewport, (*overlays, *covers)))
        )
    for index, item in enumerate(media):
        if item.kind not in {"image", "video", "gif"}:
            continue
        nodes = [
            n
            for n in container.iter()
            if n.get("content-desc") == item.description
            and _rect(n) == item.visibility.bounds
        ]
        if len(nodes) != 1:
            continue
        node = nodes[0]
        try:
            clickable = _clickable(node, container)
        except _Unsupported:
            continue
        if _intersect(_rect(clickable), _rect(node)) != _rect(node):
            continue
        targets.append(Target(f"Open media {index}", item.visibility))
    return tuple(targets)


def read_profile(scope, viewport, overlays, handle):
    if handle is None:
        return None
    node = _one(
        scope.xpath(
            './/*[@class="android.widget.ScrollView"]/node[@text=$handle]',
            handle=handle,
        ),
        "profile handle",
    )
    header = node.getparent()
    texts = [n for n in header if n.get("text")]
    if len(texts) != 2 or texts[1] is not node:
        raise _Unsupported("Unrecognized profile name and handle.")
    top = min(_rect(n)[1] for n in texts) - 1
    area = (viewport[0], top, viewport[2], viewport[1])
    if not all(_visibility(n, area, overlays).unobscured for n in texts):
        raise _Unsupported("Profile identity text is obscured.")
    spans = tuple(
        TextSpan(n.get("text"), visibility)
        for n in header.iterdescendants()
        if n.get("text") and (visibility := _visibility(n, area, overlays)).unobscured
    )
    return Profile(handle, texts[0].get("text"), spans)


def read_detail(scope, viewport, overlays):
    listing = _one(scope.xpath('./node[@scrollable="true"]'), "detail list")
    timestamps = [
        n
        for n in listing
        if n.get("class") == "android.widget.TextView"
        and " • " in n.get("text", "")
        and n.get("text", "").endswith(" Views")
    ]
    if len(timestamps) > 1:
        raise _Unsupported("Ambiguous main-post timestamp.")
    timestamp = timestamps[0] if timestamps else None
    sort_nodes = [
        n
        for n in listing.xpath('./node/node[@class="android.widget.TextView"]')
        if n.get("text") in {"Relevant", "Most recent", "Most liked"}
    ]
    if len(sort_nodes) > 1:
        raise _Unsupported("Ambiguous thread sort order.")
    sort_node = sort_nodes[0] if sort_nodes else None

    def span(node):
        if node is not None:
            visibility = _visibility(node, viewport, overlays)
            if visibility.unobscured:
                return TextSpan(node.get("text"), visibility)
        return None

    from .detail import main_header_visible, read_main

    reason = (
        "Main post unavailable: the inspected detail layout omits its author and body."
    )
    try:
        main = read_main(listing, viewport, overlays, timestamp)
        if main is not None:
            reason = None
    except _Unsupported as error:
        main, reason = None, str(error)
    detail = Detail(
        main,
        reason,
        span(timestamp),
        span(sort_node),
        read_text(listing, viewport, overlays, timestamp),
        main_header_visible(listing, viewport, overlays),
    )
    posts, rejected, areas, anchors = [], [], [], []
    for header in listing.xpath('./node/node[@resource-id="timeline_post"]'):
        try:
            posts.append(_post(header, viewport, overlays))
        except _Unsupported as error:
            rejected.append(RejectedPost(_rect(header.getparent()), str(error)))
        try:
            areas.append(_scroll_area(header, viewport, overlays))
        except _Unsupported:
            pass
    # Empty native main-content views may contain unreported media. Exclude them
    # along with every nested control before offering the remaining list space.
    unknown = tuple(
        _rect(n)
        for n in listing
        if not n.get("text")
        and not n.get("content-desc")
        and not n.xpath('./node[@resource-id="timeline_post"]')
    )
    base = _scroll_container(listing, viewport, overlays)
    containers = {
        _rect(h.getparent())
        for h in listing.xpath('./node/node[@resource-id="timeline_post"]')
    }
    areas.append(
        ScrollArea(
            base.visibility,
            (*(r for r in base.exclusions if r not in containers), *unknown),
        )
    )
    for n in listing.iterdescendants():
        text = n.get("text", "")
        if len(text) >= 4 and sum(c.isalpha() for c in text) >= 3:
            visibility = _visibility(n, viewport, overlays)
            if visibility.accessible and visibility.visible_bounds is not None:
                anchors.append(TextSpan(text, visibility))
    if detail.text is not None:
        anchors.extend(detail.text.anchors)
    return detail, tuple(posts), tuple(rejected), tuple(areas), tuple(anchors)


def read_gallery(scope, area, overlays):
    actions = _one(
        scope.xpath('.//*[@resource-id="GalleryActionBar"]'), "gallery actions"
    )
    bottom = _one(
        scope.xpath('.//*[@resource-id="GalleryBottomBar"]'), "gallery bottom bar"
    )
    chrome = actions.getparent()
    if bottom.getparent().getparent() is not chrome:
        raise _Unsupported("Unrecognized gallery controls.")
    target = back_target(scope, area, overlays)
    caption = _one(
        chrome.xpath('./node[@class="android.widget.TextView"]'), "gallery caption"
    )
    handles = [
        n
        for n in chrome.xpath('./node/node/node[@class="android.widget.TextView"]')
        if HANDLE.fullmatch(n.get("text", ""))
    ]
    handle = _one(handles, "gallery author")
    header = handle.getparent()
    name = _one(
        [n for n in header if n.get("text") and n is not handle], "gallery display name"
    )
    if not all(
        _visibility(n, area, (*overlays, *_control_covers(chrome, n))).unobscured
        for n in (name, handle, caption)
    ):
        raise _Unsupported("Gallery identity is obscured.")
    if not (
        _rect(header)[3] <= _rect(caption)[1] < _rect(caption)[3] <= _rect(actions)[1]
    ):
        raise _Unsupported("Unrecognized gallery caption placement.")
    media_host = _one([n for n in scope if n is not chrome], "gallery media host")
    image = _one(
        media_host.xpath('.//*[@content-desc!=""]'), "gallery image description"
    )
    visibility = _visibility(image, area, overlays)
    crop = visibility.visible_bounds
    if crop is None or not visibility.accessible or visibility.overlaps:
        raise _Unsupported("Gallery image is obscured.")
    controls = [n for n in chrome.iter() if n.get("clickable") == "true"]
    if any(
        _intersect(crop, _rect(n))
        for n in (*controls, caption, header, actions, bottom)
    ):
        raise _Unsupported("Gallery controls cover its image.")
    return Screen(
        "media",
        content_viewport=crop,
        overlaps=tuple(overlays),
        controls=(target,),
        gallery=Gallery(
            handle.get("text"),
            name.get("text"),
            TextSpan(caption.get("text"), _visibility(caption, area, overlays)),
            image.get("content-desc"),
            crop,
        ),
    )
