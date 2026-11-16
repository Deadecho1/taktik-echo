"""Pure interpretation of the inspected English X hierarchies.

The caller must verify the foreground app through Phone before using this data.
Targets and content keys are snapshot evidence, not permission to engage.
"""

import hashlib
import json
import re
from dataclasses import dataclass, replace
from itertools import pairwise

from lxml import etree

from taktik.core.shared.ui.geometry import bounds

PACKAGE = "com.twitter.android"
HANDLE = re.compile(r"@[A-Za-z0-9_]{1,15}", re.ASCII)
PRIMARY = {
    "PostDetail": "detail",
    "UserProfileScreen": "profile",
    "SearchQuery": "search_input",
    "Search": "search_results",
    "scaffold_home_tabbed": "home",
}
ACTION_LABELS = ("Reply", "Repost", "Like", "Impressions", "Bookmark", "Share")
Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class Visibility:
    bounds: Rect
    visible_bounds: Rect | None
    overlaps: tuple[Rect, ...] = ()
    accessible: bool = True
    clipped: bool = False

    @property
    def unobscured(self):
        return (
            self.accessible
            and self.visible_bounds == self.bounds
            and not self.overlaps
            and not self.clipped
        )


@dataclass(frozen=True)
class Target:
    label: str
    visibility: Visibility
    count: str | None = None
    selected: bool | None = None


@dataclass(frozen=True)
class Media:
    kind: str
    description: str | None
    visibility: Visibility
    source_label: str | None = None
    preview_text: str | None = None
    preview_text_visibility: Visibility | None = None
    description_visibility: Visibility | None = None
    source_prefix: str | None = None


@dataclass(frozen=True)
class ScrollArea:
    visibility: Visibility
    exclusions: tuple[Rect, ...]


@dataclass(frozen=True)
class QuotedPost:
    author: str
    display_name: str
    body: str | None
    body_complete: bool
    media: tuple[Media, ...]
    visibility: Visibility
    header_visibility: Visibility
    body_visibility: Visibility | None
    labels: tuple[str, ...] = ()
    translation: str | None = None
    nested_quote: "QuotedPost | None" = None
    footer_annotations: tuple["TextSpan", ...] = ()
    body_annotations: tuple["TextSpan", ...] = ()

    @property
    def observable(self):
        return (
            (self.nested_quote is None or self.nested_quote.observable)
            and self.header_visibility.unobscured
            and (
                self.body_visibility.unobscured
                if self.body_visibility is not None
                else any(
                    m.description
                    and (m.description_visibility or m.visibility).unobscured
                    for m in self.media
                )
            )
        )


@dataclass(frozen=True)
class CommunityNote:
    title: str
    body: str
    body_complete: bool
    translation: str | None
    visibility: Visibility
    header_visibility: Visibility
    body_visibility: Visibility


@dataclass(frozen=True)
class MarketCard:
    name: str
    symbol: str
    price: str
    change: str
    visibility: Visibility


@dataclass(frozen=True)
class Post:
    author: str
    display_name: str
    body: str | None
    body_complete: bool
    age: str
    content_key: str
    visibility: Visibility
    header_visibility: Visibility
    author_visibility: Visibility
    body_visibility: Visibility | None
    media: tuple[Media, ...] = ()
    quoted_post: QuotedPost | None = None
    reposted_by: str | None = None
    reply_annotation: str | None = None
    reply_to: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    media_tags: tuple[str, ...] = ()
    actions: tuple[Target, ...] = ()
    # Absence of a supported disclosure is not proof of organic content.
    advertising: str = "unknown"
    translation: str | None = None
    media_labels: tuple[str, ...] = ()
    body_annotations: tuple[str, ...] = ()
    advertising_visibility: Visibility | None = None
    community_note: CommunityNote | None = None
    market_card: MarketCard | None = None

    @property
    def observable(self):
        quote = self.quoted_post
        return (
            self.header_visibility.unobscured
            and self.author_visibility.unobscured
            and (
                self.body_visibility.unobscured
                if self.body_visibility is not None
                else any(
                    m.visibility.accessible
                    and m.visibility.visible_bounds is not None
                    and not any(
                        _intersect(m.visibility.visible_bounds, rect)
                        == m.visibility.visible_bounds
                        for rect in m.visibility.overlaps
                    )
                    for m in self.media
                )
            )
            and (quote is None or quote.observable)
        )


@dataclass(frozen=True)
class RejectedPost:
    bounds: Rect | None
    reason: str


@dataclass(frozen=True)
class TextSpan:
    text: str
    visibility: Visibility


@dataclass(frozen=True)
class PostFragment:
    """Unattributed content for continuity only; never a new observation."""

    body: str | None
    media: tuple[Media, ...]
    visibility: Visibility
    body_visibility: Visibility | None
    actions: tuple[Target, ...] = ()
    quoted_post: QuotedPost | None = None
    translation: str | None = None
    body_annotations: tuple[str, ...] = ()
    advertising: str = "unknown"
    advertising_visibility: Visibility | None = None
    community_note: CommunityNote | None = None
    preview_texts: tuple[TextSpan, ...] = ()
    media_labels: tuple[str, ...] = ()
    quoted_body: TextSpan | None = None
    covered_header_visibility: Visibility | None = None
    covered_handle: TextSpan | None = None
    quoted_footer_annotations: tuple[TextSpan, ...] = ()
    quoted_body_annotations: tuple[TextSpan, ...] = ()
    market_card: MarketCard | None = None


@dataclass(frozen=True)
class Screen:
    kind: str
    reason: str | None = None
    tab: str | None = None
    query: str | None = None
    active_account: str | None = None
    profile_handle: str | None = None
    content_viewport: Rect | None = None
    overlaps: tuple[Rect, ...] = ()
    controls: tuple[Target, ...] = ()
    posts: tuple[Post, ...] = ()
    rejected_posts: tuple[RejectedPost, ...] = ()
    empty: bool = False
    scroll_areas: tuple[ScrollArea, ...] = ()
    collapsed: bool = False
    fragments: tuple[PostFragment, ...] = ()
    waiting_for: str | None = None

    @property
    def observable_posts(self):
        return tuple(post for post in self.posts if post.observable)


class _Unsupported(ValueError):
    pass


class _MissingHomeComposer(_Unsupported):
    pass


def _one(items, description):
    if len(items) != 1:
        raise _Unsupported(f"Expected one {description}; found {len(items)}.")
    return items[0]


def _desc(root, label):
    return root.xpath(".//*[@content-desc=$label]", label=label)


def _rect(node):
    rect = bounds(node)
    if rect is None or rect[0] >= rect[2] or rect[1] >= rect[3]:
        raise _Unsupported("Missing or invalid node bounds.")
    return rect


def _intersect(a, b):
    if a is None or b is None:
        return None
    result = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return result if result[0] < result[2] and result[1] < result[3] else None


def _visibility(node, viewport, overlaps=()):
    rect = _rect(node)
    visible = _intersect(rect, viewport)
    accessible = True
    for ancestor in (node, *node.iterancestors()):
        accessible &= (
            ancestor.get("enabled") != "false"
            and ancestor.get("visible-to-user") != "false"
        )
        if ancestor.get("bounds"):
            visible = _intersect(visible, _rect(ancestor))
    return Visibility(
        rect,
        visible if accessible else None,
        tuple(area for area in overlaps if _intersect(visible, area)),
        accessible,
        node.get("class") == "android.widget.TextView"
        and (rect[1] <= viewport[1] or rect[3] >= viewport[3]),
    )


def _clickable(node, boundary):
    for current in (node, *node.iterancestors()):
        if current is boundary:
            break
        if current.get("clickable") == "true":
            return current
    raise _Unsupported("Control has no scoped clickable target.")


def _target(node, label, boundary, viewport, overlaps=(), count=None):
    target = _clickable(node, boundary)
    selected = target.get("selected")
    return Target(
        label,
        _visibility(target, viewport, overlaps),
        count,
        None if selected is None else selected == "true",
    )


def _handle(nodes, description):
    candidates = [node for node in nodes if node.get("text", "").startswith("@")]
    node = _one(candidates, description)
    if not HANDLE.fullmatch(node.get("text", "")):
        raise _Unsupported(f"Invalid {description}.")
    return node


def _navigation(root):
    home = _one(_desc(root, "Home"), "bottom Home control")
    row = home.getparent().getparent()
    for label in ("Home", "Explore", "Grok"):
        _one(_desc(row, label), f"bottom {label} control")
    return row


def _tabs(root, required, bottom):
    anchors = [node for node in _desc(root, required[0]) if _rect(node)[3] <= bottom]
    anchor = _one(anchors, f"{required[0]} tab")
    row = anchor.getparent().getparent()
    for label in required:
        _one(_desc(row, label), f"{label} tab")
    selected = [child for child in row if child.get("selected") == "true"]
    wrapper = _one(selected, "selected tab wrapper")
    label = _one(wrapper.xpath('./node[@content-desc!=""]'), "selected tab label").get(
        "content-desc"
    )
    return label, wrapper, row


def _header_bar(node, scope):
    for ancestor in node.iterancestors():
        if ancestor is scope:
            break
        rect = _rect(ancestor)
        if rect[0] == _rect(scope)[0] and rect[2] == _rect(scope)[2]:
            return ancestor
    raise _Unsupported("Missing screen header bar.")


def _drawer(root, area, overlays):
    close = _one(_desc(root, "Close navigation menu"), "drawer dismissal")
    profile = _one(root.xpath('.//*[@text="Profile"]'), "drawer Profile row")
    menu = _one(
        [
            n
            for n in profile.iterancestors()
            if n.get("class") == "android.widget.ScrollView"
        ],
        "drawer menu",
    )
    headers = [
        n
        for n in menu.getparent()
        if n.get("clickable") == "true" and _rect(n)[3] <= _rect(menu)[1]
    ]
    header = _one(headers, "drawer account header")
    handle = _handle(header.iter(), "drawer account handle")
    if not _visibility(handle, area, overlays).unobscured:
        raise _Unsupported("Drawer account handle is obscured.")
    return Screen(
        "drawer",
        active_account=handle.get("text"),
        overlaps=overlays,
        controls=(
            _target(close, "Close navigation menu", root, area, overlays),
            _target(profile, "Profile", root, area, overlays),
        ),
    )


def _post_options(root, area, overlays):
    close = _one(_desc(root, "Close sheet"), "sheet dismissal")
    menu = _one(root.xpath('.//*[@class="android.widget.ScrollView"]'), "options list")
    labels = []
    controls = [_target(close, "Close sheet", root, area, overlays)]
    for row in menu:
        text = _one(row.xpath('.//*[@text!=""]'), "option label")
        label = text.get("text")
        labels.append(label)
        if not _visibility(text, area, overlays).unobscured:
            raise _Unsupported("Post options are obscured.")
        controls.append(_target(text, label, menu, area, overlays))
    expected = {
        "This post's not helpful",
        "Add/remove from Lists",
        "Report post",
        "Request Community Note",
        "View Post Interactions",
        "View Hidden Replies",
    }
    author_labels = [label for label in labels if label not in expected]
    authors = []
    for prefix in ("Follow ", "Mute ", "Block "):
        label = _one(
            [s for s in author_labels if s.startswith(prefix)], prefix + "option"
        )
        handle = label.removeprefix(prefix)
        if not HANDLE.fullmatch(handle):
            raise _Unsupported("Invalid options author.")
        authors.append(handle.lower())
    if len(labels) != 9 or not expected.issubset(labels) or len(set(authors)) != 1:
        raise _Unsupported("Unrecognized post options structure.")
    return Screen("post_options", overlaps=overlays, controls=tuple(controls))


