"""Pure interpretation of the inspected English X hierarchies.

The caller must verify the foreground app through Phone before using this data.
Targets and content keys are snapshot evidence, not permission to engage.
"""

import hashlib
import json
import re
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import TYPE_CHECKING

from lxml import etree

from taktik.core.shared.phone_interaction import TextField
from taktik.core.shared.ui.geometry import bounds

if TYPE_CHECKING:
    from .inspection import Detail, Gallery, Profile

PACKAGE = "com.twitter.android"
HANDLE = re.compile(r"@[A-Za-z0-9_]{1,15}", re.ASCII)
PRIMARY = {
    "PostDetail": "detail",
    "UserProfileScreen": "profile",
    "SearchQuery": "search_input",
    "Search": "search_results",
    "scaffold_home_tabbed": "home",
    "MediaGallery": "media",
}
ACTION_LABELS = ("Reply", "Repost", "Like", "Impressions", "Bookmark", "Share")
VERIFICATION_LABELS = frozenset(
    {"Verified", "Verified Business", "Verified Governmental Account"}
)
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
    source_visibility: Visibility | None = None
    source_content: tuple[Visibility, ...] = ()


@dataclass(frozen=True)
class ScrollArea:
    visibility: Visibility
    exclusions: tuple[Rect, ...]


