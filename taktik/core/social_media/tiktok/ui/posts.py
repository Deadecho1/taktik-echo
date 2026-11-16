"""TikTok post capture and verified native actions using the pinned Taktik catalogs."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from loguru import logger

from taktik.core.shared.browsing import PlatformError
from taktik.core.shared.ui.geometry import bounds, nodes, text_of
from taktik.core.shared.ui.post_time import tiktok_post_time_utc

UTC = timezone.utc

PACKAGE = "com.zhiliaoapp.musically"
PHOTO_LAYOUT_IDS = (("r__", "wu8", "r9k"), ("r_y", "wv8", "r_j"))


@dataclass(frozen=True)
class PhotoLayout:
    detected: bool
    images: tuple
    controls: tuple
    slide_index: int | None = None
    slide_count: int | None = None

    def swipe_bounds(self, fallback):
        rect = self.images[0] if len(self.images) == 1 else fallback
        if rect and len(self.images) <= 1:
            left, top, right, bottom = rect
            cutoffs = [
                y1
                for x1, y1, x2, y2 in self.controls
                if x1 <= (left + right) / 2 <= x2 and y2 > top and y1 < bottom
            ]
            bottom = min([bottom, *cutoffs])
            if (self.images or cutoffs) and bottom - top >= 2:
                return left, top, right, bottom
        logger.warning(
            "Unsupported TikTok photo layout: image_bounds={}, pagination_bounds={}, media_bounds={}",
            self.images,
            self.controls,
            fallback,
        )
        raise PlatformError(
            "Cannot locate a safe swipe area for this TikTok photo layout."
        )


def photo_layout(root, area):
    pagers, images, controls = [], [], []
    for pager_id, image_id, controls_id in PHOTO_LAYOUT_IDS:
        pager = f'//*[@resource-id="{PACKAGE}:id/{pager_id}"]'
        pagers.extend(nodes(root, [pager], area))
        images.extend(
            nodes(root, [pager + f'//*[@resource-id="{PACKAGE}:id/{image_id}"]'], area)
        )
        controls.extend(
            nodes(root, [f'//*[@resource-id="{PACKAGE}:id/{controls_id}"]'], area)
        )
    creator, _, media, *_ = catalogs()
    content = set(
        nodes(root, creator.author_username, area)
        + nodes(root, media.video_description, area)
    )
    detected = bool(pagers or images or controls)
    slide_index = slide_count = None
    for node in nodes(root, ["//*"], area):
        if node in content or any(parent in content for parent in node.iterancestors()):
            continue
        label = text_of(node)
        if not label and any(child.get("text", "").strip() == "/" for child in node):
            label = "".join(child.get("text", "") for child in node)
        match = re.fullmatch(
            r"(?:Photo\s+)?(\d+)\s*(?:/|of)\s*(\d+)", label, re.IGNORECASE
        )
        if match and 1 <= int(match[1]) <= int(match[2]):
            position = tuple(map(int, match.groups()))
            if slide_count is not None and (slide_index, slide_count) != position:
                raise PlatformError("Ambiguous photo slide counters.")
            slide_index, slide_count = position
            detected = True
        detected |= label in ("Photo", "Photos", "Photo mode")
    return PhotoLayout(
        detected,
        tuple(bounds(node) for node in images),
        tuple(bounds(node) for node in controls),
        slide_index,
        slide_count,
    )


def catalogs():
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import (
        VIDEO_CREATOR_SELECTORS,
        VIDEO_ENGAGEMENT_SELECTORS,
        VIDEO_MEDIA_SELECTORS,
        VIDEO_SHARE_SELECTORS,
        VIDEO_STATE_SELECTORS,
    )

    return (
        VIDEO_CREATOR_SELECTORS,
        VIDEO_ENGAGEMENT_SELECTORS,
        VIDEO_MEDIA_SELECTORS,
        VIDEO_SHARE_SELECTORS,
        VIDEO_STATE_SELECTORS,
    )


def count_label(label):
    text = re.sub(r"[\s,\u200e\u200f]", "", label).upper()
    if not re.fullmatch(r"\d+(?:\.\d+)?[KMB]?", text):
        return None
    suffix = text[-1] if text[-1] in "KMB" else ""
    try:
        value = (
            Decimal(text[:-1] if suffix else text)
            * {
                "": 1,
                "K": 1000,
                "M": 1_000_000,
                "B": 1_000_000_000,
            }[suffix]
        )
        return int(value) if value == int(value) else None
    except InvalidOperation:
        return None


def caption_prefix(caption):
    return re.sub(r"(?:…|\.\.\.)[\s\u2060\u200e\u200f]*more\s*$", "", caption).rstrip()


def unlabeled_for_you_card_bounds(root, width, height):
    from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import (
        NAVIGATION_SELECTORS,
    )

    area = (0, 0, width, height)
    tabs = []
    for selectors in (NAVIGATION_SELECTORS.home_tab, NAVIGATION_SELECTORS.for_you_tab):
        selected = nodes(root, [s + '[@selected="true"]' for s in selectors], area)
        if len(selected) != 1:
            return None
        tabs.append(bounds(selected[0]))
    pagers = nodes(
        root,
        [
            (
                f'//*[@resource-id="{PACKAGE}:id/view_pager_layout_wrapper"]'
                f'/*[@resource-id="{PACKAGE}:id/viewpager"][@scrollable="true"]'
            )
        ],
        area,
    )
    if len(pagers) != 1:
        return None
    content = nodes(pagers[0], [".//*"], bounds(pagers[0]))
    # Community and topic cards render their labels outside the accessibility tree.
    if not any(
        n.get("class", n.tag) == "android.widget.ImageView" for n in content
    ) or any(
        n.get("resource-id") or text_of(n).strip() or n.get("clickable") == "true"
        for n in content
    ):
        return None
    left, top, right, bottom = bounds(pagers[0])
    top, bottom = max(top, tabs[1][3]), min(bottom, tabs[0][1])
    return (left, top, right, bottom) if top < bottom else None


def excluded_content(root, width, height):
    from taktik.core.social_media.tiktok.ui.selectors.shell.popups import (
        POPUP_SELECTORS,
    )

    creator, _, media, _, state = catalogs()
    area = (0, 0, width, height)
    selectors = [
        *state.ad_label,
        *state.live_preview,
        *state.stories_card,
        *POPUP_SELECTORS.suggestion_page_indicator,
        '//*[@text="Sponsored" or @text="Shop now" or @text="TikTok Shop"]',
        '//*[starts-with(@content-desc, "Watch LIVE") or contains(@text, "Tap to watch LIVE")]',
        '//*[@text="People you may know" or @text="Suggested accounts"]',
        '//*[contains(@resource-id, ":id/rdt")][@text="Personnes que tu pourrais connaître"]',
    ]
    if nodes(root, selectors, area) or unlabeled_for_you_card_bounds(
        root, width, height
    ):
        return True
    avatars = nodes(
        root,
        [
            s + '[@content-desc!=""]'
            for s in creator.creator_profile_image_resource_id_selectors
        ],
        area,
    )
    # Invisible nicknames can omit the name control entirely; skip only a known post.
    return (
        not nodes(root, [s + '[@text!=""]' for s in creator.author_username], area)
        and len(avatars) == 1
        and len(nodes(root, media.video_container, area)) == 1
    )


@dataclass
class PostView:
    username: str
    caption: str
    identity: str
    source_key: str
    crop: tuple
    visible_text: list
    root: object = field(repr=False)
    author: object = field(repr=False)
    like_count: int | None = None
    post_time: str | None = None
    slide_index: int | None = None
    slide_count: int | None = None
    media_type: str = "video"
    date_label: str = ""
    caption_type: str | None = None


def read_post(root, width, height, *, captured_at=None):
    creator, engagement, media, _, state = catalogs()
    area = (0, 0, width, height)
    if excluded_content(root, width, height):
        raise PlatformError("This TikTok item is excluded from browsing.")
    # The avatar description may contain a handle. Export only the actual name text.
    authors = nodes(root, [s + '[@text!=""]' for s in creator.author_username], area)
    if len(authors) > 1:
        authors = [
            node
            for node in authors
            if node.tag == "android.widget.Button"
            or node.get("class") == "android.widget.Button"
        ]
    if len(authors) != 1 or not text_of(authors[0]).strip():
        raise PlatformError("Cannot identify one displayed TikTok post author.")
    author = authors[0]
    username = text_of(author)
    captions = nodes(root, media.video_description, area)
    if len(captions) > 1:
        raise PlatformError("Multiple TikTok captions are visible.")
    caption = text_of(captions[0]) if captions else ""
    if captions:
        titles = [
            node
            for node in captions[0].getparent().iter()
            if node is not author
            and node.get("resource-id", "").endswith(":id/title")
            and text_of(node)
        ]
        if len(titles) == 1:
            caption = text_of(titles[0]) + "\n" + caption
    containers = nodes(root, media.video_container, area)
    indicators = nodes(root, state.video_page_indicator, area)
    if not containers and not indicators:
        raise PlatformError("The screen is not an attributable TikTok post.")
    crop = bounds(containers[0]) if len(containers) == 1 else area
    dates = nodes(root, media.post_time, area)
    date_label = text_of(dates[0]) if len(dates) == 1 else ""
    avatars = nodes(root, creator.creator_profile_image_resource_id_selectors, area)
    avatar_labels = {text_of(node) for node in avatars if text_of(node)}
    if len(avatar_labels) > 1:
        raise PlatformError("Multiple TikTok author avatars are visible.")
    avatar_label = next(iter(avatar_labels), "")
    source_key = f"{username}\n{avatar_label}"
    identity = hashlib.sha256(
        (source_key + "\n" + date_label + "\n" + caption_prefix(caption)).encode()
    ).hexdigest()
    labels = [
        text_of(node)
        for node in nodes(
            root,
            engagement.like_count
            + ['//*[@content-desc="Video liked"]/descendant::*[@text!=""][1]'],
            area,
        )
    ]
    for node in nodes(root, engagement.like_button_for_count, area):
        match = re.fullmatch(
            r"(?:Like video|Unlike video)[. ]+([\d,.\s]+[KMB]?) likes?",
            text_of(node),
            re.IGNORECASE,
        )
        if match:
            labels.append(match[1])
    # Prefer a full accessibility count over an abbreviated visible counter.
    labels.sort(key=lambda label: bool(re.search(r"[KMB]", label, re.IGNORECASE)))
    like_count = next(
        (count for label in labels if (count := count_label(label)) is not None), None
    )
    visible = []
    layout = photo_layout(root, crop)
    for node in root.iter():
        rect = bounds(node)
        if not rect or not (
            crop[0] <= rect[0] < rect[2] <= crop[2]
            and crop[1] <= rect[1] < rect[3] <= crop[3]
        ):
            continue
        label = text_of(node)
        if not label and any(child.get("text", "").strip() == "/" for child in node):
            label = "".join(child.get("text", "") for child in node)
        if node.get("text") and label not in visible:
            visible.append(label[:2000])
    caption_type = None
    for node in nodes(
        root, ['//*[@resource-id="com.zhiliaoapp.musically:id/tv_toggle"]'], area
    ):
        label = text_of(node).casefold()
        if label in ("more", "less"):
            caption_type = "truncated" if label == "more" else "full"
    return PostView(
        username,
        caption,
        identity,
        source_key,
        crop,
        visible[:80],
        root,
        author,
        like_count,
        tiktok_post_time_utc(date_label, captured_at or datetime.now(UTC)),
        layout.slide_index,
        layout.slide_count,
        "photo" if layout.detected else "video",
        date_label,
        caption_type,
    )


def read_photo_caption(root, reference, width, height):
    authors = nodes(root, ['//*[@resource-id="com.zhiliaoapp.musically:id/k35"]'])
    descriptions = nodes(root, ['//*[@resource-id="com.zhiliaoapp.musically:id/snd"]'])
    titles = nodes(root, ['//*[@resource-id="com.zhiliaoapp.musically:id/sob"]'])
    if (
        len(authors) != 1
        or len(descriptions) != 1
        or text_of(authors[0]) != reference.username
    ):
        raise PlatformError("Cannot attribute the expanded photo caption.")
    caption = (text_of(titles[0]) + "\n" if len(titles) == 1 else "") + text_of(
        descriptions[0]
    )
    prefix = caption_prefix(reference.caption)
    if not prefix or not caption.startswith(prefix):
        raise PlatformError("The expanded photo caption belongs to a different post.")
    return PostView(
        reference.username,
        caption,
        reference.identity,
        reference.source_key,
        (0, 0, width, height),
        [caption],
        root,
        authors[0],
        reference.like_count,
        reference.post_time,
        reference.slide_index,
        reference.slide_count,
        "photo",
        reference.date_label,
        "full",
    )


def same_post(view, observation, *, expanded=False):
    if view.source_key != observation.source_key:
        return False
    if (
        view.date_label
        and observation.date_label
        and view.date_label != observation.date_label
    ):
        return False
    before, after = caption_prefix(observation.caption), caption_prefix(view.caption)
    return before == after or bool(
        expanded
        and before
        and after
        and (after.startswith(before) or before.startswith(after))
    )