def _profile_identity(scope, area, content_top, overlays):
    edit = [
        node
        for node in scope.xpath('.//*[@text="Edit profile"]')
        if _rect(node)[3] <= content_top
    ]
    headers = scope.xpath(
        './/*[@class="android.widget.ScrollView"][node[starts-with(@text,"@")]]'
    )
    if not headers:
        if edit:
            raise _Unsupported("Own profile has no account handle.")
        return None, None
    header = _one(headers, "profile identity header")
    if header.xpath('.//*[@resource-id="timeline_post"]'):
        raise _Unsupported("Profile identity overlaps post list.")
    handle = _handle(header, "profile handle")
    if (
        _rect(handle)[3] > content_top
        or not _visibility(handle, area, overlays).unobscured
    ):
        raise _Unsupported("Profile handle is obscured.")
    value = handle.get("text")
    edit = [node for node in edit if header in node.iterancestors()]
    own = bool(edit)
    if own:
        _clickable(_one(edit, "Edit profile control"), scope)
    return value, value if own else None


def _video_credit(video):
    parent = video.getparent()
    if parent.get("clickable") != "true":
        return None
    credits = [
        n
        for n in parent
        if n is not video
        and n.get("clickable") == "true"
        and n.xpath('.//*[@text!=""]')
    ]
    if not credits:
        return None
    credit = _one(credits, "video source label")
    children = list(credit)
    prefix = (
        children[0] if children and children[0].get("text") == "Clip from" else None
    )
    account = children[1:] if prefix is not None else children
    if (
        len(account) not in (2, 3)
        or any(len(child) for child in children)
        or account[0].get("class") != "android.view.View"
        or account[1].get("class") != "android.widget.TextView"
        or not account[1].get("text")
        or account[0].get("content-desc") != account[1].get("text")
        or (
            len(account) == 3
            and (
                account[2].get("class") != "android.view.View"
                or account[2].get("content-desc")
                not in {
                    "Verified",
                    "Verified Business",
                    "Verified Governmental Account",
                }
                or account[2].get("text")
            )
        )
        or account[0].get("text")
        or account[1].get("content-desc")
        or (
            prefix is not None
            and (
                prefix.get("class") != "android.widget.TextView"
                or prefix.get("content-desc")
            )
        )
        or any(
            child.get("enabled") != "true"
            or any(
                child.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable", "focusable")
            )
            or _intersect(_rect(child), _rect(credit)) != _rect(child)
            for child in children
        )
        or any(
            _rect(left)[2] > _rect(right)[0]
            or max(_rect(left)[1], _rect(right)[1])
            >= min(_rect(left)[3], _rect(right)[3])
            for left, right in pairwise(children)
        )
        or not (
            _rect(video)[0] <= _rect(credit)[0] < _rect(credit)[2] <= _rect(video)[2]
            and _rect(video)[1] <= _rect(credit)[1]
        )
        or any(
            _intersect(_rect(child), _rect(video)) != _rect(child) for child in children
        )
    ):
        raise _Unsupported("Unrecognized video source label.")
    return (
        credit,
        account[1].get("text"),
        prefix.get("text") if prefix is not None else None,
    )


def _media(root, viewport, overlaps, excluded=()):
    result, covered = [], set()
    for node in root.iter():
        if any(node is skip or skip in node.iterancestors() for skip in excluded):
            continue
        desc = node.get("content-desc", "")
        if desc in {"Video", "GIF", "Image"} or desc.startswith("Image:"):
            credit = _video_credit(node) if desc == "Video" else None
            source_label = source_prefix = None
            if credit is not None:
                credit, source_label, source_prefix = credit
                covered.update(credit.iter())
            ancestors = set(node.iterancestors())
            controls = tuple(
                _rect(control)
                for control in root.iter()
                if control is not node
                and control not in ancestors
                and control.get("clickable") == "true"
            )
            result.append(
                Media(
                    {"Video": "video", "GIF": "gif"}.get(desc, "image"),
                    desc,
                    _visibility(node, viewport, (*overlaps, *controls)),
                    source_label,
                    source_prefix=source_prefix,
                )
            )
            covered.add(node)
    return tuple(result), covered


def _body_complete(text, visibility):
    return visibility.unobscured and not re.search(r"(?:\s|\xa0)Show more\s*$", text)


def _body_annotations(body):
    if body is None or not len(body):
        return (), set()
    annotation = _one(list(body), "inline body annotation")
    if (
        len(annotation)
        or annotation.get("class") != "android.view.View"
        or annotation.get("content-desc") != "Iran flag"
        or annotation.get("text")
        or any(
            annotation.get(flag) == "true"
            for flag in ("clickable", "long-clickable", "scrollable", "focusable")
        )
        or _intersect(_rect(body), _rect(annotation)) != _rect(annotation)
    ):
        raise _Unsupported("Unrecognized inline body annotation.")
    return (annotation.get("content-desc"),), {annotation}


def _quote_preview(card, body, viewport, overlaps):
    previews = [
        n for n in card if n.get("content-desc", "").endswith("more media item")
    ]
    if not previews:
        return (), set()
    preview = _one(previews, "compact quote preview")
    if (
        body is None
        or preview.get("content-desc") != "1 more media item"
        or preview.get("class") != "android.view.View"
        or preview.get("clickable") == "true"
        or preview.get("text")
        or len(preview) != 1
        or len(preview[0])
        or preview[0].get("class") != "android.widget.TextView"
        or preview[0].get("text") != "+1"
        or preview[0].get("content-desc")
        or preview[0].get("clickable") == "true"
        or _intersect(_rect(preview), _rect(preview[0])) != _rect(preview[0])
        or _rect(preview)[1] != _rect(body)[1]
        or _rect(preview)[2] > _rect(body)[0]
        or list(card).index(preview) != list(card).index(body) - 1
    ):
        raise _Unsupported("Unrecognized compact quote preview.")
    return (
        Media(
            "preview",
            preview.get("content-desc"),
            _visibility(preview, viewport, overlaps),
        ),
    ), set(preview.iter())


def _compact_quote_video(card, body):
    candidates = [
        n
        for n in card
        if n.xpath('./node[@content-desc="Video"]') and n.get("clickable") == "true"
    ]
    if not candidates:
        return set()
    preview = _one(candidates, "compact quoted video")
    if body is None or len(preview) != 3:
        raise _Unsupported("Unrecognized compact quoted video.")
    video, picture, play = preview
    rect = _rect(preview)
    if (
        preview.get("class") != "android.view.View"
        or preview.get("text")
        or preview.get("content-desc")
        or preview.get("enabled") != "true"
        or preview.get("focusable") != "true"
        or preview.get("long-clickable") == "true"
        or preview.get("scrollable") == "true"
        or [n.get("content-desc", "") for n in preview] != ["Video", "", "play"]
        or any(
            len(n)
            or n.get("text")
            or n.get("class") != "android.view.View"
            or any(
                n.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable", "focusable")
            )
            for n in preview
        )
        or _rect(video) != rect
        or _rect(picture) != rect
        or _intersect(rect, _rect(play)) != _rect(play)
        or rect[2] - rect[0] != rect[3] - rect[1]
        or rect[1] != _rect(body)[1]
        or rect[2] > _rect(body)[0]
        or _intersect(rect, _rect(card)) != rect
        or _intersect(_rect(body), _rect(card)) != _rect(body)
        or preview.getnext() is not body
    ):
        raise _Unsupported("Unrecognized compact quoted video.")
    return set(preview.iter())


def _article_preview(card, preceding, viewport, overlaps, excluded=()):
    candidates = [n for n in card if n.get("clickable") == "true" and n not in excluded]
    if not candidates:
        return (), set()
    preview = _one(candidates, "quoted article preview")
    if len(preview) not in (1, 2, 3):
        raise _Unsupported("Unrecognized article preview.")
    picture, *texts = preview
    title = texts[0] if texts else None
    summary = texts[1] if len(texts) == 2 else None
    if (
        preview.get("class") != "android.view.View"
        or preview.get("text")
        or preview.get("content-desc")
        or preview.get("scrollable") == "true"
        or picture.get("class") != "android.view.View"
        or any(
            n.get("class") != "android.widget.TextView" or not n.get("text")
            for n in texts
        )
        or (summary is not None and _rect(summary)[1] <= _rect(title)[3])
        or any(
            len(n)
            or n.get("content-desc")
            or any(
                n.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable")
            )
            for n in preview
        )
        or picture.get("text")
        or list(card).index(preview) != list(card).index(preceding) + 1
        or _rect(preview)[1] <= _rect(preceding)[3]
        or (title is not None and _rect(picture)[3] > _rect(title)[1])
        or any(_intersect(_rect(preview), _rect(n)) != _rect(n) for n in preview)
        or (
            title is None
            and (
                _rect(preview)[3] < viewport[3]
                or _rect(preview)[3] != _rect(card)[3]
                or _rect(preview)[::2] != _rect(card)[::2]
                or _rect(picture)[:3] != _rect(preview)[:3]
            )
        )
    ):
        raise _Unsupported("Unrecognized article preview.")
    return (
        Media(
            "preview",
            title.get("text") if title is not None else None,
            _visibility(preview, viewport, overlaps),
            preview_text=summary.get("text") if summary is not None else None,
            preview_text_visibility=(
                _visibility(summary, viewport, overlaps)
                if summary is not None
                else None
            ),
            description_visibility=(
                _visibility(title, viewport, overlaps) if title is not None else None
            ),
        ),
    ), set(preview.iter())


def _plain_annotation(node, *, allowed_children=()):
    return (
        all(child in allowed_children for child in node)
        and node.get("class") == "android.widget.TextView"
        and not node.get("content-desc")
        and all(
            node.get(flag) != "true"
            for flag in ("clickable", "long-clickable", "scrollable", "focusable")
        )
        and node.get("enabled") != "false"
        and node.get("visible-to-user") != "false"
    )