@dataclass(frozen=True)
class QuotedPost:
    author: str | None
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
    translation_visibility: Visibility | None = None
    reply_annotation: str | None = None
    reply_to: tuple[str, ...] = ()
    reply_visibility: Visibility | None = None

    @property
    def observable(self):
        return (
            self.author is not None
            and (self.nested_quote is None or self.nested_quote.observable)
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
    adjacent_assets: tuple["TextSpan", ...] = ()


@dataclass(frozen=True)
class SportsCard:
    teams: tuple[str, str]
    status: str
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
    sports_card: SportsCard | None = None
    targets: tuple[Target, ...] = ()

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
    quoted_translation: TextSpan | None = None
    sports_card: SportsCard | None = None


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
    # Native timeline text is movement evidence, never attributed post content.
    scroll_anchors: tuple[TextSpan, ...] = ()
    navigation_areas: tuple[ScrollArea, ...] = ()
    query_field: TextField | None = None
    profile: "Profile | None" = None
    detail: "Detail | None" = None
    gallery: "Gallery | None" = None

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


def _handle(nodes, description, *, display_name=None):
    candidates = [
        node
        for node in nodes
        if node is not display_name and node.get("text", "").startswith("@")
    ]
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
                or account[2].get("content-desc") not in VERIFICATION_LABELS
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


def _gif_description_control(node):
    wrapper = node.getparent()
    control = _one(_desc(wrapper, "Image description"), "GIF description control")
    if (
        not node.get("content-desc", "").removeprefix("GIF: ").strip()
        or node.get("class") != "android.view.View"
        or node.get("text")
        or len(node)
        or node.get("enabled") != "true"
        or any(
            node.get(flag) == "true"
            for flag in ("clickable", "long-clickable", "focusable", "scrollable")
        )
        or wrapper.get("class") != "android.view.View"
        or wrapper.get("clickable") != "true"
        or wrapper.get("text")
        or wrapper.get("content-desc")
        or control.getparent() is not wrapper
        or control.get("class") != "android.widget.ImageView"
        or control.get("text")
        or len(control)
        or any(
            control.get(flag) != "true"
            for flag in ("clickable", "focusable", "enabled")
        )
        or any(control.get(flag) == "true" for flag in ("long-clickable", "scrollable"))
        or _rect(node)[:3] != _rect(wrapper)[:3]
        or _rect(node)[3] < _rect(wrapper)[3]
        or _intersect(_rect(control), _rect(node)) != _rect(control)
        or _rect(control)[3] not in {_rect(wrapper)[3], _rect(node)[3]}
    ):
        raise _Unsupported("Unrecognized GIF description control.")
    return control


def _native_video_overlays(video):
    root = video.getparent()
    if (
        len(root) != 3
        or root[0] is not video
        or len(root[2]) != 1
        or root[2][0].get("content-desc") != "play"
    ):
        return set()
    _, picture, overlay = root
    glyph = overlay[0]
    if (
        _rect(video) != _rect(root)
        or _rect(picture) != _rect(root)
        or _intersect(_rect(root), _rect(overlay)) != _rect(overlay)
        or _intersect(_rect(overlay), _rect(glyph)) != _rect(glyph)
        or picture.get("content-desc")
        or overlay.get("content-desc")
        or len(picture)
        or len(glyph)
        or any(
            n.get("class") != "android.view.View"
            or n.get("text")
            or any(
                n.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable")
            )
            for n in (video, picture, overlay, glyph)
        )
    ):
        raise _Unsupported("Unrecognized native video play overlay.")
    return {picture, overlay, glyph}


def _media(root, viewport, overlaps, excluded=()):
    result, covered = [], set()
    for node in root.iter():
        if any(node is skip or skip in node.iterancestors() for skip in excluded):
            continue
        desc = node.get("content-desc", "")
        described_gif = desc.startswith("GIF: ")
        if (
            desc in {"Video", "GIF", "Image"}
            or desc.startswith("Image:")
            or described_gif
        ):
            if described_gif:
                covered.add(_gif_description_control(node))
            if desc == "Video":
                covered.update(_native_video_overlays(node))
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
                    "gif"
                    if described_gif
                    else {"Video": "video", "GIF": "gif"}.get(desc, "image"),
                    desc,
                    _visibility(node, viewport, (*overlaps, *controls)),
                    source_label,
                    source_prefix=source_prefix,
                    source_visibility=(
                        _visibility(credit, viewport, overlaps)
                        if credit is not None
                        else None
                    ),
                    source_content=tuple(
                        _visibility(child, viewport, overlaps) for child in credit
                    )
                    if credit is not None
                    else (),
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
        n
        for n in card
        if n.get("content-desc", "").endswith(("more media item", "more media items"))
    ]
    if not previews:
        return (), set()
    preview = _one(previews, "compact quote preview")
    count = re.fullmatch(
        r"([1-9][0-9]*) more media (item|items)", preview.get("content-desc", "")
    )
    # Offscreen bottom-clipped wrappers can precede their native count glyph.
    pending_count = (
        not len(preview)
        and _rect(preview)[1] >= viewport[3]
        and _rect(preview)[3] == _rect(card)[3]
        and _intersect(_rect(preview), _rect(card)) == _rect(preview)
    )
    if (
        body is None
        or count is None
        or count[2] != ("item" if count[1] == "1" else "items")
        or preview.get("class") != "android.view.View"
        or preview.get("clickable") == "true"
        or preview.get("text")
        or (
            not pending_count
            and (
                len(preview) != 1
                or len(preview[0])
                or preview[0].get("class") != "android.widget.TextView"
                or preview[0].get("text") != f"+{count[1]}"
                or preview[0].get("content-desc")
                or preview[0].get("clickable") == "true"
                or _intersect(_rect(preview), _rect(preview[0])) != _rect(preview[0])
            )
        )
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


def _compact_quote_video(card, body, viewport):
    candidates = [
        n
        for n in card
        if n.xpath('./node[@content-desc="Video"]') and n.get("clickable") == "true"
    ]
    if not candidates:
        return set()
    preview = _one(candidates, "compact quoted video")
    if len(preview) not in (2, 3):
        raise _Unsupported("Unrecognized compact quoted video.")
    video, picture = preview[:2]
    play = preview[2] if len(preview) == 3 else None
    rect = _rect(preview)
    if (
        preview.get("class") != "android.view.View"
        or preview.get("text")
        or preview.get("content-desc")
        or preview.get("enabled") != "true"
        or preview.get("focusable") != "true"
        or preview.get("long-clickable") == "true"
        or preview.get("scrollable") == "true"
        or [n.get("content-desc", "") for n in preview]
        != ["Video", "", *(["play"] if play is not None else [])]
        # X can expose the native video/picture pair before its central Play
        # glyph enters the clipped card, even when the video's top is visible.
        or (play is None and not (rect[3] == _rect(card)[3] >= viewport[3]))
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
        or (play is not None and _intersect(rect, _rect(play)) != _rect(play))
        or not (
            rect[2] - rect[0] == rect[3] - rect[1]
            or (
                0 < rect[3] - rect[1] < rect[2] - rect[0]
                and rect[3] == _rect(card)[3] >= viewport[3]
            )
        )
        or _intersect(rect, _rect(card)) != rect
        or (
            body is not None
            and (
                rect[1] != _rect(body)[1]
                or rect[2] > _rect(body)[0]
                or _intersect(_rect(body), _rect(card)) != _rect(body)
                or preview.getnext() is not body
            )
        )
        or (
            body is None
            and (
                preview is not card[-1]
                or rect[1] <= max(_rect(n)[3] for n in list(card)[:-1])
                or not (0 < rect[0] - _rect(card)[0] == _rect(card)[2] - rect[2])
            )
        )
    ):
        raise _Unsupported("Unrecognized compact quoted video.")
    return set(preview.iter())


def _article_content_nodes(preview):
    children = list(preview)
    if not children or not children[-1].xpath('./node[@content-desc="Play"]'):
        return children
    control = children[-1]
    content = children[:-1]
    texts = [n for n in content if n.get("class") == "android.widget.TextView"]
    if len(control) != 1 or not texts:
        raise _Unsupported("Unrecognized article playback control.")
    glyph = control[0]
    rect, icon, title = map(_rect, (control, glyph, texts[0]))
    if (
        control.get("class") != "android.view.View"
        or control.get("clickable") != "true"
        or control.get("focusable") != "true"
        or control.get("text")
        or control.get("content-desc")
        or glyph.get("class") != "android.view.View"
        or glyph.get("content-desc") != "Play"
        or glyph.get("text")
        or len(glyph)
        or any(
            n.get("enabled") != "true"
            or n.get("visible-to-user") == "false"
            or n.get("long-clickable") == "true"
            or n.get("scrollable") == "true"
            for n in (control, glyph)
        )
        or any(glyph.get(flag) == "true" for flag in ("clickable", "focusable"))
        or rect[2] - rect[0] != rect[3] - rect[1]
        or icon[2] - icon[0] != icon[3] - icon[1]
        or _intersect(rect, icon) != icon
        or _intersect(_rect(preview), rect) != rect
        or abs(rect[0] + rect[2] - icon[0] - icon[2]) > 2
        or abs(rect[1] + rect[3] - icon[1] - icon[3]) > 2
        or not (title[1] <= icon[1] < icon[3] <= title[3])
        or any(_rect(n)[2] > icon[0] for n in texts)
        or (
            content[0].get("class") == "android.view.View"
            and _rect(content[0])[3] > rect[1]
        )
    ):
        raise _Unsupported("Unrecognized article playback control.")
    return content


def _article_preview(card, preceding, viewport, overlaps, excluded=()):
    candidates = [n for n in card if n.get("clickable") == "true" and n not in excluded]
    if not candidates:
        return (), set()
    preview = _one(candidates, "quoted article preview")
    content = _article_content_nodes(preview)
    if len(content) not in (1, 2, 3):
        raise _Unsupported("Unrecognized article preview.")
    picture, *texts = content
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
            for n in content
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


def _native_quote_image(wrapper, card):
    """Validate the native image wrapper shared by full and compact quotes."""
    if wrapper is None or len(wrapper) != 1:
        return set()
    image = wrapper[0]
    rect = _rect(wrapper)
    if (
        wrapper.get("class") != "android.view.View"
        or wrapper.get("text")
        or wrapper.get("content-desc")
        or any(
            wrapper.get(flag) == "true"
            for flag in ("clickable", "long-clickable", "focusable", "scrollable")
        )
        or image.get("class") != "android.widget.ImageView"
        or image.get("content-desc") != "Image"
        or image.get("text")
        or len(image)
        or any(
            image.get(flag) != "true"
            for flag in ("clickable", "long-clickable", "focusable")
        )
        or image.get("scrollable") == "true"
        or any(
            n.get("enabled") != "true" or n.get("visible-to-user") != "true"
            for n in (wrapper, image)
        )
        or _rect(image) != rect
        or _intersect(rect, _rect(card)) != rect
    ):
        return set()
    return {wrapper, image}


def _compact_quote_image(card, body, viewport):
    if body is None:
        return set()
    wrapper = body.getprevious()
    nodes = _native_quote_image(wrapper, card)
    if not nodes:
        return set()
    rect, body_rect = _rect(wrapper), _rect(body)
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    if (
        rect[1] != body_rect[1]
        or rect[2] > body_rect[0]
        or _intersect(body_rect, _rect(card)) != body_rect
        or not (
            height == width
            or (0 < height < width and rect[3] == _rect(card)[3] >= viewport[3])
        )
    ):
        return set()
    return nodes


def _quoted_translation(
    card, texts, viewport, overlaps, *, has_handle=True, reply=None
):
    header_count = 3 if has_handle else 2
    language_pattern = r"Translated from [A-Za-z]+(?:[ ()-][A-Za-z]+)*"
    if (
        len(texts) == header_count + 1
        and texts[-1].get("text", "").startswith("Translated from ")
        and _rect(texts[-1])[0] > _rect(_one(_desc(card, "Quote"), "quote marker"))[0]
    ):
        *header, label = texts
        rect = _rect(label)
        if (
            all(_rect(n)[1] >= viewport[3] for n in header)
            and label is card[-1]
            and label.getprevious() is header[-1]
            and _plain_annotation(label)
            and re.fullmatch(language_pattern, label.get("text"))
            and rect[1] >= max(_rect(n)[3] for n in header)
            and rect[3] == _rect(card)[3]
            and all(
                _intersect(_rect(n), _rect(card)) == _rect(n) for n in (*header, label)
            )
        ):
            return label
        raise _Unsupported("Quoted translation has no separate body.")
    if len(texts) != header_count + 2:
        return None
    *header, label, body = texts
    age = header[-1]
    rect, body_rect = _rect(label), _rect(body)
    preceding = label.getnext()
    if preceding is not body:
        _, preview_nodes = _quote_preview(card, body, viewport, overlaps)
        compact_nodes = _compact_quote_video(card, body, viewport)
        image_nodes = _compact_quote_image(card, body, viewport)
        if (
            preceding not in preview_nodes | compact_nodes | image_nodes
            or preceding.getnext() is not body
        ):
            raise _Unsupported("Unrecognized quoted translation annotation.")
    content_left = min(body_rect[0], _rect(preceding)[0])
    if (
        not re.fullmatch(language_pattern, label.get("text"))
        or not _plain_annotation(label)
        or label.getprevious() is not (reply if reply is not None else age)
        or rect[1] < max(_rect(n)[3] for n in header)
        or rect[3] > body_rect[1]
        or rect[0] <= content_left
        or rect[2] > body_rect[2]
    ):
        raise _Unsupported("Unrecognized quoted translation annotation.")
    return label


def _reply_recipients(text):
    recipients = text.removeprefix("Replying to ").replace("\ufeff", "")
    if not re.fullmatch(
        r"@[A-Za-z0-9_]{1,15}(?: and @[A-Za-z0-9_]{1,15})*", recipients
    ):
        raise _Unsupported("Unrecognized reply recipients.")
    return tuple(HANDLE.findall(recipients))


def _quoted_reply(card, texts, viewport):
    if len(texts) not in (5, 6) or not texts[3].get("text", "").startswith(
        "Replying to "
    ):
        return None
    name, handle, age, label, *content = texts
    body = content[-1]
    translated = len(content) == 2
    rect = _rect(label)
    preceding = body.getprevious()
    compact = _compact_quote_image(card, body, viewport)
    content_layout = (
        preceding is content[0]
        and preceding.get("text", "").startswith("Translated from ")
        and _plain_annotation(preceding)
        and rect[0] == _rect(body)[0]
        and rect[1] < _rect(preceding)[1] < rect[3] <= _rect(body)[1]
        if translated
        else (
            preceding in compact
            and rect[0] == _rect(preceding)[0]
            and rect[1] < _rect(body)[1] < rect[3] <= _rect(body)[3]
        )
    )
    if (
        label.get("class") != "android.widget.TextView"
        or len(label)
        or label.get("content-desc")
        or any(
            label.get(flag) != "true"
            for flag in ("clickable", "focusable", "enabled", "visible-to-user")
        )
        or any(label.get(flag) == "true" for flag in ("scrollable", "long-clickable"))
        or label.getprevious() is not age
        or label.getnext() is not preceding
        or not content_layout
        or rect[2] > _rect(body)[2]
        or rect[1] != _rect(name)[3]
        or _intersect(rect, _rect(card)) != rect
        or not HANDLE.fullmatch(handle.get("text", ""))
    ):
        raise _Unsupported("Unrecognized quoted reply annotation.")
    _reply_recipients(label.get("text"))
    return label


def _quote(card, viewport, overlaps):
    texts = [n for n in card if n.get("text")]
    reply = _quoted_reply(card, texts, viewport)
    if reply is not None:
        texts.remove(reply)
    handles = [n for n in card if HANDLE.fullmatch(n.get("text", ""))]
    if handles:
        handle = _handle(card, "quoted author", display_name=texts[0])
        if (
            texts.index(handle) != 1
            or len(texts) not in (3, 4, 5)
            or not texts[2].get("text").startswith("· ")
        ):
            raise _Unsupported("Unrecognized quote text arrangement.")
        translation = _quoted_translation(card, texts, viewport, overlaps, reply=reply)
        if translation is not None:
            texts.remove(translation)
        name, _, age, *bodies = texts
    else:
        if len(texts) not in (3, 4) or len(card) < 5:
            raise _Unsupported("Unrecognized quote without an author handle.")
        name, age, *bodies = texts
        marker, _, badge, _ = list(card)[:4]
        first, last, mark = map(_rect, (name, age, badge))
        if (
            list(card)[:4] != [marker, name, badge, age]
            or marker.get("content-desc") != "Quote"
            or not all(_plain_annotation(n) and n.get("text") for n in (name, age))
            or "@" in name.get("text")
            or not age.get("text").startswith("· ")
            or badge.get("class") != "android.view.View"
            or badge.get("content-desc") not in VERIFICATION_LABELS
            or badge.get("text")
            or len(badge)
            or not all(
                _visibility(n, viewport, overlaps).accessible
                for n in (name, badge, age)
            )
            or any(
                badge.get(flag) == "true"
                for flag in ("clickable", "focusable", "long-clickable", "scrollable")
            )
            or not (first[1] <= last[1] < last[3] <= first[3])
            or not (first[1] <= mark[1] < mark[3] <= first[3])
            or not (
                _rect(marker)[2] <= first[0] < first[2] <= mark[0] < mark[2] <= last[0]
            )
            # Native date glyph bounds can overhang the inset by five pixels.
            or not -4
            <= last[2] - (_rect(card)[2] - (_rect(marker)[0] - _rect(card)[0]))
            <= 5
        ):
            raise _Unsupported("Unrecognized quote without an author handle.")
        handle = None
        translation = _quoted_translation(
            card, texts, viewport, overlaps, has_handle=False
        )
        if translation is not None:
            bodies.remove(translation)
    body = bodies[0] if bodies else None
    _, annotation_nodes = _body_annotations(body)
    body_view = (
        _visibility(
            body, viewport, (*overlaps, *([_rect(reply)] if reply is not None else []))
        )
        if body is not None
        else None
    )
    media, media_nodes = _media(card, viewport, overlaps)
    compact_nodes = _compact_quote_video(card, body, viewport)
    previews, preview_nodes = _quote_preview(card, body, viewport, overlaps)
    articles, article_nodes = _article_preview(
        card,
        body if body is not None else age,
        viewport,
        overlaps,
        compact_nodes | {reply},
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
            if n is not None
        )
    )
    image_only = (
        body is None
        and len(media) == 1
        and media[0].kind == "image"
        and age.getnext() is card[-1]
        and bool(_native_quote_image(card[-1], card))
        and _rect(card[-1])[1] > max(_rect(n)[3] for n in list(card)[:-1])
    )
    video_only = (
        body is None and len(media) == 1 and media[0].kind == "video" and compact_nodes
    )
    if (
        body is None
        and not articles
        and not header_only
        and not image_only
        and not video_only
    ):
        raise _Unsupported("Bodyless quote has no recognized preview.")
    if articles and (previews or media):
        raise _Unsupported("Mixed article and quote media.")
    if previews and media:
        raise _Unsupported("Mixed compact and expanded quote media.")
    media += previews + articles
    labels = list(card)[
        list(card).index(name) + 1 : list(card).index(
            handle if handle is not None else age
        )
    ]
    for label in labels:
        rect = _rect(label)
        if (
            len(label)
            or label.get("text")
            or not label.get("content-desc")
            or label.get("clickable") == "true"
            or label.get("class") != "android.view.View"
            or rect[0] < _rect(name)[2]
            or rect[2] > _rect(handle if handle is not None else age)[0]
            or rect[1] < _rect(handle if handle is not None else age)[1]
            or rect[3] > _rect(handle if handle is not None else age)[3]
        ):
            raise _Unsupported("Unrecognized quoted author label.")
    known = {
        name,
        handle,
        age,
        body,
        translation,
        reply,
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
        handle.get("text") if handle is not None else None,
        name.get("text"),
        body.get("text") if body is not None else None,
        # Compact translated quote bounds do not establish full text visibility.
        body is not None
        and translation is None
        and reply is None
        and bool(_body_complete(body.get("text"), body_view)),
        media,
        _visibility(card, viewport, overlaps),
        _visibility(handle if handle is not None else name, viewport, overlaps),
        body_view,
        tuple(label.get("content-desc") for label in labels),
        translation.get("text") if translation is not None else None,
        translation_visibility=(
            _visibility(translation, viewport, overlaps)
            if translation is not None
            else None
        ),
        reply_annotation=reply.get("text") if reply is not None else None,
        reply_to=_reply_recipients(reply.get("text")) if reply is not None else (),
        reply_visibility=_visibility(reply, viewport, overlaps)
        if reply is not None
        else None,
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
        and media[0].kind in {"video", "gif"}
        and quote.visibility.bounds[1] >= media[0].visibility.bounds[3]
        and quote.visibility.bounds[::2] == media[0].visibility.bounds[::2]
    ):
        raise _Unsupported("Bodyless quote does not follow its outer video or GIF.")
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


