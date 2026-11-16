"""Explicit integration of Taktik's Instagram framing engine with Phone.

This backend integration exposes semantic framing operations, never a device.
Future platform adapters normally need only Phone's public interface.
"""

from loguru import logger

from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.shared.phone_interaction._session import (
    InteractionError,
    _ExecutionAborted,
)
from taktik.core.social_media.instagram.actions.atomic.scroll import ScrollActions
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import (
    DETECTION_SELECTORS,
)


class _Facade:
    def __init__(self, phone):
        self._phone = phone
        self._device = phone._backend._transport()

    def snapshot(self):
        try:
            return ScreenSnapshot(self._phone.read("hierarchy"))
        except InteractionError as error:
            raise _ExecutionAborted(error) from error

    def get_screen_size(self):
        try:
            return self._phone.read("size")
        except InteractionError as error:
            raise _ExecutionAborted(error) from error

    def human_tap(self, bounds, **kwargs):
        try:
            return self._phone.tap(
                bounds, kind="immediate" if kwargs.get("quick") else "tap"
            ).require()
        except InteractionError as error:
            raise _ExecutionAborted(error) from error

    def back(self):
        try:
            self._phone.command("back").require()
        except InteractionError as error:
            raise _ExecutionAborted(error) from error


class _IntegratedScroll(ScrollActions):
    def __init__(self, phone):
        # BaseAction constructs a global HumanBehavior singleton and permissive
        # forwarding facade. This integration supplies only the capabilities used.
        self._phone = phone
        self.device = _Facade(phone)
        self.logger = logger.bind(module="phone-instagram-framing")
        self.detection_selectors = DETECTION_SELECTORS
        self.behavior_state = phone._behavior
        self._interaction_rng = phone._rng
        self._interaction_clock = phone._clock
        self._reading_clock = phone._clock
        self._interaction_sleep = lambda seconds: phone.wait(
            seconds, purpose="readiness"
        )
        self._viewing_sleep = lambda seconds: phone.wait(seconds, purpose="viewing")

    def _tap_xpath(self, xpath):
        target = self.device.snapshot().first(xpath)
        if target is None:
            return False
        return bool(self.device.human_tap(target.bounds))

    def _reread_caption_without_xml(self, bounds):
        # Optional emoji recovery, read-only; no UiObject escapes this integration.
        from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import (
            FEED_SCROLL_SELECTORS as FS,
        )

        self._phone._check()
        raw = self._phone._backend._raw
        query = raw(className=FS.caption_layout_class)
        for index in range(min(query.count, 8)):
            info = raw(className=FS.caption_layout_class, instance=index).info
            rect = info.get("bounds") or {}
            if (
                abs(rect.get("left", -9999) - bounds[0]) <= 4
                and abs(rect.get("top", -9999) - bounds[1]) <= 4
            ):
                return info.get("text")
        return None


class HomeScroll:
    """The existing framing/recovery/reading engine on a restricted phone backend."""

    _operations = frozenset(
        {
            "land_on_post_header",
            "scroll_feed_to_next_post",
            "expand_caption_if_truncated",
            "_reframe_post_after_reading",
            "framed_post_identity",
            "show_framed_post_row_of",
            "human_reading_pause",
            "browse_carousel_slides",
        }
    )

    def __init__(self, phone):
        self._phone = phone
        self._engine = _IntegratedScroll(phone)

    @property
    def _last_reveal_scroll_px(self):
        return getattr(self._engine, "_last_reveal_scroll_px", 0)

    @_last_reveal_scroll_px.setter
    def _last_reveal_scroll_px(self, value):
        self._engine._last_reveal_scroll_px = value

    def __getattr__(self, name):
        if name not in self._operations:
            raise AttributeError(name)

        def invoke(*args, **kwargs):
            return self._phone._run(
                "taktik_" + name, lambda: getattr(self._engine, name)(*args, **kwargs)
            ).require()

        return invoke