def _quoted_translation(card, texts, viewport, overlaps):
    if (
        len(texts) == 4
        and texts[-1].get("text", "").startswith("Translated from ")
        and _rect(texts[-1])[0] > _rect(_one(_desc(card, "Quote"), "quote marker"))[0]
    ):
        raise _Unsupported("Quoted translation has no separate body.")
    if len(texts) != 5:
        return None
    name, handle, age, label, body = texts
    rect, body_rect = _rect(label), _rect(body)
    preceding = label.getnext()
    if preceding is not body:
        _, preview_nodes = _quote_preview(card, body, viewport, overlaps)
        compact_nodes = _compact_quote_video(card, body)
        if (
            preceding not in preview_nodes | compact_nodes
            or preceding.getnext() is not body
        ):
            raise _Unsupported("Unrecognized quoted translation annotation.")
    content_left = min(body_rect[0], _rect(preceding)[0])
    if (
        not re.fullmatch(
            r"Translated from [A-Za-z]+(?:[ ()-][A-Za-z]+)*", label.get("text")
        )
        or not _plain_annotation(label)
        or label.getprevious() is not age
        or rect[1] < max(_rect(n)[3] for n in (name, handle, age))
        or rect[3] > body_rect[1]
        or rect[0] <= content_left
        or rect[2] > body_rect[2]
    ):
        raise _Unsupported("Unrecognized quoted translation annotation.")
    return label


def _quote(card, viewport, overlaps):
    handle = _handle(card, "quoted author")
    texts = [n for n in card if n.get("text")]
    index = texts.index(handle)
    if (
        index != 1
        or len(texts) not in (3, 4, 5)
        or not texts[2].get("text").startswith("· ")
    ):
        raise _Unsupported("Unrecognized quote text arrangement.")
    translation = _quoted_translation(card, texts, viewport, overlaps)
    if translation is not None:
        texts.remove(translation)
    name, _, age, *bodies = texts
    body = bodies[0] if bodies else None
    _, annotation_nodes = _body_annotations(body)
    body_view = _visibility(body, viewport, overlaps) if body is not None else None
    media, media_nodes = _media(card, viewport, overlaps)
    compact_nodes = _compact_quote_video(card, body)
    previews, preview_nodes = _quote_preview(card, body, viewport, overlaps)
    articles, article_nodes = _article_preview(
        card, body if body is not None else age, viewport, overlaps, compact_nodes
    )
    header_only = (
        body is None
        and not media
        and not articles
        and not previews
        and _rect(card)[3] >= viewport[3]
        and all(
            _rect(n)[1] >= viewport[3] and _intersect(_rect(n), _rect(card)) == _rect(n)
            for n in (name, handle, age)
        )
    )
    if body is None and not articles and not header_only:
        raise _Unsupported("Bodyless quote has no recognized preview.")
    if articles and (previews or media):
        raise _Unsupported("Mixed article and quote media.")
    if previews and media:
        raise _Unsupported("Mixed compact and expanded quote media.")
    media += previews + articles
    labels = list(card)[list(card).index(name) + 1 : list(card).index(handle)]
    for label in labels:
        rect = _rect(label)
        if (
            len(label)
            or label.get("text")
            or not label.get("content-desc")
            or label.get("clickable") == "true"
            or label.get("class") != "android.view.View"
            or rect[0] < _rect(name)[2]
            or rect[2] > _rect(handle)[0]
            or rect[1] < _rect(handle)[1]
            or rect[3] > _rect(handle)[3]
        ):
            raise _Unsupported("Unrecognized quoted author label.")
    known = {
        name,
        handle,
        age,
        body,
        translation,
        *labels,
        *media_nodes,
        *compact_nodes,
        *preview_nodes,
        *article_nodes,
        *annotation_nodes,
    }
    for node in card.iter():
        if node in known:
            continue
        if node.get("text") or node.get("content-desc", "") not in (
            "",
            "Quote",
            "Verified",
            "Unmute",
        ):
            raise _Unsupported("Unrecognized quote content.")
    return QuotedPost(
        handle.get("text"),
        name.get("text"),
        body.get("text") if body is not None else None,
        # Compact translated quote bounds do not establish full text visibility.
        body is not None
        and translation is None
        and bool(_body_complete(body.get("text"), body_view)),
        media,
        _visibility(card, viewport, overlaps),
        _visibility(handle, viewport, overlaps),
        body_view,
        tuple(label.get("content-desc") for label in labels),
        translation.get("text") if translation is not None else None,
        body_annotations=tuple(
            TextSpan(n.get("content-desc"), _visibility(n, viewport, overlaps))
            for n in annotation_nodes
        ),
    )


def _quote_bundle(card, viewport, overlaps):
    quote = _quote(card, viewport, overlaps)
    wrapper = card.getparent()
    footer = _quote_footer_annotations(wrapper, viewport, overlaps)
    if footer:
        return replace(
            quote,
            footer_annotations=footer,
            visibility=_visibility(wrapper, viewport, overlaps),
        ), wrapper
    nested = [n for n in wrapper if n.get("resource-id") == "nested_quote_preview"]
    if not nested:
        return quote, card
    node = _one(nested, "nested quote preview")
    texts = [n for n in node if n.get("text")]
    if (
        list(wrapper) != [card, node]
        or wrapper.get("clickable") == "true"
        or node.get("class") != "android.view.View"
        or node.get("clickable") != "true"
        or node.get("text")
        or node.get("content-desc")
        or node.get("long-clickable") == "true"
        or node.get("scrollable") == "true"
        or len(texts) != 4
        or texts[-1].get("resource-id") != "nested_quote_body"
        or any(not _plain_annotation(n) for n in texts)
        or any(len(n) or n.get("clickable") == "true" for n in node)
        or any(_intersect(_rect(n), _rect(node)) != _rect(n) for n in texts)
        or len({(_rect(n)[1], _rect(n)[3]) for n in texts[:3]}) != 1
        or _rect(texts[-1])[1] <= _rect(texts[2])[3]
        or _rect(node)[1] <= _rect(card)[3]
        or _intersect(_rect(node), _rect(wrapper)) != _rect(node)
    ):
        raise _Unsupported("Unrecognized nested quote preview.")
    nested_quote = _quote(node, viewport, overlaps)
    if nested_quote.media or nested_quote.translation:
        raise _Unsupported("Unrecognized nested quote media.")
    return replace(
        quote,
        nested_quote=nested_quote,
        visibility=_visibility(wrapper, viewport, overlaps),
    ), wrapper


def _actions(container, viewport, overlaps, excluded):
    actions, covered = [], set()
    for label in ACTION_LABELS:
        icons = [
            n
            for n in _desc(container, label)
            if not any(q in n.iterancestors() for q in excluded)
        ]
        if not icons:
            continue
        icon = _one(icons, label + " icon")
        target = _clickable(icon, container)
        action_icons = [
            n for n in target.iter() if n.get("content-desc") in ACTION_LABELS
        ]
        if len(action_icons) != 1:
            raise _Unsupported("Actions share a clickable target.")
        counts = target.xpath('.//*[@text!=""]')
        count = _one(counts, label + " count").get("text") if counts else None
        if count is not None and not re.fullmatch(
            r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?[KMB]?", count
        ):
            raise _Unsupported("Unrecognized action count.")
        if any(n.get("content-desc", "") not in ("", label) for n in target.iter()):
            raise _Unsupported("Unrecognized action contents.")
        actions.append(_target(icon, label, container, viewport, overlaps, count))
        covered.update(target.iter())
    return tuple(actions), covered