def _sports_card(container, media, actions, viewport, overlays):
    status_pattern = (
        r"Final|(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), "
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (?:[1-9]|[12][0-9]|3[01])"
    )
    candidates = [
        n
        for n in container
        if n.get("class") == "android.view.View"
        and any(re.fullmatch(status_pattern, child.get("text", "")) for child in n)
    ]
    if not candidates:
        return None, set()
    card = _one(candidates, "sports result card")
    rect = _rect(card)
    if len(card) != 6:
        raise _Unsupported("Unrecognized sports result card.")
    first_icon, first, middle, second_icon, second, status = card
    labels = (first, second, status)
    icons = (first_icon, middle, second_icon)
    if (
        len(media) != 1
        or media[0].kind not in {"video", "gif"}
        or card.get("text")
        or card.get("content-desc")
        or card.get("clickable") != "true"
        or card.get("focusable") != "true"
        or card.get("enabled") != "true"
        or card.get("long-clickable") == "true"
        or card.get("scrollable") == "true"
        or any(not _plain_annotation(n) or not n.get("text") for n in labels)
        or any(not re.fullmatch(r"[A-Z]{2,4}", n.get("text")) for n in (first, second))
        or not re.fullmatch(status_pattern, status.get("text"))
        or any(_intersect(_rect(n), rect) != _rect(n) for n in labels)
        or any(_rect(n)[1::2] != _rect(first)[1::2] for n in labels)
        or any(_rect(x)[2] > _rect(y)[0] for x, y in pairwise(labels))
        or any(
            len(n)
            or n.get("class") != "android.view.View"
            or n.get("text")
            or n.get("content-desc")
            or n.get("enabled") != "true"
            or any(
                n.get(flag) == "true"
                for flag in ("clickable", "focusable", "long-clickable", "scrollable")
            )
            or not (rect[0] - 6 <= _rect(n)[0] < _rect(n)[2] <= rect[2])
            or not (rect[1] <= _rect(n)[1] <= rect[1] + 2)
            or _rect(n)[3] != rect[3]
            for n in icons
        )
        or any(_rect(x)[0] >= _rect(y)[0] for x, y in pairwise(icons))
        or rect[::2] != media[0].visibility.bounds[::2]
        or card.getprevious() is None
        or _rect(card.getprevious()) != media[0].visibility.bounds
        or rect[1] < media[0].visibility.bounds[3]
        or tuple(a.label for a in actions) != ACTION_LABELS
        or any(a.visibility.bounds[1] != rect[3] for a in actions)
    ):
        raise _Unsupported("Unrecognized sports result card.")
    return SportsCard(
        (first.get("text"), second.get("text")),
        status.get("text"),
        _visibility(card, viewport, overlays),
    ), set(card.iter())


