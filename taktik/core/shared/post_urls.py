"""Platform-specific canonical public post identities, including photo posts."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {
    "igsh",
    "igshid",
    "fbclid",
    "share_app_id",
    "share_item_id",
    "share_link_id",
    "is_from_webapp",
    "sender_device",
    "web_id",
    "is_copy_url",
    "tt_from",
    "u_code",
    "timestamp",
    "_r",
    "_t",
    "lang",
    "refer",
    "referer_url",
    "referer_video_id",
    "enter_from",
}


def canonicalize(platform, value):
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or re.search(r"[\s\\\x00-\x1f]", value)
    ):
        raise ValueError("Invalid public post URL.")
    parsed = urlsplit(value)
    if platform == "x":
        return _x_url(parsed)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port
        or host != platform + ".com"
    ):
        raise ValueError("Post URL is outside the selected public platform.")
    patterns = {
        "instagram": r"/(?:p|reel|reels)/([A-Za-z0-9_-]+)/?",
        "tiktok": r"/@[A-Za-z0-9_.-]+/(?:video|photo)/(\d+)/?",
    }
    found = re.fullmatch(patterns[platform], parsed.path)
    if not found:
        raise ValueError("Expected a direct Instagram or TikTok post URL.")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING and not key.startswith("utm_")
    ]
    path = parsed.path.rstrip("/") + ("/" if platform == "instagram" else "")
    return urlunsplit(("https", "www." + host, path, urlencode(query), "")), found[1]


def _x_url(parsed):
    hosts = {
        "x.com",
        "www.x.com",
        "m.x.com",
        "twitter.com",
        "www.twitter.com",
        "mobile.twitter.com",
        "m.twitter.com",
    }
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ValueError("Post URL is outside the selected public platform.")
    found = re.fullmatch(
        r"/([A-Za-z0-9_]{1,15})/status/([1-9][0-9]{0,19})/?", parsed.path
    )
    if not found or int(found[2]) > 2**64 - 1:
        raise ValueError("Expected a direct X post URL with an author and native ID.")
    author, post_id = found.groups()
    if author.lower() == "i":
        raise ValueError("An authorless X status URL cannot identify a post author.")
    return f"https://x.com/{author}/status/{post_id}", post_id