def _covered_bookmark_row(container, actions, viewport, overlaps):
    """Recognize a covered empty slot without synthesizing a Bookmark target."""
    if tuple(a.label for a in actions) != tuple(
        label for label in ACTION_LABELS if label != "Bookmark"
    ) or len(container) < len(ACTION_LABELS):
        return False
    row = list(container)[-len(ACTION_LABELS) :]
    rects = [_rect(n) for n in row]
    if (
        any(n.get("clickable") != "true" for n in row)
        or len({r[1::2] for r in rects}) != 1
        or any(a[2] != b[0] for a, b in pairwise(rects))
        or rects[-1][2:] != _rect(container)[2:]
    ):
        return False
    icons = []
    for label, target in zip(ACTION_LABELS, row):
        if label == "Bookmark":
            if (
                len(target)
                or target.get("text")
                or target.get("content-desc")
                or target.get("class") != "android.view.View"
                or target.get("enabled") != "true"
            ):
                return False
            continue
        candidates = _desc(target, label)
        if len(candidates) != 1 or _clickable(candidates[0], container) is not target:
            return False
        icons.append(_rect(candidates[0]))
    # Four retained square icons locate the glyph row. Share may be clipped
    # horizontally by the same composer, but must retain its vertical edges.
    size = icons[0][2] - icons[0][0]
    top, bottom = icons[0][1::2]
    if (
        size != bottom - top
        or any(r[1::2] != (top, bottom) for r in icons)
        or any(r[2] - r[0] != size for r in icons[:-1])
    ):
        return False
    slot = rects[ACTION_LABELS.index("Bookmark")]
    center = (slot[0] + slot[2]) // 2
    # Narrow slots can clip a right-aligned glyph. Cover the entire band
    # through the slot's right edge, not only a centered square.
    expected = (center - size // 2, top, slot[2], bottom)
    return (
        _intersect(expected, slot) == expected
        and _intersect(expected, viewport) == expected
        and any(_intersect(expected, cover) == expected for cover in overlaps)
    )


def _translation(container, header=None, *, clipped_viewport=None):
    labels = [n for n in container if n.get("text", "").startswith("Translated from ")]
    controls = [n for n in container if n.get("text") == "Show original"]
    if not labels and not controls:
        return None, set()
    if not labels and header is None and clipped_viewport is not None:
        control = _one(controls, "clipped Show original control")
        body = control.getnext()
        rect = _rect(control)
        if (
            body is not None
            and _plain_annotation(body)
            and body.get("text")
            and control.get("class") == "android.widget.TextView"
            and not len(control)
            and not control.get("content-desc")
            and control.get("clickable") == "true"
            and control.get("enabled") == "true"
            and control.get("visible-to-user") != "false"
            and control.get("scrollable") != "true"
            and control.get("long-clickable") != "true"
            and rect[1] < clipped_viewport[1] < rect[3] == _rect(body)[1]
            and _rect(body)[0] < rect[0] < rect[2] <= _rect(body)[2]
        ):
            return None, {control}
    label = _one(labels, "translation label")
    control = _one(controls, "Show original control")
    if (
        not re.fullmatch(
            r"Translated from [A-Za-z]+(?:[ ()-][A-Za-z]+)*", label.get("text")
        )
        or label.getnext() is not control
        or (
            header is not None
            and (
                list(container).index(label) <= list(container).index(header)
                or _rect(label)[1] < _rect(header)[3]
            )
        )
        or _rect(control)[0] < _rect(label)[2]
        or label.get("clickable") == "true"
        or control.get("clickable") != "true"
        or any(
            len(n)
            or n.get("content-desc")
            or n.get("class") != "android.widget.TextView"
            for n in (label, control)
        )
    ):
        raise _Unsupported("Unrecognized translation annotation.")
    return label.get("text"), {label, control}


def _community_note(container, viewport, overlaps):
    markers = _desc(container, "Community Notes")
    if not markers:
        return None, None
    marker = _one(markers, "Community Notes marker")
    header = marker.getparent()
    card = header.getparent()
    title = marker.getnext()
    if (
        card.getparent() is not container
        or card.get("class") != "android.view.View"
        or card.get("clickable") != "true"
        or card.get("text")
        or card.get("content-desc")
        or len(header) != 2
        or header[0] is not marker
        or title.get("text")
        != "Readers added context they thought people might want to know"
        or not _plain_annotation(title)
        or marker.get("class") != "android.view.View"
        or marker.get("text")
        or len(marker)
        or any(
            n.get(flag) == "true"
            for n in (header, marker)
            for flag in ("clickable", "long-clickable", "scrollable")
        )
        or header.get("text")
        or header.get("content-desc")
        or _intersect(_rect(header), _rect(marker)) != _rect(marker)
        or _intersect(_rect(header), _rect(title)) != _rect(title)
        or _rect(marker)[2] > _rect(title)[0]
    ):
        raise _Unsupported("Unrecognized Community Note header.")
    translation, translation_nodes = _translation(card, header)
    bodies = [n for n in card if n is not header and n not in translation_nodes]
    body = _one(bodies, "Community Note body")
    if (
        not _plain_annotation(body)
        or not body.get("text")
        or card[0] is not header
        or card[-1] is not body
        or any(
            n.get(flag) == "true"
            for n in card.iter()
            for flag in ("long-clickable", "scrollable")
        )
        or any(
            _intersect(_rect(card), _rect(n)) != _rect(n)
            for n in (header, body, *translation_nodes)
        )
        or _rect(header)[3] > _rect(body)[1]
        or any(_rect(n)[3] > _rect(body)[1] for n in translation_nodes)
        or not _visibility(card, viewport, overlaps).accessible
        or (
            card.getprevious() is not None
            and _rect(card.getprevious())[3] > _rect(card)[1]
        )
    ):
        raise _Unsupported("Unrecognized Community Note body.")
    body_view = _visibility(body, viewport, overlaps)
    return CommunityNote(
        title.get("text"),
        body.get("text"),
        _body_complete(body.get("text"), body_view),
        translation,
        _visibility(card, viewport, overlaps),
        _visibility(header, viewport, overlaps),
        body_view,
    ), card


def _link_preview(container, viewport, overlaps):
    sources = [
        n
        for n in container
        if n.get("text", "").startswith("from ") and n.get("clickable") == "true"
    ]
    if not sources:
        return (), set()
    source = _one(sources, "link preview source")
    wrapper = card = source.getprevious()
    if card is not None and len(card) == 1:
        if (
            card.get("class") != "android.view.View"
            or card.get("text")
            or card.get("content-desc")
            or any(
                card.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable")
            )
            or _rect(card) != _rect(card[0])
        ):
            raise _Unsupported("Unrecognized link preview wrapper.")
        card = card[0]
    if card is None or len(card) != 2:
        raise _Unsupported("Unrecognized link preview.")
    picture, title = card
    if (
        not re.fullmatch(r"from (?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}", source.get("text"))
        or source.get("class") != "android.widget.TextView"
        or source.get("content-desc")
        or len(source)
        or card.get("class") != "android.view.View"
        or card.get("clickable") != "true"
        or card.get("text")
        or card.get("content-desc")
        or picture.get("class") != "android.view.View"
        or picture.get("text")
        or title.get("class") != "android.widget.TextView"
        or not title.get("text")
        or title.get("content-desc")
        or any(len(n) or n.get("clickable") == "true" for n in card)
        or any(n.get("scrollable") == "true" for n in (card, picture, title, source))
        or any(n.get("long-clickable") == "true" for n in (picture, title))
        or _rect(picture) != _rect(card)
        or _intersect(_rect(card), _rect(title)) != _rect(title)
        or _rect(title)[3] != _rect(card)[3]
        or _rect(source)[1] != _rect(card)[3]
        or _rect(source)[::2] != _rect(card)[::2]
    ):
        raise _Unsupported("Unrecognized link preview.")
    return (
        Media(
            "link_preview",
            picture.get("content-desc", ""),
            _visibility(card, viewport, overlaps),
            source.get("text"),
            title.get("text"),
            _visibility(title, viewport, overlaps),
        ),
    ), {source, *wrapper.iter()}


def _media_without_body(header, media, quote):
    if not media or any(m.kind not in {"image", "video", "gif"} for m in media):
        raise _Unsupported("Missing body without supported media.")
    if quote is not None and not (
        len(media) == 1
        and media[0].kind == "video"
        and quote.visibility.bounds[1] >= media[0].visibility.bounds[3]
        and quote.visibility.bounds[::2] == media[0].visibility.bounds[::2]
    ):
        raise _Unsupported("Bodyless quote does not follow its outer video.")
    container = header.getparent()
    controls = [
        n
        for n in container
        if n.get("content-desc") in {"Post options", "Explain this post with Grok"}
    ]
    top = min(m.visibility.bounds[1] for m in media)
    if not (
        _rect(header)[3]
        <= top
        <= max((_rect(n)[3] for n in controls), default=_rect(header)[3])
    ):
        raise _Unsupported("Missing body between the header and media.")


def _market_card(container, media, actions, viewport, overlays):
    candidates = [
        wrapper
        for wrapper in container
        if len(wrapper) == 1
        and len(wrapper[0]) == 5
        and len(wrapper[0][0]) == 1
        and not wrapper[0][0].get("content-desc")
        and len(wrapper[0].xpath('./node[@class="android.widget.TextView"]')) == 4
    ]
    if not candidates:
        return None, set()
    wrapper = _one(candidates, "market card")
    card = wrapper[0]
    picture, name, symbol, price, change = card
    rect = _rect(card)
    if (
        len(media) != 1
        or media[0].kind not in {"video", "gif"}
        or len(picture) != 1
        or any(
            n.get("class") != "android.view.View"
            or n.get("text")
            or n.get("content-desc")
            or n.get("scrollable") == "true"
            or n.get("long-clickable") == "true"
            or n.get("enabled") != "true"
            for n in (wrapper, card, picture)
        )
        or wrapper.get("clickable") == "true"
        or card.get("clickable") != "true"
        or any(
            not _plain_annotation(n) or not n.get("text")
            for n in (name, symbol, price, change)
        )
        or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,19}", symbol.get("text"))
        or not re.fullmatch(r"\$[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?", price.get("text"))
        or not re.fullmatch(r"[+−-]?[0-9]+(?:\.[0-9]+)?%", change.get("text"))
        or _rect(wrapper) != rect
        or rect[::2] != media[0].visibility.bounds[::2]
        or wrapper.getprevious() is None
        or _rect(wrapper.getprevious()) != media[0].visibility.bounds
        or rect[1] < media[0].visibility.bounds[3]
        or not actions
        or any(a.visibility.bounds[1] != rect[3] for a in actions)
        or any(_intersect(_rect(n), rect) != _rect(n) for n in card)
        or _rect(picture)[2] > _rect(name)[0]
        or _rect(name)[0] != _rect(symbol)[0]
        or _rect(name)[3] != _rect(symbol)[1]
        or any(_rect(n)[1::2] != _rect(symbol)[1::2] for n in (price, change))
        or any(_rect(x)[2] > _rect(y)[0] for x, y in pairwise((symbol, price, change)))
    ):
        raise _Unsupported("Unrecognized market card.")
    icon = picture[0]
    if (
        len(icon)
        or icon.get("class") != "android.view.View"
        or icon.get("text")
        or icon.get("content-desc") != name.get("text")
        or _intersect(_rect(icon), _rect(picture)) != _rect(icon)
        or _rect(icon)[2] - _rect(icon)[0] != _rect(icon)[3] - _rect(icon)[1]
        or _rect(picture)[2] - _rect(picture)[0]
        != _rect(picture)[3] - _rect(picture)[1]
        or any(
            n.get("enabled") != "true"
            or any(
                n.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable", "focusable")
            )
            for n in (picture, icon)
        )
    ):
        raise _Unsupported("Unrecognized market card icon.")
    return MarketCard(
        *(n.get("text") for n in (name, symbol, price, change)),
        _visibility(card, viewport, overlays),
    ), set(wrapper.iter())


def _media_annotation(container, media, actions):
    native = container.xpath('./node[@text="Made on X"]')
    if native:
        label = _one(native, "native media annotation")
        previous = label.getprevious()
        rect = _rect(label)
        if (
            len(media) != 1
            or media[0].kind != "video"
            or previous is None
            or _rect(previous) != media[0].visibility.bounds
            or label.get("class") != "android.widget.Button"
            or label.get("content-desc")
            or len(label)
            or any(
                label.get(flag) != "true"
                for flag in ("enabled", "clickable", "focusable")
            )
            or any(
                label.get(flag) == "true" for flag in ("long-clickable", "scrollable")
            )
            or rect[0] != media[0].visibility.bounds[0]
            or rect[2] > media[0].visibility.bounds[2]
            or not (rect[1] <= media[0].visibility.bounds[3] < rect[3])
            or media[0].visibility.bounds[3] - rect[1] > (rect[3] - rect[1]) / 2
            or tuple(t.label for t in actions) != ACTION_LABELS
            or any(t.visibility.bounds[1] != rect[3] for t in actions)
        ):
            raise _Unsupported("Unrecognized native media annotation.")
        return (label.get("text"),), {label}
    icons = container.xpath('./node[@content-desc="Made with AI"]')
    if not icons:
        return (), set()
    icon = _one(icons, "AI media annotation")
    label = icon.getnext()
    control = label.getnext() if label is not None else None
    previous = icon.getprevious()
    if (
        not media
        or previous is None
        or label is None
        or control is None
        or icon.get("class") != "android.view.View"
        or icon.get("text")
        or label.get("class") != "android.widget.TextView"
        or label.get("text") != "Made with AI"
        or label.get("content-desc")
        or any(len(n) or n.get("clickable") == "true" for n in (icon, label))
        or control.get("class") != "android.view.View"
        or control.get("clickable") != "true"
        or control.get("text")
        or control.get("content-desc")
        or len(control) != 1
        or control[0].get("class") != "android.widget.TextView"
        or control[0].get("text") != "Create your own with Grok"
        or control[0].get("content-desc")
        or control[0].get("clickable") == "true"
        or len(control[0])
        or any(_rect(previous)[3] != m.visibility.bounds[3] for m in media)
        or min(_rect(icon)[1], _rect(label)[1]) < _rect(previous)[3]
        or _rect(icon)[2] > _rect(label)[0]
        or _rect(icon)[3] != _rect(label)[3]
        or _rect(label)[3] != _rect(control)[1]
        or _intersect(_rect(control), _rect(control[0])) != _rect(control[0])
    ):
        raise _Unsupported("Unrecognized AI media annotation.")
    return (label.get("text"),), {icon, label, *control.iter()}


def _clipped_annotation(node, header, viewport):
    rect, author = _rect(node), _rect(header)
    return (
        node.get("class") == "android.view.View"
        and node.get("clickable") == "true"
        and not len(node)
        and not node.get("text")
        and not node.get("content-desc")
        and node.get("long-clickable") != "true"
        and node.get("scrollable") != "true"
        and node.getprevious() is None
        and rect[1] < viewport[1]
        and rect[1] < author[1] < rect[3] < author[3]
        and rect[0] < author[0] < rect[2] < author[2]
    )