def _market_adjacent_assets(wrapper, card, viewport, overlays):
    if len(wrapper) != 2 or wrapper.get("scrollable") != "true":
        raise _Unsupported("Unrecognized market carousel.")
    neighbor = wrapper[1]
    if len(neighbor) != 1 or len(neighbor[0]) != 1:
        raise _Unsupported("Unrecognized clipped market asset.")
    picture, icon = neighbor[0], neighbor[0][0]
    rect, primary = _rect(neighbor), _rect(card)
    if (
        any(
            n.get("class") != "android.view.View"
            or n.get("text")
            or n.get("enabled") != "true"
            or n.get("visible-to-user") != "true"
            or n.get("long-clickable") == "true"
            or n.get("scrollable") == "true"
            for n in (neighbor, picture, icon)
        )
        or neighbor.get("clickable") != "true"
        or neighbor.get("focusable") != "true"
        or neighbor.get("content-desc")
        or picture.get("content-desc")
        or len(icon)
        or not icon.get("content-desc")
        or any(
            n.get(flag) == "true"
            for n in (picture, icon)
            for flag in ("clickable", "focusable")
        )
        or _rect(wrapper)[::2] != viewport[::2]
        or rect[1::2] != primary[1::2]
        or rect[1::2] != _rect(wrapper)[1::2]
        or rect[0] <= primary[2]
        or rect[2] != viewport[2]
        or _rect(picture)[2] != viewport[2]
        or _rect(icon)[2] != viewport[2]
        or not (rect[0] < _rect(picture)[0] < _rect(icon)[0] < rect[2])
        or _rect(picture)[1::2] != _rect(card[0])[1::2]
        or _rect(icon)[1::2] != _rect(card[0][0])[1::2]
        or _intersect(_rect(picture), rect) != _rect(picture)
        or _intersect(_rect(icon), _rect(picture)) != _rect(icon)
        or _rect(icon)[2] - _rect(icon)[0] >= _rect(icon)[3] - _rect(icon)[1]
    ):
        raise _Unsupported("Unrecognized clipped market asset.")
    return (
        TextSpan(
            icon.get("content-desc"),
            replace(_visibility(icon, viewport, overlays), clipped=True),
        ),
    )


