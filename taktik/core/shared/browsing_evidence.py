"""Opt-in ground truth capture using the same observations as persona exports."""

import io
import re
from urllib.parse import urljoin, urlsplit

import requests
from lxml import etree

from taktik.core.shared.browsing import PlatformError
from taktik.core.shared.ui.geometry import nodes

COPY_SELECTORS = [
    '//*[@content-desc="Copy link" and @clickable="true"]',
    '//*[@content-desc="Copy link"]',
    '//*[@text="Copy link" or @text="Copy Link"]',
]


def canonical_url(value, platform):
    for candidate in re.findall(r"https://[^\s<>\"']+", value or ""):
        parts = urlsplit(candidate.rstrip(".,)"))
        if parts.username or parts.password or parts.port:
            continue
        if platform == "instagram" and parts.hostname in (
            "instagram.com",
            "www.instagram.com",
        ):
            match = re.fullmatch(
                r"/(?:[\w.]+/)?(p|reel|reels|tv)/([\w-]+)/?", parts.path
            )
            if match:
                kind, code = match.groups()
                return f"https://www.instagram.com/{'reel' if kind == 'reels' else kind}/{code}/"
        if (
            platform == "tiktok"
            and parts.hostname in ("tiktok.com", "www.tiktok.com", "m.tiktok.com")
            and re.fullmatch(r"/@[^/]+/(video|photo)/\d+/?", parts.path)
        ):
            return "https://www.tiktok.com" + parts.path.rstrip("/")
    return None


def copied_url(value, platform):
    direct = canonical_url(value, platform)
    if direct:
        return direct
    if platform != "tiktok":
        return None
    for candidate in re.findall(r"https://[^\s<>\"']+", value or ""):
        parts = urlsplit(candidate)
        if parts.hostname not in ("vm.tiktok.com", "vt.tiktok.com", "www.tiktok.com"):
            continue
        with requests.Session() as client:
            for _ in range(6):
                parts = urlsplit(candidate)
                if (
                    parts.scheme != "https"
                    or parts.hostname
                    not in (
                        "vm.tiktok.com",
                        "vt.tiktok.com",
                        "www.tiktok.com",
                        "m.tiktok.com",
                        "tiktok.com",
                    )
                    or parts.username
                    or parts.password
                    or parts.port
                ):
                    break
                direct = canonical_url(candidate, platform)
                if direct:
                    return direct
                with client.get(
                    candidate, timeout=15, allow_redirects=False, stream=True
                ) as response:
                    location = response.headers.get("location")
                    if (
                        response.status_code not in (301, 302, 303, 307, 308)
                        or not location
                    ):
                        break
                    candidate = urljoin(candidate, location)
    return None


def raw_screen(app):
    return etree.fromstring(app.phone.read("hierarchy").encode())


def clipboard(app):
    try:
        return (app.phone.read("clipboard") or "").strip()
    except Exception:  # noqa: BLE001 - Some Android versions deny clipboard access.
        return ""


def verify_current(app, observation):
    if app.name == "instagram":
        return app._current(observation, allow_caption_change=True)
    return app._current(observation, expanded=True)


def close_share(app, observation):
    for _ in range(4):
        root = raw_screen(app)
        sheet = nodes(root, COPY_SELECTORS) or root.xpath(
            '//*[contains(@resource-id, "resolver_list") '
            'or contains(@resource-id, "chooser_scroll") '
            'or contains(@resource-id, "share_sheet") '
            'or contains(@resource-id, ":id/fxs")]'
        )
        if not sheet:
            verify_current(app, observation)
            return
        app.phone.command("back").require()
        app.sleep(0.5)
    raise PlatformError("Could not close the benchmark share sheet.")


def capture_evidence(app, observation):
    view = verify_current(app, observation)
    image = app.phone.read("screenshot").convert("RGB")
    screen = etree.tostring(raw_screen(app), encoding="utf-8")
    verify_current(app, observation)
    app._close_caption()
    view = verify_current(app, observation)
    if app.name == "instagram":
        from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import (
            POST_SELECTORS,
        )

        selectors = POST_SELECTORS.share_button_selectors
        choices = nodes(view.root, selectors, view.crop)
        if not choices and not view.reel:
            view = app._show_post_buttons(view)
            verify_current(app, observation)
            choices = nodes(view.root, selectors, view.crop)
    else:
        from taktik.core.social_media.tiktok.ui.posts import catalogs

        _, engagement, *_ = catalogs()
        choices = nodes(view.root, engagement.share_button, view.crop)
    if len(choices) != 1:
        raise PlatformError("The observed post has no unambiguous Share button.")
    before = clipboard(app)
    app.tap(choices[0])
    app.sleep(0.8)
    value = None
    try:
        for _ in range(5):
            root = raw_screen(app)
            choices = nodes(root, COPY_SELECTORS, (0, 0, app.width, app.height))
            if choices:
                break
            app.sleep(0.5)
        if len(choices) != 1:
            raise PlatformError("Copy link is missing or ambiguous in the share sheet.")
        app.tap(choices[0])
        for _ in range(8):
            app.sleep(0.4)
            after = clipboard(app)
            if after and after != before:
                value = after
                break
            root = raw_screen(app)
            visible = [
                n.get("text", "") for n in root.iter() if n.get("package") == "android"
            ]
            value = next(
                (text for text in visible if canonical_url(text, app.name)), None
            )
            if value:
                break
        if not value:
            raise PlatformError("Copy link did not produce a fresh post URL.")
    finally:
        with app.phone.cleanup():
            close_share(app, observation)
    try:
        url = copied_url(value, app.name)
    except requests.RequestException as error:
        raise PlatformError("Could not resolve the copied post URL.") from error
    if not url:
        raise PlatformError(
            "The copied link could not be resolved to a canonical post URL."
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return url, buffer.getvalue(), screen, value