def _paid_partnership(container, media, actions, viewport, overlaps, *, quoted=False):
    icons = container.xpath('./node[@content-desc="Paid partnership"]')
    if not icons:
        return "unknown", None, set()
    icon = _one(icons, "paid partnership icon")
    label = _one(
        container.xpath('./node[@text="Paid partnership"]'), "paid partnership label"
    )
    previous, following = icon.getprevious(), label.getnext()
    icon_rect, label_rect = _rect(icon), _rect(label)
    if (
        previous is None
        or (
            not quoted
            and (
                len(media) != 1
                or media[0].kind != "video"
                or not actions
                or actions[0].label != "Reply"
                or following is None
                or _rect(previous) != media[0].visibility.bounds
                or not previous.xpath('.//*[@content-desc="Video"]')
                or _rect(following) != actions[0].visibility.bounds
                or icon_rect[0] != _rect(previous)[0]
                or label_rect[3] != _rect(following)[1]
            )
        )
        or (
            quoted
            and (
                list(container) != [previous, icon, label]
                or following is not None
                or container.get("clickable") == "true"
                or container.get("class") != "android.view.View"
                or container.get("text")
                or container.get("content-desc")
                or previous.get("clickable") != "true"
                or _rect(previous)[:3] != _rect(container)[:3]
                or icon_rect[0] < _rect(previous)[0]
                or label_rect[3] != _rect(container)[3]
            )
        )
        or icon.getnext() is not label
        or icon.get("class") != "android.view.View"
        or icon.get("text")
        or len(icon)
        or any(
            icon.get(flag) == "true"
            for flag in ("clickable", "long-clickable", "scrollable", "focusable")
        )
        or not _plain_annotation(label)
        or any(not _visibility(n, viewport, overlaps).accessible for n in (icon, label))
        or min(icon_rect[1], label_rect[1]) < _rect(previous)[3]
        or icon_rect[2] > label_rect[0]
        or max(icon_rect[1], label_rect[1]) >= min(icon_rect[3], label_rect[3])
        or icon_rect[3] != label_rect[3]
        or any(
            _intersect(_rect(container), _rect(n)) != _rect(n) for n in (icon, label)
        )
    ):
        raise _Unsupported("Unrecognized paid partnership disclosure.")
    rect = (
        icon_rect[0],
        min(icon_rect[1], label_rect[1]),
        label_rect[2],
        label_rect[3],
    )
    return (
        "paid_partnership",
        Visibility(
            rect,
            _intersect(rect, viewport),
            tuple(area for area in overlaps if _intersect(rect, area)),
        ),
        {icon, label},
    )


def _quote_footer_annotations(wrapper, viewport, overlaps):
    if wrapper.get("clickable") == "true":
        return ()
    _, view, _ = _paid_partnership(wrapper, (), (), viewport, overlaps, quoted=True)
    return (TextSpan("Paid partnership", view),) if view is not None else ()


def _covered_author(header, cover, viewport):
    if cover is None or len(header) not in (2, 3):
        return False
    if len(header) == 3:
        badge = header[1]
        if (
            badge.get("class") != "android.view.View"
            or badge.get("content-desc") != "Verified"
            or badge.get("text")
            or len(badge)
            or any(
                badge.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable", "focusable")
            )
            or not _visibility(badge, viewport).accessible
            or not (
                _rect(header[0])[2] <= _rect(badge)[0] < _rect(badge)[2] <= cover[0]
            )
            or not (
                _rect(header)[1]
                <= _rect(badge)[1]
                < _rect(badge)[3]
                <= _rect(header)[3]
            )
        ):
            return False
    name, age = header[0], header[-1]
    if len(header) == 3 and HANDLE.fullmatch(age.get("text", "")):
        # Android retains the handle text while clipping its bounds at the
        # overlay edge and omitting the covered age. It is not author proof.
        rect, first, last = map(_rect, (header, name, age))
        return (
            all(
                _plain_annotation(n) and _visibility(n, viewport).accessible
                for n in (name, age)
            )
            and bool(name.get("text"))
            and "@" not in name.get("text", "")
            and first[1::2] == rect[1::2]
            and rect[1] <= last[1] < last[3] <= rect[3]
            and viewport[1] < rect[1] < rect[3] < viewport[3]
            and cover[1] <= last[1] < last[3] <= cover[3]
            and rect[0] == first[0]
            and _rect(header[1])[2] <= last[0] < last[2] == cover[0]
            and rect[0] < cover[0] < cover[2] < rect[2]
        )
    if any(
        len(n)
        or n.get("class") != "android.widget.TextView"
        or not n.get("text")
        or n.get("content-desc")
        or n.get("clickable") == "true"
        or "@" in n.get("text", "")
        for n in (name, age)
    ):
        return False
    rect = _rect(header)
    return (
        age.get("text").startswith("· ")
        and viewport[1] < rect[1] < rect[3] < viewport[3]
        and cover[1] <= rect[1] < rect[3] <= cover[3]
        and _rect(name)[2] <= cover[0] < cover[2] <= _rect(age)[0]
        and rect[0] < cover[0] < cover[2] < rect[2]
    )


def _missing_handle_header(header, viewport, overlaps):
    """Recognize the captured name/badge/age row without inferring its author."""
    if (
        len(header) not in (2, 3)
        or not _visibility(header, viewport, overlaps).unobscured
    ):
        return False
    if len(header) == 2:
        name, age = header
        rect, first, last = map(_rect, (header, name, age))
        return (
            all(_plain_annotation(n) and n.get("text") for n in (name, age))
            and not any(
                header.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable", "focusable")
            )
            and all("@" not in n.get("text", "") for n in header)
            and age.get("text").startswith("· ")
            and first[1::2] == rect[1::2]
            and rect[1] <= last[1] < last[3] <= rect[3]
            and first[2] <= last[0]
            and abs(first[0] - rect[0]) <= 4
            and abs(last[2] - rect[2]) <= 4
        )
    name, badge, age = header
    if (
        not all(_plain_annotation(n) and n.get("text") for n in (name, age))
        or any("@" in n.get("text", "") for n in header)
        or not age.get("text").startswith("· ")
        or badge.get("class") != "android.view.View"
        or badge.get("content-desc") != "Verified"
        or badge.get("text")
        or len(badge)
        or any(
            n.get(flag) == "true"
            for n in (header, badge)
            for flag in ("clickable", "long-clickable", "scrollable", "focusable")
        )
        or not all(_visibility(n, viewport, overlaps).accessible for n in header)
    ):
        return False
    rect, first, mark, last = map(_rect, (header, name, badge, age))
    return (
        first[1::2] == last[1::2] == rect[1::2]
        and rect[1] <= mark[1] < mark[3] <= rect[3]
        and first[2] <= mark[0] < mark[2] <= last[0]
        # Captured text bounds protrude slightly beyond the containing row.
        and abs(first[0] - rect[0]) <= 4
        and abs(last[2] - rect[2]) <= 4
    )


def _account_annotation(container, header):
    labels = [
        n
        for n in container
        if n.get("text") in {"Fan account", "Commentary account", "Parody account"}
        and _rect(n)[0] > _rect(header)[0]
    ]
    if not labels:
        return None
    label = _one(labels, "account annotation")
    following = label.getnext()
    children = list(container)
    start, end = children.index(header), children.index(label)
    rect = _rect(label)
    if (
        not _plain_annotation(label)
        or end <= start
        or any(
            n.get("content-desc") not in {"Post options", "Explain this post with Grok"}
            for n in children[start + 1 : end]
        )
        or rect[1] < _rect(header)[3]
        or following is None
        or following.get("class") != "android.widget.TextView"
        or not following.get("text")
        or rect[3] > _rect(following)[1]
        or rect[0] <= _rect(following)[0]
        or rect[2] > _rect(following)[2]
    ):
        raise _Unsupported("Unrecognized account annotation.")
    return label