def _market_card(container, media, actions, viewport, overlays, quote_card=None):
    candidates = [
        wrapper
        for wrapper in container
        if len(wrapper) in (1, 2)
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
    adjacent_assets = (
        _market_adjacent_assets(wrapper, card, viewport, overlays)
        if len(wrapper) == 2 or wrapper.get("scrollable") == "true"
        else ()
    )
    end_rect = _rect(quote_card) if quote_card is not None else rect
    quote_neighbor = wrapper.getnext()
    wrapped_quote = (
        quote_card is not None
        and quote_neighbor is not None
        and list(quote_neighbor) == [quote_card]
        and _rect(quote_neighbor) == end_rect
        and quote_neighbor.get("class") == "android.view.View"
        and not quote_neighbor.get("text")
        and not quote_neighbor.get("content-desc")
        and quote_neighbor.get("enabled") == "true"
        and all(
            quote_neighbor.get(flag) != "true"
            for flag in ("clickable", "focusable", "long-clickable", "scrollable")
        )
    )
    if quote_card is not None and (
        (quote_neighbor is not quote_card and not wrapped_quote)
        or rect[3] > end_rect[1]
        or not media
        or end_rect[::2] != media[0].visibility.bounds[::2]
    ):
        raise _Unsupported("Unrecognized market card quote layout.")
    if (
        len(media) != 1
        or media[0].kind not in {"video", "gif"}
        or len(picture) != 1
        or any(
            n.get("class") != "android.view.View"
            or n.get("text")
            or n.get("content-desc")
            or (
                n.get("scrollable") == "true"
                and (n is not wrapper or not adjacent_assets)
            )
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
        or (not adjacent_assets and _rect(wrapper) != rect)
        or (
            rect[0] != media[0].visibility.bounds[0]
            or rect[2] > media[0].visibility.bounds[2]
            or (not adjacent_assets and rect[2] != media[0].visibility.bounds[2])
        )
        or wrapper.getprevious() is None
        or _rect(wrapper.getprevious()) != media[0].visibility.bounds
        or rect[1] < media[0].visibility.bounds[3]
        or (not actions and not (adjacent_assets and end_rect[3] >= viewport[3]))
        or any(a.visibility.bounds[1] != end_rect[3] for a in actions)
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
        _visibility(wrapper if adjacent_assets else card, viewport, overlays),
        adjacent_assets=adjacent_assets,
    ), set(wrapper.iter())


def _media_annotation(container, media, actions, viewport, overlaps):
    complete_footer = tuple(
        t.label for t in actions
    ) == ACTION_LABELS or _covered_bookmark_row(container, actions, viewport, overlaps)
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
            or not complete_footer
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
    direct_footer = (
        control is not None
        and complete_footer
        and _rect(control) == actions[0].visibility.bounds
        and all(t.visibility.bounds[1] == _rect(label)[3] for t in actions)
    )
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
        or (
            not direct_footer
            and (
                control.get("class") != "android.view.View"
                or control.get("clickable") != "true"
                or control.get("text")
                or control.get("content-desc")
                or len(control) != 1
                or control[0].get("class") != "android.widget.TextView"
                or control[0].get("text") != "Create your own with Grok"
                or control[0].get("content-desc")
                or control[0].get("clickable") == "true"
                or len(control[0])
                or _intersect(_rect(control), _rect(control[0])) != _rect(control[0])
            )
        )
        or any(_rect(previous)[3] != m.visibility.bounds[3] for m in media)
        or min(_rect(icon)[1], _rect(label)[1]) < _rect(previous)[3]
        or _rect(icon)[2] > _rect(label)[0]
        or _rect(icon)[3] != _rect(label)[3]
        or _rect(label)[3] != _rect(control)[1]
    ):
        raise _Unsupported("Unrecognized AI media annotation.")
    return (label.get("text"),), {
        icon,
        label,
        *(control.iter() if not direct_footer else ()),
    }


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


def _clipped_handle_above_cover(header, cover, viewport):
    if cover is None or len(header) != 3:
        return False
    name, badge, handle = header
    rect, first, mark, last = map(_rect, (header, name, badge, handle))
    return (
        all(_plain_annotation(n) and n.get("text") for n in (name, handle))
        and "@" not in name.get("text")
        and HANDLE.fullmatch(handle.get("text")) is not None
        and badge.get("class") == "android.view.View"
        and badge.get("content-desc") in VERIFICATION_LABELS
        and not badge.get("text")
        and not len(badge)
        and all(
            _visibility(n, viewport).accessible
            and not any(
                n.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "focusable", "scrollable")
            )
            for n in (header, badge)
        )
        and rect[1] < viewport[1] < last[3] == mark[3] == cover[1] < rect[3]
        and first[1::2] == rect[1::2]
        and last[1] == rect[1] <= mark[1] < mark[3]
        and rect[0]
        == first[0]
        < first[2]
        <= mark[0]
        < mark[2]
        <= last[0]
        < last[2]
        <= rect[2]
        and last[0] < cover[2]
        and last[2] > cover[0]
    )


