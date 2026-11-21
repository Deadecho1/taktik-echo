"""Post observations, supported browsing capabilities, and execution outcomes."""

from dataclasses import dataclass, field

from taktik.core.shared.phone_interaction import InteractionError

WORKFLOWS = ["home", "reels", "explore", "search", "profile"]
PLATFORM_WORKFLOWS = {
    "instagram": WORKFLOWS,
    "tiktok": ["for_you", "search", "profile"],
}

ACTIONS = [
    "skip",
    "watch",
    "inspect",
    "read_more",
    "like",
    "save",
    "follow",
    "unfollow",
    "not_interested",
]


@dataclass
class PostObservation:
    username: str
    caption: str
    identity: str
    workflow: str
    frames: list[bytes] = field(default_factory=list)
    visible_text: list[str] = field(default_factory=list)
    elapsed: float = 0
    caption_expanded: bool = False
    like_count: int | None = None
    post_time: str | None = None
    platform: str = "instagram"
    media_type: str = "unknown"
    slide_index: int | None = None
    slide_count: int | None = None
    excluded: bool = False
    source_key: str = ""
    date_label: str = ""
    caption_type: str | None = None


@dataclass(frozen=True)
class ActionResult:
    advanced: bool = False


PlatformError = InteractionError


class EmptySearchResults(PlatformError):
    """The app explicitly confirmed that a search has no results."""