def _post(header, viewport, overlaps, *, header_cover=None, allow_missing_handle=False):
    container = header.getparent()
    if container.get("clickable") != "true":
        raise _Unsupported("Unrecognized post container.")
    _one(container.xpath('.//*[@resource-id="timeline_post"]'), "outer author header")
    handle = (
        None
        if _covered_author(header, header_cover, viewport)
        or (allow_missing_handle and _missing_handle_header(header, viewport, overlaps))
        else _handle(header.iter(), "outer author")
    )
    header_text = [n.get("text") for n in header if n.get("text")]
    if handle is not None and (
        len(header_text) != 3
        or header_text[1] != handle.get("text")
        or not header_text[2].startswith("· ")
    ):
        raise _Unsupported("Unrecognized author header.")
    known = set(header.iter())
    labels = [n.get("content-desc") for n in header if n.get("content-desc")]
    account_label = _account_annotation(container, header)
    if account_label is not None:
        labels.append(account_label.get("text"))
        known.add(account_label)
    quotes = _desc(container, "Quote")
    card = _clickable(_one(quotes, "quote marker"), container) if quotes else None
    quote, card = (
        _quote_bundle(card, viewport, overlaps) if card is not None else (None, None)
    )
    community_note, note_card = _community_note(container, viewport, overlaps)
    excluded = tuple(n for n in (card, note_card) if n is not None)
    if card is not None:
        known.update(card.iter())
    if note_card is not None:
        known.update(note_card.iter())
    media, media_nodes = _media(container, viewport, overlaps, excluded)
    previews, preview_nodes = _link_preview(container, viewport, overlaps)
    if previews and (media or quote):
        raise _Unsupported("Mixed link preview and post media.")
    media += previews
    known.update(media_nodes)
    known.update(preview_nodes)
    actions, action_nodes = _actions(container, viewport, overlaps, excluded)
    known.update(action_nodes)
    market_card, market_nodes = _market_card(
        container, media, actions, viewport, overlaps
    )
    known.update(market_nodes)
    media_labels, annotation_nodes = _media_annotation(container, media, actions)
    known.update(annotation_nodes)
    advertising, advertising_view, advertising_nodes = _paid_partnership(
        container, media, actions, viewport, overlaps
    )
    known.update(advertising_nodes)
    translation, translation_nodes = _translation(container, header)
    known.update(translation_nodes)
    children = list(container)
    header_index = children.index(header)
    reposted_by = reply_annotation = None
    reply_to, body_nodes, tags = (), [], []
    for index, node in enumerate(children):
        if (
            node is header
            or node is account_label
            or node in translation_nodes
            or node in preview_nodes
            or node in annotation_nodes
            or node in market_nodes
            or node in advertising_nodes
        ):
            continue
        if index < header_index:
            texts = node.xpath('.//*[@text!=""]')
            if texts:
                annotation = _one(texts, "repost annotation")
                raw = annotation.get("text")
                if reposted_by is not None or not raw.endswith(" reposted"):
                    raise _Unsupported("Unrecognized annotation before author.")
                reposted_by = raw
                known.update(node.iter())
            elif _clipped_annotation(node, header, viewport):
                known.add(node)
            else:
                avatars = node.xpath(
                    'self::*[@class="android.widget.ImageView"] | .//*[@class="android.widget.ImageView"]'
                )
                if avatars:
                    _one(avatars, "author avatar")
                elif any(
                    part.get("class") != "android.view.View"
                    or part.get("text")
                    or part.get("content-desc")
                    or any(
                        part.get(flag) == "true"
                        for flag in ("clickable", "long-clickable", "scrollable")
                    )
                    for part in node.iter()
                ):
                    raise _Unsupported("Unrecognized author decoration.")
                known.update(node.iter())
        elif node.get("class") == "android.widget.TextView":
            text = node.get("text", "")
            if (
                not body_nodes
                and text.startswith("Replying to ")
                and node.get("clickable") == "true"
            ):
                if reply_annotation is not None:
                    raise _Unsupported("Multiple reply annotations.")
                reply_annotation = text
                recipients = text.removeprefix("Replying to ").replace("\ufeff", "")
                if not re.fullmatch(
                    r"@[A-Za-z0-9_]{1,15}(?: and @[A-Za-z0-9_]{1,15})*", recipients
                ):
                    raise _Unsupported("Unrecognized reply recipients.")
                reply_to = tuple(HANDLE.findall(recipients))
            elif node.get("clickable") == "true":
                if (
                    not media
                    or not body_nodes
                    or not re.fullmatch(r".+ and \d+ others", text)
                ):
                    raise _Unsupported("Unrecognized media tag annotation.")
                tags.append(text)
            elif text:
                body_nodes.append(node)
            known.add(node)
    body = _one(body_nodes, "outer body") if body_nodes else None
    body_annotations, body_annotation_nodes = _body_annotations(body)
    known.update(body_annotation_nodes)
    if body is None:
        _media_without_body(header, media, quote)
    if translation and (
        body is None
        or any(
            children.index(n) >= children.index(body) or _rect(n)[3] > _rect(body)[1]
            for n in translation_nodes
        )
    ):
        raise _Unsupported("Translation annotation does not precede the body.")
    body_index = children.index(body) if body is not None else header_index
    for node in (*media_nodes, *preview_nodes, *action_nodes, *excluded):
        branch = node
        while branch.getparent() is not container:
            branch = branch.getparent()
        if children.index(branch) <= body_index:
            raise _Unsupported("Media or actions precede the body.")
    for node in container.iter():
        if node in known:
            continue
        desc = node.get("content-desc", "")
        if node.get("text") or desc not in (
            "",
            "Post options",
            "Explain this post with Grok",
            "Unmute",
        ):
            raise _Unsupported("Unrecognized post content.")
    body_view = _visibility(body, viewport, overlaps) if body is not None else None
    body_text = body.get("text") if body is not None else None
    if handle is None:
        if body is None or not (
            body_view.unobscured
            or (
                header_cover is not None
                and body_view.accessible
                and not body_view.clipped
                and body_view.visible_bounds == body_view.bounds
                and body_view.bounds[1] >= _rect(header)[3]
                and all(rect == header_cover for rect in body_view.overlaps)
                and _intersect(body_view.bounds, header_cover) != body_view.bounds
            )
        ):
            raise _Unsupported("Unattributed post has no unobscured body anchor.")
        return PostFragment(
            body_text,
            media,
            _visibility(container, viewport, overlaps),
            body_view,
            actions,
            quote,
            translation,
            body_annotations,
            advertising,
            advertising_view,
            community_note,
            market_card=market_card,
            media_labels=media_labels,
            covered_header_visibility=_visibility(header, viewport, overlaps)
            if header_cover is not None
            else None,
            covered_handle=TextSpan(
                header[-1].get("text"), _visibility(header[-1], viewport, overlaps)
            )
            if header_cover is not None
            and len(header) == 3
            and HANDLE.fullmatch(header[-1].get("text", ""))
            else None,
        )
    identity = [
        handle.get("text").lower(),
        body_text,
        [
            (m.kind, m.description, m.source_label, m.preview_text)
            if m.kind == "link_preview" or body is None
            else (m.kind, m.description)
            for m in media
        ],
    ]
    if translation:
        identity.append(translation)
    if body is None and any(m.source_prefix for m in media):
        identity.append(["source_prefixes", [m.source_prefix for m in media]])
    if body_annotations:
        identity.append(["body_annotations", body_annotations])
    if quote:
        quoted_identity = [
            quote.author.lower(),
            quote.body,
            [
                (m.kind, m.description, m.preview_text)
                if m.kind == "preview"
                else (m.kind, m.description)
                for m in quote.media
            ],
        ]
        if quote.translation:
            quoted_identity.append(quote.translation)
        if quote.body_annotations:
            quoted_identity.append(
                ["body_annotations", [v.text for v in quote.body_annotations]]
            )
        identity.append(quoted_identity)
    key = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return Post(
        author=handle.get("text"),
        display_name=header_text[0],
        body=body_text,
        body_complete=body is not None and bool(_body_complete(body_text, body_view)),
        age=header_text[2],
        content_key=key,
        visibility=_visibility(container, viewport, overlaps),
        header_visibility=_visibility(header, viewport, overlaps),
        author_visibility=_visibility(handle, viewport, overlaps),
        body_visibility=body_view,
        media=media,
        quoted_post=quote,
        reposted_by=reposted_by,
        reply_annotation=reply_annotation,
        reply_to=reply_to,
        labels=tuple(labels),
        media_tags=tuple(tags),
        actions=actions,
        translation=translation,
        media_labels=media_labels,
        body_annotations=body_annotations,
        market_card=market_card,
        advertising=advertising,
        advertising_visibility=advertising_view,
        community_note=community_note,
    )


def _scroll_area(header, viewport, overlays):
    container = header.getparent()
    if container.get("clickable") != "true":
        raise _Unsupported("Unrecognized scrolling container.")
    _one(container.xpath('.//*[@resource-id="timeline_post"]'), "outer author header")
    return _scroll_container(container, viewport, overlays)


def _scroll_container(container, viewport, overlays):
    exclusions = []
    for node in container.iterdescendants():
        if (
            node.get("class") == "android.widget.ImageView"
            or node.get("resource-id") == "timeline_post"
            or node.get("content-desc") in {"Video", "GIF"}
            or node.get("clickable") == "true"
            or node.get("long-clickable") == "true"
            or node.get("scrollable") == "true"
        ):
            exclusions.append(_rect(node))
    return ScrollArea(
        _visibility(container, viewport, overlays), tuple(dict.fromkeys(exclusions))
    )


def _clipped_scroll_area(container, viewport, overlays):
    if (
        container.get("clickable") != "true"
        or _rect(container)[1] >= viewport[1]
        or container.xpath('.//*[@resource-id="timeline_post"]')
    ):
        raise _Unsupported("Not a clipped post container.")
    actions, _ = _actions(container, viewport, overlays, ())
    if tuple(action.label for action in actions) != ACTION_LABELS:
        raise _Unsupported("Incomplete clipped post actions.")
    targets = [
        _clickable(_one(_desc(container, label), label), container)
        for label in ACTION_LABELS
    ]
    if any(target.getparent() is not container for target in targets):
        raise _Unsupported("Clipped actions are not in the outer post.")
    rects = [_rect(target) for target in targets]
    if len({r[1] for r in rects}) != 1 or any(a[2] > b[0] for a, b in pairwise(rects)):
        raise _Unsupported("Unrecognized clipped action row.")
    return _scroll_container(container, viewport, overlays)


def _clipped_preview_texts(container, actions, viewport, overlays):
    if len(container) != 7 or tuple(t.label for t in actions) != ACTION_LABELS:
        return ()
    wrapper = container[0]
    footer = _quote_footer_annotations(wrapper, viewport, overlays)
    if len(wrapper) != (3 if footer else 1) or len(wrapper[0]) != 1:
        return ()
    card, preview = wrapper[0], wrapper[0][0]
    picture = preview[0] if len(preview) == 3 else None
    texts = list(preview)[1:] if picture is not None else list(preview)
    if (
        len(texts) not in (1, 2)
        or (
            picture is not None
            and (
                len(picture)
                or picture.get("class") != "android.view.View"
                or picture.get("text")
                or picture.get("content-desc")
                or any(
                    picture.get(flag) == "true"
                    for flag in (
                        "clickable",
                        "long-clickable",
                        "scrollable",
                        "focusable",
                    )
                )
                or _intersect(_rect(picture), _rect(preview)) != _rect(picture)
            )
        )
        or not (_rect(card)[1] < viewport[1] < _rect(preview)[3] < viewport[3])
        or (not footer and _rect(wrapper) != _rect(card))
        or _rect(card)[::2] != _rect(preview)[::2]
        or _rect(card)[3] != _rect(preview)[3]
        or _rect(card)[1] > _rect(preview)[1]
        or wrapper.get("clickable") == "true"
        or card.get("clickable") != "true"
        or preview.get("clickable") != "true"
        or any(
            n.get("class") != "android.view.View"
            or n.get("text")
            or n.get("content-desc")
            or n.get("scrollable") == "true"
            or n.get("long-clickable") == "true"
            for n in (wrapper, card, preview)
        )
        or any(
            not _plain_annotation(n)
            or not n.get("text")
            or _intersect(_rect(n), _rect(preview)) != _rect(n)
            for n in texts
        )
        or any(_rect(a)[3] >= _rect(b)[1] for a, b in pairwise(preview))
        or any(t.visibility.bounds[1] != _rect(wrapper)[3] for t in actions)
    ):
        return ()
    return tuple(
        TextSpan(n.get("text"), _visibility(n, viewport, overlays)) for n in texts
    ), footer


def _clipped_quote_marker(card, viewport):
    if len(card) != 3:
        return None
    marker = card[0]
    if (
        marker.get("content-desc") == "Quote"
        and marker.get("class") == "android.view.View"
        and not marker.get("text")
        and not len(marker)
        and marker.get("clickable") != "true"
        and marker.get("long-clickable") != "true"
        and marker.get("scrollable") != "true"
        and _rect(marker)[1] < viewport[1] < _rect(marker)[3]
        and _rect(marker)[3] <= _rect(card[1])[1]
        and _intersect(_rect(marker), _rect(card)) == _rect(marker)
    ):
        return marker
    return None


def _clipped_quoted_body(container, media, media_nodes, actions, viewport, overlays):
    if len(container) != 7 or tuple(t.label for t in actions) != ACTION_LABELS:
        return None
    wrapper = container[0]
    footer = _quote_footer_annotations(wrapper, viewport, overlays)
    if len(wrapper) != (3 if footer else 1):
        return None
    card = wrapper[0]
    marker = _clipped_quote_marker(card, viewport)
    if len(card) != (3 if marker is not None else 2):
        return None
    body, video = list(card)[-2:]
    _, annotation_nodes = _body_annotations(body)
    if not media:
        media, media_nodes = _article_preview(card, body, viewport, overlays)
    if len(media) != 1 or media[0].kind not in {"video", "preview"}:
        return None
    if (
        not _plain_annotation(body, allowed_children=annotation_nodes)
        or not body.get("text")
        or not (viewport[1] < _rect(body)[3] <= _rect(video)[1])
        or (marker is None and _rect(body)[1] >= viewport[1])
        or (not footer and _rect(wrapper) != _rect(card))
        or wrapper.get("clickable") == "true"
        or card.get("clickable") != "true"
        or any(
            n.get("text")
            or n.get("content-desc")
            or n.get("class") != "android.view.View"
            or n.get("scrollable") == "true"
            or n.get("long-clickable") == "true"
            for n in (wrapper, card)
        )
        or _intersect(_rect(body), _rect(card)) != _rect(body)
        or _intersect(_rect(video), _rect(card)) != _rect(video)
        or media[0].visibility.bounds != _rect(video)
        or any(t.visibility.bounds[1] != _rect(wrapper)[3] for t in actions)
        or any(
            n is not body
            and n is not marker
            and n not in annotation_nodes
            and n not in media_nodes
            and (n.get("text") or n.get("content-desc", "") not in ("", "Unmute"))
            for n in card.iter()
        )
    ):
        return None
    return (
        TextSpan(body.get("text"), _visibility(body, viewport, overlays)),
        media,
        footer,
        tuple(
            TextSpan(n.get("content-desc"), _visibility(n, viewport, overlays))
            for n in annotation_nodes
        ),
    )