def _covered_author(header, cover, viewport):
    if _clipped_handle_above_cover(header, cover, viewport):
        return True
    if cover is None or len(header) not in (2, 3):
        return False
    if len(header) == 3:
        badge = header[1]
        if (
            badge.get("class") != "android.view.View"
            or badge.get("content-desc") not in VERIFICATION_LABELS
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
    if HANDLE.fullmatch(age.get("text", "")):
        # Android can retain a clipped or overlapping handle node while
        # omitting the age under New posts. This is not author proof.
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
            and (
                (last[2] == cover[0] and cover[1] <= last[1] < last[3] <= cover[3])
                or (
                    cover[0] < last[2] <= cover[2]
                    and _intersect(last, cover) is not None
                )
            )
            and rect[0] == first[0]
            and _rect(header[-2])[2] <= last[0] < cover[0] <= last[2]
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


def _missing_handle_header(header, viewport, overlaps, *, header_cover=None):
    """Recognize the captured name/badge/age row without inferring its author."""
    if len(header) == 1:
        name = header[0]
        rect, first = _rect(header), _rect(name)
        return (
            _plain_annotation(name)
            and bool(name.get("text"))
            and "@" not in name.get("text")
            and not name.get("text").startswith("· ")
            and _visibility(header, viewport, overlaps).accessible
            and not any(
                header.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "scrollable", "focusable")
            )
            and rect[1] < viewport[1] < rect[3]
            and first[1::2] == rect[1::2]
            and abs(first[0] - rect[0]) <= 4
            and first[0] < first[2] < rect[2]
        )
    if (
        len(header) not in (2, 3)
        or not _visibility(
            header, viewport, tuple(r for r in overlaps if r != header_cover)
        ).unobscured
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
        or badge.get("content-desc") not in VERIFICATION_LABELS
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
        first[1::2] == rect[1::2]
        and rect[1] <= last[1] < last[3] <= rect[3]
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


def _avatar_live_badge(container, clipped_viewport=None):
    candidates = [n for n in container if n.xpath('./node/node[@text="LIVE"]')]
    if not candidates:
        return set()
    badge = _one(candidates, "avatar LIVE badge")
    if len(badge) != 1 or len(badge[0]) != 1:
        raise _Unsupported("Unrecognized avatar LIVE badge.")
    inner, label = badge[0], badge[0][0]
    avatar = badge.getprevious()
    rect, text = _rect(badge), _rect(label)
    if (
        any(
            n.get("class") != "android.view.View"
            or n.get("text")
            or n.get("content-desc")
            or n.get("enabled") != "true"
            or n.get("visible-to-user") != "true"
            or any(
                n.get(flag) == "true"
                for flag in ("clickable", "long-clickable", "focusable", "scrollable")
            )
            for n in (badge, inner)
        )
        or not _plain_annotation(label)
        or label.get("text") != "LIVE"
        or _rect(inner) != rect
        or _intersect(text, rect) != text
        or rect[2] - rect[0] != rect[3] - rect[1]
    ):
        raise _Unsupported("Unrecognized avatar LIVE badge.")
    if avatar is None:
        body = badge.getnext()
        if (
            clipped_viewport is None
            or body is None
            or not _plain_annotation(body)
            or not body.get("text")
            or not (rect[1] < clipped_viewport[1] < rect[3])
            or not (text[1] < clipped_viewport[1] < text[3])
            or not (_rect(body)[1] < clipped_viewport[1] < _rect(body)[3])
            or not (clipped_viewport[0] <= rect[0] < rect[2] < _rect(body)[0])
        ):
            raise _Unsupported("Unrecognized clipped LIVE badge.")
        return set(badge.iter())
    icon = _rect(avatar)
    if (
        avatar.get("class") != "android.widget.ImageView"
        or avatar.get("text")
        or not avatar.get("content-desc")
        or len(avatar)
        or any(
            avatar.get(flag) != "true"
            for flag in ("clickable", "long-clickable", "focusable", "enabled")
        )
        or avatar.get("scrollable") == "true"
        or rect[::2] != icon[::2]
        or icon[2] - icon[0] != icon[3] - icon[1]
        or not (icon[1] < rect[1] < icon[3] < rect[3])
        or not (text[1] < icon[3] < text[3])
    ):
        raise _Unsupported("Unrecognized avatar LIVE badge.")
    return {avatar, *badge.iter()}


def _post(header, viewport, overlaps, *, header_cover=None, allow_missing_handle=False):
    from .inspection import post_targets

    container = header.getparent()
    if container.get("clickable") != "true":
        raise _Unsupported("Unrecognized post container.")
    _one(container.xpath('.//*[@resource-id="timeline_post"]'), "outer author header")
    covered_author = _covered_author(header, header_cover, viewport)
    handle = (
        None
        if covered_author
        or (
            allow_missing_handle
            and _missing_handle_header(
                header, viewport, overlaps, header_cover=header_cover
            )
        )
        else _handle(
            header.iter(),
            "outer author",
            display_name=next((n for n in header if n.get("text")), None),
        )
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
    live_nodes = _avatar_live_badge(container)
    if live_nodes:
        labels.append("LIVE")
        known.update(live_nodes)
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
        container, media, actions, viewport, overlaps, card
    )
    known.update(market_nodes)
    sports_card, sports_nodes = _sports_card(
        container, media, actions, viewport, overlaps
    )
    known.update(sports_nodes)
    media_labels, annotation_nodes = _media_annotation(
        container, media, actions, viewport, overlaps
    )
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
            or node in live_nodes
            or node is account_label
            or node in translation_nodes
            or node in preview_nodes
            or node in annotation_nodes
            or node in market_nodes
            or node in sports_nodes
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
                reply_to = _reply_recipients(text)
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
                and (
                    covered_author
                    or (
                        allow_missing_handle
                        and _missing_handle_header(header, viewport, overlaps)
                    )
                )
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
            sports_card=sports_card,
            media_labels=media_labels,
            covered_header_visibility=_visibility(header, viewport, overlaps)
            if header_cover is not None
            else None,
            covered_handle=TextSpan(
                header[-1].get("text"), _visibility(header[-1], viewport, overlaps)
            )
            if header_cover is not None
            and len(header) in (2, 3)
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
            quote.author.lower()
            if quote.author is not None
            else [None, quote.display_name],
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
        if quote.reply_annotation:
            quoted_identity.append(["reply", quote.reply_annotation, quote.reply_to])
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
        sports_card=sports_card,
        advertising=advertising,
        advertising_visibility=advertising_view,
        community_note=community_note,
        targets=post_targets(header, media, viewport, overlaps),
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
    content = _article_content_nodes(preview)
    picture = content[0] if len(content) == 3 else None
    texts = content[1:] if picture is not None else content
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
        or any(_rect(a)[3] >= _rect(b)[1] for a, b in pairwise(content))
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
    if (
        not media
        and len(card) in (1, 2)
        and card[-1].get("class") == "android.widget.TextView"
    ):
        body = card[-1]
        translation = card[0] if len(card) == 2 else None
        _, annotation_nodes = _body_annotations(body)
        if (
            _plain_annotation(body, allowed_children=annotation_nodes)
            and bool(body.get("text"))
            and _rect(card)[1] < viewport[1] < _rect(body)[3] < viewport[3]
            and _intersect(_rect(body), _rect(card)) == _rect(body)
            and (footer or _rect(wrapper) == _rect(card))
            and wrapper.get("clickable") != "true"
            and card.get("clickable") == "true"
            and all(
                n.get("class") == "android.view.View"
                and not n.get("text")
                and not n.get("content-desc")
                and n.get("scrollable") != "true"
                and n.get("long-clickable") != "true"
                for n in (wrapper, card)
            )
            and all(t.visibility.bounds[1] == _rect(wrapper)[3] for t in actions)
            and (
                (translation is None and _rect(body)[1] < viewport[1])
                or (
                    translation is not None
                    and _plain_annotation(translation)
                    and re.fullmatch(
                        r"Translated from [A-Za-z]+(?:[ ()-][A-Za-z]+)*",
                        translation.get("text", ""),
                    )
                    and _rect(translation)[1]
                    < viewport[1]
                    < _rect(translation)[3]
                    == _rect(body)[1]
                    and _rect(body)[0]
                    < _rect(translation)[0]
                    < _rect(translation)[2]
                    <= _rect(body)[2]
                    and _intersect(_rect(translation), _rect(card))
                    == _rect(translation)
                )
            )
        ):
            return (
                TextSpan(body.get("text"), _visibility(body, viewport, overlays)),
                (),
                footer,
                tuple(
                    TextSpan(n.get("content-desc"), _visibility(n, viewport, overlays))
                    for n in annotation_nodes
                ),
                TextSpan(
                    translation.get("text"),
                    _visibility(translation, viewport, overlays),
                )
                if translation is not None
                else None,
            )
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
        None,
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


def _clipped_avatar_decoration(node, body, viewport):
    rect = _rect(node)
    return (
        len(node) <= 1
        and rect[2] - rect[0] == rect[3] - rect[1]
        and rect[1] < viewport[1] < rect[3]
        and viewport[0] <= rect[0] < rect[2] < _rect(body)[0]
        and all(
            n.get("class") == "android.view.View"
            and not n.get("text")
            and not n.get("content-desc")
            and n.get("enabled") == "true"
            and n.get("visible-to-user") == "true"
            and _rect(n) == rect
            and (n is node or not len(n))
            and all(
                n.get(flag) != "true"
                for flag in ("clickable", "long-clickable", "focusable", "scrollable")
            )
            for n in node.iter()
        )
    )


def _parallel_video_row(media):
    """Recognized native videos in one ordered, nonoverlapping horizontal row."""
    return (
        len(media) > 1
        and all(m.kind == "video" for m in media)
        and len({m.visibility.bounds[1::2] for m in media}) == 1
        and all(
            left.visibility.bounds[2] <= right.visibility.bounds[0]
            for left, right in pairwise(media)
        )
    )


def _clipped_media_before_footer(container, body, media, media_nodes, viewport):
    """Retain native body/video when the footer has not entered the viewport."""
    if body is None or len(media) != 1 or media[0].kind != "video":
        return False
    video, text = media[0].visibility.bounds, _rect(body)
    if not (
        text[::2] == video[::2]
        and text[3] <= video[1] < viewport[3] <= video[3] <= _rect(container)[3]
        and media[0].visibility.visible_bounds is not None
    ):
        return False
    # Prefix nodes and translation controls are validated by _fragment.
    children = list(container)
    following = children[children.index(body) + 1 :]
    if len(following) == 1 + len(ACTION_LABELS):
        wrapper, *slots = following
        rect = _rect(wrapper)
        slot_rects = [_rect(n) for n in slots]
        if (
            wrapper.get("class") == "android.view.View"
            and wrapper.get("clickable") == "true"
            and rect[:3] == video[:3]
            and 0 <= video[3] - rect[3] <= 14
            and any(n in media_nodes for n in wrapper.iter())
            and all(
                n.get("class") == "android.view.View"
                and len(n) <= 2
                and not n.get("text")
                and not n.get("content-desc")
                and all(
                    n.get(flag) == "true"
                    for flag in ("clickable", "long-clickable", "focusable", "enabled")
                )
                and n.get("scrollable") != "true"
                and all(
                    child.get("class") == "android.view.View"
                    and not len(child)
                    and not child.get("text")
                    and not child.get("content-desc")
                    and child.get("enabled") == "true"
                    and not any(
                        child.get(flag) == "true"
                        for flag in (
                            "clickable",
                            "long-clickable",
                            "focusable",
                            "scrollable",
                        )
                    )
                    and _rect(child)[1] >= _rect(n)[1]
                    and _rect(child)[3] == _rect(n)[3]
                    and _intersect(_rect(child), _rect(container)) == _rect(child)
                    for child in n
                )
                for n in slots
            )
            and all(
                r[1] == rect[3] >= viewport[3]
                and r[3] == _rect(container)[3]
                and _intersect(r, _rect(container)) == r
                for r in slot_rects
            )
            and all(left[2] == right[0] for left, right in pairwise(slot_rects))
            and slot_rects[0][0] < video[0]
            and slot_rects[-1][2] == _rect(container)[2]
        ):
            # The offscreen slots supply no action labels or state. They only
            # explain the native footer structure beneath the retained media.
            return True
    for node in following:
        if _rect(node) == video and any(n in media_nodes for n in node.iter()):
            continue
        rect = _rect(node)
        if (
            node is not container[-1]
            or any(
                len(n) > 1
                or n.get("class") != "android.view.View"
                or n.get("text")
                or n.get("content-desc")
                or n.get("enabled") != "true"
                or _rect(n) != rect
                or any(
                    n.get(flag) == "true" for flag in ("scrollable", "long-clickable")
                )
                for n in node.iter()
            )
            or rect[1] < max(viewport[3], video[3])
            or _intersect(rect, _rect(container)) != rect
        ):
            return False
    return True


def _fragment(container, viewport, overlays, *, collapsed=False):
    if (
        container.get("clickable") != "true"
        or _rect(container)[1] >= viewport[1]
        or container.xpath('.//*[@resource-id="timeline_post"]')
    ):
        raise _Unsupported("Not a clipped post container.")
    live_nodes = _avatar_live_badge(container, viewport if collapsed else None)
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
        container, media, actions, viewport, overlays, card
    )
    sports_card, sports_nodes = _sports_card(
        container, media, actions, viewport, overlays
    )
    media_labels, annotation_nodes = _media_annotation(
        container, media, actions, viewport, overlays
    )
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
                or (
                    not collapsed
                    and len(translation_nodes) == 2
                    and min(_rect(n)[1] for n in translation_nodes) <= viewport[1]
                    and max(_rect(n)[3] for n in translation_nodes) == _rect(body)[1]
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
            quoted_body, media, footer, annotations, quoted_translation = quoted_content
            return PostFragment(
                None,
                media,
                _visibility(container, viewport, overlays),
                None,
                actions,
                quoted_body=quoted_body,
                quoted_footer_annotations=footer,
                quoted_body_annotations=annotations,
                quoted_translation=quoted_translation,
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
    video_row = quote is None and _parallel_video_row(media)
    if (
        (
            not quote
            and len(media) != 1
            and not (body is not None and not media)
            and not video_row
        )
        or (len(media) > 1 and not video_row)
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
        and not (
            not actions
            and _clipped_media_before_footer(
                container, body, media, media_nodes, viewport
            )
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
        *live_nodes,
        *body_annotation_nodes,
        *media_nodes,
        *action_nodes,
        *advertising_nodes,
        *translation_nodes,
        *annotation_nodes,
        *market_nodes,
        *sports_nodes,
    }
    if card is not None:
        known.update(card.iter())
    if note_card is not None:
        known.update(note_card.iter())
    if body is None and media and len(container) > 1:
        avatar = container[0]
        rect, video = _rect(avatar), media[0].visibility.bounds
        prefix = [avatar]
        grok = container[1]
        if (
            len(container) > 2
            and grok.get("class") == "android.widget.ImageView"
            and grok.get("content-desc") == "Explain this post with Grok"
            and not grok.get("text")
            and not len(grok)
            and all(
                grok.get(flag) == "true"
                for flag in ("clickable", "focusable", "enabled", "visible-to-user")
            )
            and all(
                grok.get(flag) != "true" for flag in ("long-clickable", "scrollable")
            )
            and _rect(grok)[1] <= _rect(container)[1] < viewport[1]
            and viewport[1] < _rect(grok)[3] == video[1] <= rect[3]
            and video[0] < _rect(grok)[0] < _rect(grok)[2]
            and _rect(grok)[2] == _rect(container[2])[0]
            and _rect(grok)[1] == _rect(container[2])[1]
            and container[2].get("content-desc") == "Post options"
        ):
            prefix.append(grok)
        options = container[len(prefix)]
        if (
            options.get("class") == "android.widget.Button"
            and options.get("content-desc") == "Post options"
            and not options.get("text")
            and not len(options)
            and all(
                options.get(flag) == "true"
                for flag in ("clickable", "focusable", "enabled", "visible-to-user")
            )
            and all(
                options.get(flag) != "true" for flag in ("long-clickable", "scrollable")
            )
            and _rect(options)[1] <= _rect(container)[1] < viewport[1]
            and viewport[1] < _rect(options)[3] <= rect[3]
            and video[0] < _rect(options)[0]
            and _rect(options)[2] == _rect(container)[2]
        ):
            prefix.append(options)
        if (
            len(media) == 1
            and media[0].kind == "video"
            and len(container) > len(prefix)
            and (
                _rect(container[len(prefix)]) == video
                or (
                    _rect(container[len(prefix)])[:3] == video[:3]
                    and tuple(a.label for a in actions) == ACTION_LABELS
                    and all(
                        a.visibility.bounds[1] == _rect(container[len(prefix)])[3]
                        for a in actions
                    )
                    and _rect(container[len(prefix)])[3]
                    < video[3]
                    <= min(a.visibility.bounds[3] for a in actions)
                    and actions[0].visibility.bounds[0] <= video[0]
                    and actions[-1].visibility.bounds[2] >= video[2]
                )
            )
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
            known.update(prefix)
    for child in container:
        if child is body or body is None:
            break
        if child in translation_nodes or child in live_nodes:
            continue
        if _clipped_avatar_decoration(child, body, viewport):
            known.update(child.iter())
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
        sports_card=sports_card,
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


def _search_empty(scope, query, viewport, overlays):
    panels = scope.xpath(
        './node/node[@scrollable="true"]/node[@class="android.widget.ScrollView"]'
    )
    if query is None or len(panels) != 1:
        return False
    panel = panels[0]
    if (
        len(panel) != 2
        or len(panel.getparent()) != 1
        or any(
            panel.get(flag) != "false"
            for flag in ("clickable", "long-clickable", "scrollable")
        )
    ):
        return False
    title, hint = panel
    return (
        title.get("text") == f"No results for “{query}”"
        and hint.get("text")
        == (
            "Try searching for something else, or check your Search settings "
            "to see if they’re protecting you from potentially sensitive content."
        )
        and _rect(title)[3] <= _rect(hint)[1]
        and all(
            node.get("class") == "android.widget.TextView"
            and not len(node)
            and node.get("clickable") == "false"
            and node.get("long-clickable") == "false"
            and _visibility(node, viewport, overlays).unobscured
            for node in panel
        )
    )


def _read(root, area):
    windows = [n for n in root if n.get("package") == PACKAGE]
    window = _one(windows, "X window")
    if any(n.get("package") != PACKAGE for n in window.iter()):
        raise _Unsupported("Unexpected package inside X window.")
    keyboard, system_bars = [], []
    for other in root:
        if other is window:
            continue
        if other.get("package") in {
            "com.google.android.inputmethod.latin",
            "com.alexal1.adbkeyboard",
        }:
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
    landings = window.xpath('.//*[@resource-id="MainLanding"]')
    standalone = not landings
    if standalone and any(n.get("resource-id") in PRIMARY for n in window.iter()):
        landing = window
    else:
        landing = _one(landings, "MainLanding")
    if _desc(landing, "Close navigation menu"):
        return _drawer(landing, area, external)
    explore_settings = [
        node
        for label in ("Explore Settings", "Explore Settings. New feature available")
        for node in _desc(landing, label)
    ]
    markers = [n for n in landing.iter() if n.get("resource-id") in PRIMARY]
    if markers:
        if explore_settings:
            raise _Unsupported("Conflicting Explore and primary screen markers.")
        scope = _one(markers, "primary screen marker")
        kind = PRIMARY[scope.get("resource-id")]
    elif explore_settings:
        _one(explore_settings, "Explore Settings control")
        scope, kind = landing, "explore"
    else:
        raise _Unsupported("Unrecognized X screen.")
    if keyboard and kind != "search_input":
        raise _Unsupported("Unexpected keyboard over X screen.")
    if kind == "media":
        from .inspection import read_gallery

        return read_gallery(scope, area, external)
    controls, overlays = [], list(external)
    tab = query = active = profile = None
    query_field = None
    collapsed = (
        (kind == "home" and not _desc(landing, "Home"))
        or (
            standalone
            and kind == "search_results"
            and not _desc(scope, "Back")
            and not _desc(scope, "Search")
        )
        or (kind == "detail" and not _desc(scope, "Back"))
    )
    if kind == "search_input":
        field = _one(
            scope.xpath('.//*[@class="android.widget.EditText"]'), "query field"
        )
        if (
            field.get("focused") != "true"
            or field.get("enabled") != "true"
            or field.get("focusable") != "true"
            or field.get("password") == "true"
        ):
            raise _Unsupported("Query field is not focused.")
        if not _visibility(field, area, external).unobscured:
            raise _Unsupported("Query field is obscured.")
        query = field.get("text", "")
        query_field = TextField(PACKAGE, "SearchQuery")
        bar = _header_bar(field, scope)
        if len(keyboard) > 1:
            raise _Unsupported("Multiple keyboard windows.")
        bottom = keyboard[0][1] if keyboard else area[3]
        clear = _desc(field, "Clear search")
        if len(clear) > 1:
            raise _Unsupported("Multiple Clear search controls.")
        exclusions = (*external, *(_rect(_clickable(n, field)) for n in clear))
        controls.append(_target(field, "Query", scope, area, exclusions))
        top = _rect(bar)[3]
    elif kind == "home" and collapsed:
        top, bottom = _collapsed_home(scope, landing, area, system_bars)
        overlays.append((area[0], bottom, area[2], area[3]))
    else:
        if standalone:
            if kind not in {"search_results", "profile", "detail"}:
                raise _Unsupported("Unsupported standalone X screen.")
            if kind == "search_results" and not collapsed:
                back = _one(_desc(scope, "Back"), "search Back")
                back_target = _target(back, "Back", scope, area, external)
                if not back_target.visibility.unobscured:
                    raise _Unsupported("Search Back control is obscured.")
                controls.append(back_target)
            if kind == "detail":
                bottom = area[3]
            else:
                composer = _one(_desc(scope, "Post"), "floating composer")
                target = _clickable(composer, scope)
                if not _visibility(target, area, external).unobscured:
                    raise _Unsupported("Floating composer is obscured.")
                bottom = _rect(target)[3]
                if not area[1] < bottom < area[3]:
                    raise _Unsupported("Missing standalone bottom inset.")
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
            from .inspection import back_target

            field = _one(
                scope.xpath('.//*[@resource-id="post-detail-reply-text-field"]'),
                "reply composer",
            )
            composer = field.getparent()
            overlays.append(_rect(composer))
            bottom = _rect(composer)[1]
            if collapsed:
                bar = _one(system_bars, "collapsed detail status bar")
                if bar[:3] != area[:3] or bar[3] > area[3] * 0.1:
                    raise _Unsupported("Unrecognized collapsed detail header.")
                top = bar[3]
            else:
                back = _one(_desc(scope, "Back"), "detail Back")
                top = _rect(_header_bar(back, scope))[3]
                controls.append(back_target(scope, area, external))
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
            if kind == "search_results" and collapsed:
                bar = _one(system_bars, "collapsed search status bar")
                if (
                    bar[:3] != area[:3]
                    or bar[3] > area[3] * 0.1
                    or _rect(row)[1] != bar[3]
                    or scope.xpath('.//*[@class="android.widget.EditText"]')
                ):
                    raise _Unsupported("Unrecognized collapsed search header.")
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
                if len(labels) == 1 and (not collapsed or kind == "search_results"):
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
            if kind in ("search_results", "explore") and not collapsed:
                search = _one(_desc(scope, "Search"), "Search header")
                target = _clickable(search, scope)
                query_node = _one(target.xpath('.//*[@text!=""]'), "query header text")
                query = query_node.get("text") if kind == "search_results" else None
                if (
                    scope.xpath('.//*[@class="android.widget.EditText"]')
                    or _rect(target)[3] > top
                    or not _visibility(query_node, area, external).unobscured
                    or (
                        standalone
                        and _header_bar(back, scope) is not _header_bar(search, scope)
                    )
                ):
                    raise _Unsupported("Invalid noneditable query header.")
                controls.append(_target(search, "Search", scope, area, external))
            if kind == "profile":
                from .inspection import back_target

                profile, active = _profile_identity(scope, area, top, external)
                controls.append(back_target(scope, area, external))
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
    scroll_anchors = []
    navigation_areas = []
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
            if kind in {"home", "search_results"}:
                try:
                    scroll_areas.append(_scroll_area(header, viewport, tuple(overlays)))
                except _Unsupported:
                    pass
    if kind in {"home", "search_results"}:
        containers = scope.xpath(
            ("./" if kind == "home" else "./node/")
            + 'node[@scrollable="true"]/node[@scrollable="true"]/node'
        )
        containers = [node for node in containers if _intersect(_rect(node), viewport)]
        # The native list owns scrolling even when a child layout cannot be
        # extracted as a post. Keep every nested interaction excluded as usual.
        for container in containers:
            if container.get("clickable") != "true":
                continue
            try:
                scroll_area = _scroll_container(container, viewport, tuple(overlays))
            except _Unsupported:
                continue
            navigation_areas.append(scroll_area)
            for node in container.iterdescendants():
                text = node.get("text", "")
                if (
                    node.get("class") == "android.widget.TextView"
                    and len(text) >= 4
                    and sum(c.isalpha() for c in text) >= 3
                ):
                    try:
                        visibility = _visibility(node, viewport, tuple(overlays))
                    except _Unsupported:
                        continue
                    if visibility.accessible and visibility.visible_bounds is not None:
                        scroll_anchors.append(TextSpan(text, visibility))
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
    ) or (
        kind == "search_results"
        and _search_empty(scope, query, viewport, tuple(overlays))
    )
    if empty and (posts or rejected or fragments):
        raise _Unsupported("Empty timeline message conflicts with post candidates.")
    profile_evidence = detail = None
    if kind in {"profile", "detail"}:
        from .inspection import read_detail, read_profile

        if kind == "profile":
            profile_evidence = read_profile(scope, viewport, tuple(overlays), profile)
        else:
            detail, posts, rejected, scroll_areas, scroll_anchors = read_detail(
                scope, viewport, tuple(overlays)
            )
    return Screen(
        kind,
        reason=detail.main_reason if detail is not None else None,
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
        scroll_anchors=tuple(scroll_anchors),
        navigation_areas=tuple(navigation_areas),
        query_field=query_field,
        profile=profile_evidence,
        detail=detail,
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
