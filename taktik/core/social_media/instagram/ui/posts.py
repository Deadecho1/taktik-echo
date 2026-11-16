"""Native Instagram observation and workflow-specific controls using Taktik."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from taktik.core.shared.browsing import PlatformError
from taktik.core.shared.ui.geometry import bounds, nodes, text_of
from taktik.core.shared.ui.post_time import post_time_utc

UTC = timezone.utc

PACKAGE = "com.instagram.android"


def resource(name):
    return f'//*[@resource-id="{PACKAGE}:id/{name}"]'


def caption_text(text, username):
    # The feed's text layout includes the author's handle before the caption.
    prefix = re.match(rf"^@?{re.escape(username)}\s+", text)
    return text[prefix.end() :] if prefix else text


@dataclass
class PostView:
    username: str
    caption: str
    identity: str
    crop: tuple
    reel: bool
    visible_text: list
    root: object = field(repr=False)
    like_count: int | None = None
    post_time: str | None = None


def read_post(root, width, height, *, captured_at=None):
    from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import (
        PostReadingMixin,
    )
    from taktik.core.social_media.instagram.ui.extractors import (
        username_from_author_header,
    )
    from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import (
        POST_SELECTORS,
    )

    captured_at = captured_at or datetime.now(UTC)
    reader = PostReadingMixin()
    reader.screen_height = height
    window = reader.framed_post_context(root, recover_text=False)
    if window is not None:
        username = window["author"]
        crop = (
            0,
            max(0, window["header_bounds"][1]),
            width,
            min(height, window["window_bottom"]),
        )
        caption = window["caption_text"]
        identity = window["header_desc"]
        reel = False
    else:
        authors = nodes(
            root, POST_SELECTORS.reel_author_username_selectors, (0, 0, width, height)
        )
        if len(authors) != 1:
            raise PlatformError(
                "Cannot identify one current post author on this screen."
            )
        username = username_from_author_header(text_of(authors[0])) or ""
        crop = (0, 0, width, height)
        captions = nodes(root, POST_SELECTORS.reel_caption_selectors, crop)
        if not captions:
            captions = nodes(
                root,
                [resource("media_viewer_caption_text_view"), resource("clips_caption")],
                crop,
            )
        caption = next((text_of(n) for n in captions if text_of(n).strip()), "")
        sheet_captions = nodes(
            root,
            [
                resource("layout_container_bottom_sheet")
                + f'//*[starts-with(@content-desc, "{username} said ") or starts-with(@content-desc, "{username} a dit ")]'
            ],
            crop,
        )
        if sheet_captions:
            caption = re.sub(
                rf"^{re.escape(username)} (?:said|a dit) ",
                "",
                text_of(sheet_captions[0]),
            )
        identity = "reel"
        reel = True
    if (
        not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", username)
        or crop[3] - crop[1] < height * 0.2
    ):
        raise PlatformError(
            "The post is not sufficiently framed to attribute its content."
        )
    caption = caption_text(caption, username)
    visible = []
    for node in root.iter():
        rect = bounds(node)
        text = node.get("text", "")
        if (
            rect
            and crop[1] <= rect[1] < rect[3] <= crop[3]
            and text
            and text not in visible
        ):
            visible.append(text[:2000])
    signature = hashlib.sha256(
        (username + "\n" + identity + "\n" + caption).encode()
    ).hexdigest()
    like_count, post_time = read_metadata(root, crop, window, captured_at)
    return PostView(
        username,
        caption,
        signature,
        crop,
        reel,
        visible[:80],
        root,
        like_count,
        post_time,
    )


def read_metadata(root, crop, window, captured_at):
    from taktik.core.social_media.instagram.ui.extractors import (
        count_from_counter_label,
        likes_from_media_label,
    )
    from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import (
        POST_SELECTORS,
    )

    like_count = None
    for node in nodes(
        root,
        [resource("row_feed_photo_imageview") + " | " + resource("carousel_image")],
        crop,
    ):
        like_count = likes_from_media_label(node.get("content-desc"))
        if like_count is not None:
            break
    if like_count is None:
        for selector in [
            *POST_SELECTORS.like_count_selectors,
            resource("row_feed_textview_likes"),
        ]:
            for node in nodes(root, [selector], crop):
                # A facepile naming people is not a total like count.
                label = text_of(node)
                if re.search(r"\b(?:others?|autres?)\b", label, re.IGNORECASE):
                    continue
                like_count = count_from_counter_label(label)
                if like_count is not None:
                    break
            if like_count is not None:
                break

    if window is not None:
        bottom = max(
            [rect[3] for rect, _ in window["captions"]]
            + [(window["buttons_bounds"] or window["header_bounds"])[3]]
        )
        date_nodes = nodes(
            root,
            ['//*[self::android.widget.TextView or @class="android.widget.TextView"]'],
            crop,
        )
        labels = [text_of(n) for n in date_nodes if bounds(n)[1] >= bottom]
    else:
        # Dates are separate elements in the reel caption or its expanded sheet.
        containers = nodes(
            root,
            [
                resource("layout_container_bottom_sheet"),
                resource("clips_caption_component"),
            ],
            crop,
        )
        labels = []
        for container in containers:
            caption_bottom = max(
                [
                    bounds(n)[3]
                    for n in container.iter()
                    if bounds(n) and re.search(r" (?:said|a dit) ", text_of(n))
                ]
                or [bounds(container)[1]]
            )
            labels.extend(
                text_of(n)
                for n in container.iter()
                if bounds(n) and bounds(n)[1] >= caption_bottom and not len(n)
            )
    for label in labels:
        result = post_time_utc(label, captured_at)
        if result:
            return like_count, result
    if window is not None:
        # Some layouts expose the date only at the end of the author's header.
        words = window["header_desc"].split()
        for start in range(1, len(words)):
            result = post_time_utc(" ".join(words[start:]), captured_at)
            if result:
                return like_count, result
    return like_count, None


def read_scrolled_post_time(root, reference, width, height, captured_at):
    headers = nodes(
        reference.root, [resource("row_feed_profile_header")], reference.crop
    )
    if len(headers) != 1:
        return None
    header = text_of(headers[0])
    try:
        current = read_post(root, width, height, captured_at=captured_at)
    except PlatformError:
        current = None
    if current and not current.reel:
        current_headers = nodes(
            root, [resource("row_feed_profile_header")], current.crop
        )
        if (
            len(current_headers) == 1
            and text_of(current_headers[0]) == header
            and current.username == reference.username
            and (not reference.caption or same_content(current, reference))
        ):
            return current.post_time

    # A short scroll can hide the header while leaving the same caption visible.
    captions = nodes(
        root,
        [
            (
                "//*[self::com.instagram.ui.widget.textview.IgTextLayoutView "
                'or @class="com.instagram.ui.widget.textview.IgTextLayoutView"]'
            )
        ],
        (0, 0, width, height),
    )
    matches = [
        node
        for node in captions
        if reference.caption
        and caption_text(text_of(node), reference.username) == reference.caption
    ]
    if len(matches) != 1:
        return None
    caption_top, caption_bottom = bounds(matches[0])[1::2]
    headers = nodes(root, [resource("row_feed_profile_header")])
    above = [node for node in headers if bounds(node)[1] < caption_top]
    if above and text_of(max(above, key=lambda node: bounds(node)[1])) != header:
        return None
    bottom = min(
        [height]
        + [bounds(node)[1] for node in headers if bounds(node)[1] >= caption_top]
        + [bounds(node)[1] for node in nodes(root, [resource("tab_bar")])]
        + [
            bounds(node)[3]
            for node in nodes(root, ['//*[@resource-id="android:id/list"]'])
        ]
    )
    for node in nodes(
        root,
        ['//*[self::android.widget.TextView or @class="android.widget.TextView"]'],
        (0, caption_bottom, width, bottom),
    ):
        result = post_time_utc(text_of(node), captured_at)
        if result:
            return result
    return None


def same_content(view, observation, expanded=False):
    if view.username.casefold() != observation.username.casefold():
        return False
    if view.identity == observation.identity:
        return True
    if expanded:
        prefix = re.sub(
            r"(?:\s*(?:…|\.\.\.)?\s*(?:more|plus))?\s*$", "", observation.caption
        ).rstrip("…. \t\r\n")
        other = re.sub(
            r"(?:\s*(?:…|\.\.\.)?\s*(?:more|plus))?\s*$", "", view.caption
        ).rstrip("…. \t\r\n")
        return bool(prefix and other) and (
            view.caption.startswith(prefix) or observation.caption.startswith(other)
        )
    return False