def _header_controls_clipped(container, body, viewport):
    prefix = list(container)[: list(container).index(body)]
    if len(prefix) != 3:
        return False
    avatar, grok, options = prefix
    return (
        avatar.get("class") == "android.widget.ImageView"
        and grok.get("class") == "android.widget.ImageView"
        and grok.get("content-desc") == "Explain this post with Grok"
        and options.get("class") == "android.widget.Button"
        and options.get("content-desc") == "Post options"
        and all(
            not len(n)
            and not n.get("text")
            and n.get("clickable") == "true"
            and n.get("enabled") == "true"
            for n in prefix
        )
        and _rect(grok)[1] == _rect(options)[1] <= _rect(container)[1]
        and _rect(grok)[1] < viewport[1] < _rect(grok)[3] == _rect(body)[1]
        and _rect(grok)[2] == _rect(options)[0]
        and _rect(options)[2] == _rect(container)[2]
        and _rect(avatar)[1] < viewport[1]
        and _rect(avatar)[2] < _rect(body)[0] < _rect(grok)[0]
    )


def _fragment(container, viewport, overlays, *, collapsed=False):
    if (
        container.get("clickable") != "true"
        or _rect(container)[1] >= viewport[1]
        or container.xpath('.//*[@resource-id="timeline_post"]')
    ):
        raise _Unsupported("Not a clipped post container.")
    quotes = _desc(container, "Quote")
    card = _clickable(_one(quotes, "quote marker"), container) if quotes else None
    if (
        collapsed
        and card is not None
        and _clipped_quote_marker(card, viewport) is not None
    ):
        # The marker can outlive its author row. The tail parser below must
        # recognize the complete structure; it never supplies an author.
        card = None
    quote, card = (
        _quote_bundle(card, viewport, overlays) if card is not None else (None, None)
    )
    community_note, note_card = _community_note(container, viewport, overlays)
    excluded = tuple(n for n in (card, note_card) if n is not None)
    media, media_nodes = _media(container, viewport, overlays, excluded)
    actions, action_nodes = _actions(container, viewport, overlays, excluded)
    market_card, market_nodes = _market_card(
        container, media, actions, viewport, overlays
    )
    media_labels, annotation_nodes = _media_annotation(container, media, actions)
    advertising, advertising_view, advertising_nodes = _paid_partnership(
        container, media, actions, viewport, overlays
    )
    translation, translation_nodes = _translation(
        container, clipped_viewport=viewport if collapsed else None
    )
    bodies = [
        n
        for n in container.xpath('./node[@class="android.widget.TextView"]')
        if n not in advertising_nodes
        and n not in translation_nodes
        and n not in annotation_nodes
    ]
    body = _one(bodies, "clipped post body") if bodies else None
    if body is not None and (
        not body.get("text")
        or body.get("clickable") == "true"
        # Collapsed Home can lose a header while its body starts one pixel
        # below the system inset. Expanded toolbar clipping is separate.
        or (
            _rect(body)[1] >= viewport[1]
            and not (
                collapsed
                and (
                    _rect(body)[1] <= viewport[1] + 2
                    or _header_controls_clipped(container, body, viewport)
                    or (
                        translation_nodes
                        and min(_rect(n)[1] for n in translation_nodes) < viewport[1]
                        and max(_rect(n)[3] for n in translation_nodes)
                        <= _rect(body)[1]
                    )
                )
            )
        )
    ):
        raise _Unsupported("Unrecognized clipped post body.")
    body_annotations, body_annotation_nodes = _body_annotations(body)
    if collapsed and body is None and quote is None and community_note is None:
        quoted_content = _clipped_quoted_body(
            container, media, media_nodes, actions, viewport, overlays
        )
        if quoted_content is not None:
            quoted_body, media, footer, annotations = quoted_content
            return PostFragment(
                None,
                media,
                _visibility(container, viewport, overlays),
                None,
                actions,
                quoted_body=quoted_body,
                quoted_footer_annotations=footer,
                quoted_body_annotations=annotations,
            )
    if (
        collapsed
        and body is None
        and not media
        and quote is None
        and community_note is None
    ):
        preview_texts = _clipped_preview_texts(container, actions, viewport, overlays)
        if preview_texts:
            preview_texts, footer = preview_texts
            return PostFragment(
                None,
                (),
                _visibility(container, viewport, overlays),
                None,
                actions,
                preview_texts=preview_texts,
                quoted_footer_annotations=footer,
            )
    if translation_nodes and (
        body is None
        or any(
            list(container).index(n) >= list(container).index(body)
            or _rect(n)[3] > _rect(body)[1]
            for n in translation_nodes
        )
    ):
        raise _Unsupported("Clipped translation does not precede the body.")
    if (
        collapsed
        and body is None
        and not media
        and quote is None
        and community_note is None
        and len(container) == len(ACTION_LABELS)
        and tuple(action.label for action in actions) == ACTION_LABELS
        and all(
            n in action_nodes or not (n.get("text") or n.get("content-desc"))
            for n in container.iter()
        )
    ):
        _clipped_scroll_area(container, viewport, overlays)
        return PostFragment(
            None, (), _visibility(container, viewport, overlays), None, actions
        )
    if (
        body is not None
        and len(container) == 1
        and not len(body)
        and not body.get("content-desc")
        and _rect(body)[3] >= viewport[3]
        and _visibility(body, viewport, overlays).accessible
    ):
        return PostFragment(
            body.get("text"),
            (),
            _visibility(container, viewport, overlays),
            _visibility(body, viewport, overlays),
        )
    if (
        (not quote and len(media) != 1 and not (body is not None and not media))
        or len(media) > 1
        or any(
            m.kind not in {"video", "gif"}
            and not (
                m.kind == "image"
                and body is not None
                and quote is None
                and viewport[1] < _rect(body)[3] <= m.visibility.bounds[1]
            )
            for m in media
        )
    ):
        raise _Unsupported("Unrecognized clipped post media.")
    # Collapsed Home may clip the body in the gap before a video. Retain only
    # unattributed content here; navigation must prove the loss and video motion.
    if (
        body is None
        and media
        and media[0].visibility.bounds[1] >= viewport[1]
        and not collapsed
    ):
        raise _Unsupported("Missing body above unclipped media.")
    if (
        body is None
        and quote is None
        and not any(m.visibility.visible_bounds for m in media)
    ):
        raise _Unsupported("Clipped post has no visible content.")
    if (
        tuple(action.label for action in actions) != ACTION_LABELS
        and not (
            (quote or community_note)
            and not actions
            and _rect(container)[3] >= viewport[3]
        )
        and not _covered_bookmark_row(container, actions, viewport, overlays)
    ):
        raise _Unsupported("Incomplete clipped post actions.")
    if not media and quote is None:
        if (
            body is None
            or len(body)
            or body.get("content-desc")
            or body.get("long-clickable") == "true"
            or not _visibility(body, viewport, overlays).accessible
        ):
            raise _Unsupported("Unrecognized clipped text footer.")
        _clipped_scroll_area(container, viewport, overlays)
    known = {
        body,
        *body_annotation_nodes,
        *media_nodes,
        *action_nodes,
        *advertising_nodes,
        *translation_nodes,
        *annotation_nodes,
        *market_nodes,
    }
    if card is not None:
        known.update(card.iter())
    if note_card is not None:
        known.update(note_card.iter())
    if body is None and media and len(container) > 1:
        avatar = container[0]
        rect, video = _rect(avatar), media[0].visibility.bounds
        if (
            len(media) == 1
            and media[0].kind == "video"
            and _rect(container[1]) == video
            and avatar.get("class") == "android.widget.ImageView"
            and not len(avatar)
            and not avatar.get("text")
            and avatar.get("clickable") == "true"
            and avatar.get("long-clickable") == "true"
            and avatar.get("enabled") == "true"
            and avatar.get("visible-to-user") != "false"
            and avatar.get("scrollable") != "true"
            and _rect(container)[0] <= rect[0] < rect[2] <= video[0]
            and rect[2] - rect[0] == rect[3] - rect[1]
            and rect[1] < viewport[1] < rect[3]
            and rect[1] <= video[1] <= rect[3]
        ):
            known.add(avatar)
    for child in container:
        if child is body or body is None:
            break
        if child in translation_nodes:
            continue
        if child.get("text") or not (
            child.get("class") == "android.widget.ImageView"
            or (
                child.get("class") == "android.widget.Button"
                and child.get("content-desc") == "Post options"
                and _rect(child)[1] < viewport[1]
            )
        ):
            raise _Unsupported("Unrecognized clipped post prefix.")
        known.add(child)
    for node in container.iter():
        if node not in known and (
            node.get("text") or node.get("content-desc", "") not in ("", "Unmute")
        ):
            raise _Unsupported("Unrecognized clipped post content.")
    return PostFragment(
        body.get("text") if body is not None else None,
        media,
        _visibility(container, viewport, overlays),
        _visibility(body, viewport, overlays) if body is not None else None,
        actions,
        quote,
        translation=translation,
        body_annotations=body_annotations,
        market_card=market_card,
        advertising=advertising,
        advertising_visibility=advertising_view,
        community_note=community_note,
        media_labels=media_labels,
    )


def _collapsed_home(scope, landing, area, system_bars):
    for label in (
        "Home",
        "Explore",
        "Grok",
        "Show navigation drawer",
        "Scroll to top",
    ):
        if _desc(landing, label):
            raise _Unsupported("Incomplete expanded Home controls.")
    outer = _one(scope.xpath('./node[@scrollable="true"]'), "Home scroll surface")
    _one(outer.xpath('./node[@scrollable="true"]'), "Home post list")
    bar = _one(system_bars, "collapsed Home status bar")
    if bar[:3] != area[:3] or bar[3] > area[3] * 0.1:
        raise _Unsupported("Unrecognized collapsed Home system inset.")
    top = bar[3]
    if _desc(scope, "For you") or _desc(scope, "Following"):
        tab, _, row = _tabs(scope, ("For you", "Following"), area[3])
        if tab not in ("For you", "Following") or _rect(row)[1] >= bar[3]:
            raise _Unsupported("Incomplete expanded Home controls.")
        top = max(top, *(_rect(node)[3] for node in row.iter()))
    composers = _desc(scope, "Post")
    if not composers:
        raise _MissingHomeComposer("Missing collapsed Home composer.")
    composer = _one(composers, "collapsed Home composer")
    target = _clickable(composer, scope)
    if not _visibility(target, area, system_bars).unobscured:
        raise _Unsupported("Collapsed Home composer is obscured.")
    # The gesture navigation bar has no XML node in this capture. Conservatively
    # exclude the entire strip below the floating composer instead of guessing it.
    bottom = _rect(target)[3]
    if bottom <= bar[3] or bottom >= area[3]:
        raise _Unsupported("Missing collapsed Home bottom inset.")
    return top, bottom


def _read(root, area):
    windows = [n for n in root if n.get("package") == PACKAGE]
    window = _one(windows, "X window")
    if any(n.get("package") != PACKAGE for n in window.iter()):
        raise _Unsupported("Unexpected package inside X window.")
    keyboard, system_bars = [], []
    for other in root:
        if other is window:
            continue
        if other.get("package") == "com.google.android.inputmethod.latin":
            keyboard.append(_rect(other))
        elif other.get("package") != "com.android.systemui":
            raise _Unsupported("Unrecognized external window.")
        elif _rect(other)[1] != 0:
            raise _Unsupported("Unrecognized system overlay.")
        else:
            system_bars.append(_rect(other))
    external = (*keyboard, *system_bars)
    if _desc(window, "Close sheet"):
        if _desc(window, "Close navigation menu"):
            raise _Unsupported("Conflicting X overlays.")
        return _post_options(window, area, external)
    landing = _one(window.xpath('.//*[@resource-id="MainLanding"]'), "MainLanding")
    if _desc(landing, "Close navigation menu"):
        return _drawer(landing, area, external)
    markers = [n for n in landing.iter() if n.get("resource-id") in PRIMARY]
    if markers:
        if _desc(landing, "Explore Settings"):
            raise _Unsupported("Conflicting Explore and primary screen markers.")
        scope = _one(markers, "primary screen marker")
        kind = PRIMARY[scope.get("resource-id")]
    elif _desc(landing, "Explore Settings"):
        scope, kind = landing, "explore"
    else:
        raise _Unsupported("Unrecognized X screen.")
    if keyboard and kind != "search_input":
        raise _Unsupported("Unexpected keyboard over X screen.")
    controls, overlays = [], list(external)
    tab = query = active = profile = None
    collapsed = kind == "home" and not _desc(landing, "Home")
    if kind == "search_input":
        field = _one(
            scope.xpath('.//*[@class="android.widget.EditText"]'), "query field"
        )
        if field.get("focused") != "true":
            raise _Unsupported("Query field is not focused.")
        if not _visibility(field, area, external).unobscured:
            raise _Unsupported("Query field is obscured.")
        query = field.get("text", "")
        bar = _header_bar(field, scope)
        bottom = _one(keyboard, "keyboard window")[1]
        clear = _desc(field, "Clear search")
        if len(clear) > 1:
            raise _Unsupported("Multiple Clear search controls.")
        exclusions = (*external, *(_rect(_clickable(n, field)) for n in clear))
        controls.append(_target(field, "Query", scope, area, exclusions))
        top = _rect(bar)[3]
    elif collapsed:
        top, bottom = _collapsed_home(scope, landing, area, system_bars)
        overlays.append((area[0], bottom, area[2], area[3]))
    else:
        navigation = _navigation(landing)
        bottom = _rect(navigation)[1]
        overlays.append(_rect(navigation))
        for label in ("Home", "Explore"):
            node = _one(_desc(navigation, label), label)
            wrapper = node.getparent()
            controls.append(
                Target(
                    label,
                    _visibility(wrapper, area, external),
                    selected=wrapper.get("selected") == "true",
                )
            )
        if kind == "detail":
            field = _one(
                scope.xpath('.//*[@resource-id="post-detail-reply-text-field"]'),
                "reply composer",
            )
            composer = field.getparent()
            overlays.append(_rect(composer))
            bottom = _rect(composer)[1]
            back = _one(_desc(scope, "Back"), "detail Back")
            top = _rect(_header_bar(back, scope))[3]
        else:
            required = {
                "home": ("For you", "Following"),
                "profile": ("Posts", "Replies"),
                "search_results": ("Top", "Latest"),
                "explore": ("Explore", "Trending"),
            }[kind]
            tab, selected, row = _tabs(scope, required, bottom)
            evidence = (
                _one(
                    selected.xpath(".//*[@text=$label]", label=tab),
                    "selected Home label",
                )
                if kind == "home"
                else selected
            )
            if kind == "home" and tab not in required:
                raise _Unsupported("Unsupported Home timeline.")
            if kind == "search_results" and tab not in required:
                raise _Unsupported("Unsupported search result tab.")
            if not _visibility(evidence, area, external).unobscured:
                if (
                    kind != "home"
                    or len(system_bars) != 1
                    or system_bars[0][:3] != area[:3]
                    or system_bars[0][3] > area[3] * 0.1
                    or _rect(row)[1] >= system_bars[0][3]
                    or not _visibility(evidence, area).unobscured
                    or _desc(scope, "Show navigation drawer")
                ):
                    raise _Unsupported("Selected tab is obscured.")
                collapsed, tab = True, None
            top = _rect(selected)[3]
            if collapsed:
                top = max(system_bars[0][3], *(_rect(n)[3] for n in row.iter()))
            for wrapper in row:
                labels = wrapper.xpath('./node[@content-desc!=""]')
                if len(labels) == 1 and not collapsed:
                    controls.append(
                        Target(
                            labels[0].get("content-desc"),
                            _visibility(wrapper, area, external),
                            selected=wrapper is selected,
                        )
                    )
            if kind == "home":
                drawers = _desc(scope, "Show navigation drawer")
                partially_hidden = _rect(row)[1] <= max(
                    (r[3] for r in system_bars), default=0
                )
                if drawers or not partially_hidden:
                    node = _one(drawers, "drawer launcher")
                    controls.append(
                        _target(node, "Show navigation drawer", scope, area, external)
                    )
            if kind in ("search_results", "explore"):
                search = _one(_desc(scope, "Search"), "Search header")
                target = _clickable(search, scope)
                query_node = _one(target.xpath('.//*[@text!=""]'), "query header text")
                query = query_node.get("text") if kind == "search_results" else None
                if (
                    scope.xpath('.//*[@class="android.widget.EditText"]')
                    or _rect(target)[3] > top
                    or not _visibility(query_node, area, external).unobscured
                ):
                    raise _Unsupported("Invalid noneditable query header.")
            if kind == "profile":
                profile, active = _profile_identity(scope, area, top, external)
    for composer in _desc(scope, "Post"):
        overlays.append(_rect(_clickable(composer, scope)))
    header_cover = None
    if kind == "home":
        new_posts = _desc(scope, "New posts")
        if new_posts or scope.xpath('.//*[@resource-id="ntp"]'):
            target = _one(scope.xpath('.//*[@resource-id="ntp"]'), "New posts target")
            node = _one(
                target.xpath('.//*[@content-desc="New posts" or @text="New posts"]'),
                "New posts label",
            )
            if _clickable(node, scope) is not target:
                raise _Unsupported("Unrecognized New posts target.")
            overlays.append(_rect(target))
            header_cover = _rect(target)
    viewport = _intersect((area[0], top, area[2], bottom), area)
    if viewport is None:
        raise _Unsupported("No usable content viewport.")
    if any(_intersect(viewport, rect) for rect in system_bars):
        raise _Unsupported("System overlay covers X content.")
    posts, rejected, scroll_areas, fragments = [], [], [], []
    if kind in ("home", "search_results", "profile"):
        for header in scope.xpath('.//*[@resource-id="timeline_post"]'):
            try:
                post = _post(
                    header,
                    viewport,
                    tuple(overlays),
                    header_cover=header_cover if not posts and not fragments else None,
                    # Fragments precede attributed posts in ordered alignment.
                    # A missing handle later in the list must remain rejected.
                    allow_missing_handle=(
                        kind == "home" and not posts and not fragments and not rejected
                    ),
                )
                if isinstance(post, PostFragment):
                    fragments.append(post)
                else:
                    posts.append(post)
            except _Unsupported as exc:
                rejected.append(RejectedPost(bounds(header.getparent()), str(exc)))
            if kind == "home":
                try:
                    scroll_areas.append(_scroll_area(header, viewport, tuple(overlays)))
                except _Unsupported:
                    pass
    if kind == "home":
        containers = scope.xpath(
            './node[@scrollable="true"]/node[@scrollable="true"]/node'
        )
        containers = [node for node in containers if _intersect(_rect(node), viewport)]
        if (
            containers
            and containers[0].get("clickable") == "true"
            and _rect(containers[0])[1] < viewport[1] < _rect(containers[0])[3]
            and not containers[0].xpath('.//*[@resource-id="timeline_post"]')
        ):
            container = containers[0]
            try:
                scroll_areas.append(
                    _clipped_scroll_area(container, viewport, tuple(overlays))
                )
            except _Unsupported:
                pass
            try:
                fragment = _fragment(
                    container, viewport, tuple(overlays), collapsed=collapsed
                )
                scroll_area = _scroll_container(container, viewport, tuple(overlays))
                fragments.insert(0, fragment)
                if scroll_area not in scroll_areas:
                    scroll_areas.append(scroll_area)
            except _Unsupported as exc:
                rejected.append(RejectedPost(bounds(container), str(exc)))
    empty = (
        kind == "home"
        and tab == "Following"
        and bool(scope.xpath('.//*[@text="Welcome to your timeline!"]'))
    )
    if empty and (posts or rejected):
        raise _Unsupported("Empty timeline message conflicts with post candidates.")
    return Screen(
        kind,
        reason="Main post unavailable: the inspected detail layout omits its author and body."
        if kind == "detail"
        else None,
        tab=tab,
        query=query,
        active_account=active,
        profile_handle=profile,
        content_viewport=viewport,
        overlaps=tuple(overlays),
        controls=tuple(controls),
        posts=tuple(posts),
        rejected_posts=tuple(rejected),
        empty=empty,
        scroll_areas=tuple(scroll_areas),
        collapsed=collapsed,
        fragments=tuple(fragments),
    )


def read_screen(xml, size):
    """Return immutable snapshot evidence; unsupported structures carry a reason.

    XML window packages do not establish which app is foreground. The
    Phone-backed adapter must check that separately and re-read before acting.
    """
    try:
        width, height = size
        if width <= 0 or height <= 0:
            raise _Unsupported("Invalid screen size.")
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml, parser)
        if root.tag != "hierarchy" or root.getroottree().docinfo.doctype:
            raise _Unsupported("Expected a hierarchy without a document type.")
        return _read(root, (0, 0, width, height))
    except _MissingHomeComposer as exc:
        return Screen("unsupported", reason=str(exc), waiting_for="home_composer")
    except (etree.XMLSyntaxError, _Unsupported) as exc:
        return Screen("unsupported", reason=str(exc))
