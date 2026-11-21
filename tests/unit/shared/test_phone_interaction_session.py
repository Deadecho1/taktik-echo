import base64
import shlex
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from taktik.core.shared.input import taktik_keyboard as keyboard
from taktik.core.shared.input.taktik_keyboard import (
    TAKTIK_KEYBOARD_IME,
    UIAUTOMATOR_IME,
)
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    SessionExpired,
    Status,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice

DEVICES = {}
ACTIVE_CLOCK = []


@pytest.fixture(autouse=True)
def keyboard_transport(monkeypatch):
    """Run the real Taktik helpers against the same device used by Phone."""
    DEVICES.clear()
    ACTIVE_CLOCK.clear()
    keyboard._original_ime.clear()

    def shell(serial, command, *, strict=False):
        raw, clock = DEVICES[serial]
        ACTIVE_CLOCK[:] = [clock]
        if isinstance(command, str) and command.startswith("ime=$("):
            if raw.ime != TAKTIK_KEYBOARD_IME:
                return "NOT_ON_TAKTIK_KEYBOARD " + raw.ime
            command = (
                "am broadcast "
                + command.split("then am broadcast ", 1)[1].split("; else", 1)[0]
            )
        args = shlex.split(command) if isinstance(command, str) else command
        return raw.shell(args).output

    monkeypatch.setattr(keyboard, "run_adb_shell", shell)
    monkeypatch.setattr(
        "taktik.core.shared.device.facade.time", SimpleNamespace(sleep=lambda _: None)
    )
    monkeypatch.setattr(
        keyboard,
        "time",
        SimpleNamespace(
            time=lambda: ACTIVE_CLOCK[0](), sleep=lambda s: ACTIVE_CLOCK[0].sleep(s)
        ),
    )
    yield
    keyboard._original_ime.clear()


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Device:
    def __init__(self):
        self.window_size = Mock(return_value=(1080, 2340))
        self.long_click = Mock(side_effect=lambda *_: self.info.update(focused=True))
        self.click = Mock()
        self.double_click = Mock()
        self.swipe = Mock()
        self.swipe_points = Mock()
        self.press = Mock()
        self.app_start = Mock()
        self.app_stop = Mock()
        self.ime = "user/.Keyboard"
        self.available = [self.ime, TAKTIK_KEYBOARD_IME]
        self.enabled = [self.ime]
        self.lost_text = False
        self.clear_works = True
        self.edits = []
        self.field_reads = 0
        self.info = {
            "className": "android.widget.EditText",
            "text": "old search",
            "focused": False,
            "bounds": {"left": 100, "top": 100, "right": 800, "bottom": 200},
        }
        self.shell = Mock(side_effect=self._shell)

    def __call__(self, **query):
        self.field_reads += 1
        return SimpleNamespace(count=1, info=self.info.copy(), set_text=self._set_text)

    def _set_text(self, text):
        self.edits.append(text)
        if self.lost_text or (not text and not self.clear_works):
            return False
        self.info["text"] = text

    def _shell(self, args, **kwargs):
        answer = ""
        if args[:3] == ["settings", "get", "secure"]:
            answer = self.ime
        elif args[:2] == ["ime", "list"]:
            answer = "\n".join(self.available if "-a" in args else self.enabled)
        elif args[:2] == ["ime", "set"]:
            self.ime = args[2]
            answer = f"Input method {self.ime} selected for user #0"
        elif args[:2] == ["ime", "enable"]:
            if args[2] not in self.enabled:
                self.enabled.append(args[2])
        elif args[:2] == ["ime", "disable"]:
            self.enabled.remove(args[2])
        elif args[:2] == ["am", "broadcast"]:
            action = args[args.index("-a") + 1]
            if "CLEAR_TEXT" in action:
                if self.clear_works:
                    self.info["text"] = ""
            elif not self.lost_text:
                encoded = args[args.index("--es") + 2]
                self.info["text"] += base64.b64decode(encoded).decode()
            answer = "Broadcast completed: result=-1"
        elif args[:2] == ["input", "keyevent"]:
            self.info["text"] = self.info["text"][:-1]
        return SimpleNamespace(output=answer, exit_code=0)


def session(seed=17):
    raw, clock = Device(), Clock()
    serial = f"test-device-{len(DEVICES)}"
    DEVICES[serial] = raw, clock
    phone = Phone(TaktikDevice(raw, serial), seed=seed, clock=clock, sleep=clock.sleep)
    return phone, raw, clock


def test_focus_loss_after_final_character_prevents_submission():
    phone, raw, clock = session()
    original = clock.sleep

    def sleep(seconds):
        original(seconds)
        if raw.info["text"] == "123":
            raw.info["focused"] = False

    clock.sleep = sleep
    assert phone.enter_text("search", "123", submit="enter").status == Status.FAILED
    raw.press.assert_not_called()


def test_an_already_focused_field_is_not_retapped_over_its_voice_search_button():
    phone, raw, _ = session()
    raw.info["focused"] = True

    def voice_search(*_):
        raw.info["focused"] = False
        raw.info["className"] = "android.widget.TextView"

    raw.long_click.side_effect = voice_search
    result = phone.enter_text("search", "heel pain", submit="enter")

    assert result.status == Status.SUCCESS
    raw.long_click.assert_not_called()
    assert raw.info["text"] == "heel pain"
    raw.press.assert_called_once_with("enter")


def test_cancelled_before_action_is_diagnosed_and_cleanup_remains_available():
    phone, raw, _ = session()
    events = []
    phone.configure(cancelled=lambda: True, diagnostic=events.append)
    with pytest.raises(InteractionCancelled):
        phone.tap((100, 100, 200, 200))
    assert events[-1]["status"] == "cancelled"
    raw.long_click.assert_not_called()
    phone.close().require()
    raw.press.assert_called_once_with("home")


def test_taps_are_bounded_varied_and_exclude_overlapping_controls():
    phone, raw, _ = session()
    points = [
        phone.tap((100, 100, 300, 300), exclude=[(100, 230, 300, 300)]).require()
        for _ in range(80)
    ]
    assert len(set(points)) > 50
    assert all(100 < x < 300 and 100 < y < 230 for x, y in points)
    assert all(0.03 <= call.args[2] <= 0.12 for call in raw.long_click.call_args_list)
    assert (
        phone.tap((100, 100, 300, 300), exclude=[(0, 0, 500, 500)]).status
        == Status.FAILED
    )
    assert raw.long_click.call_count == 80
    raw.click.assert_not_called()


def test_long_press_double_tap_and_immediate_have_distinct_execution():
    phone, raw, _ = session()
    target = (100, 100, 300, 300)
    phone.tap(target, kind="long_press").require()
    assert raw.long_click.call_args.args[2] == 1.0
    phone.tap(target, kind="double_tap").require()
    raw.double_click.assert_called_once()
    assert not raw.double_click.call_args.kwargs
    phone.tap(target, kind="immediate").require()
    raw.click.assert_called_once()


def test_failed_tap_never_retries_as_a_center_click():
    phone, raw, _ = session()
    raw.long_click.side_effect = OSError("disconnected after down")
    result = phone.tap((100, 100, 300, 300))
    assert result.status == Status.UNCERTAIN
    with pytest.raises(InteractionError):
        result.require()
    raw.long_click.assert_called_once()
    raw.click.assert_not_called()


def test_missing_contact_capability_is_explicit_and_never_falls_back():
    phone, raw, _ = session()
    raw.long_click = None
    assert phone.tap((100, 100, 300, 300)).status == Status.UNSUPPORTED
    raw.click.assert_not_called()


@pytest.mark.parametrize("height", [800, 1506, 2500])
def test_pager_flick_reaches_threshold_inside_image_and_clear_of_controls(height):
    phone, raw, _ = session()
    raw.window_size.return_value = (1440, 3216)
    region = (50, 160, 1100, 160 + height)
    for _ in range(30):
        phone.gesture("page", "up", region).require()
        sx, sy, ex, ey = raw.swipe.call_args.args
        assert 50 < sx < 1100 and 50 < ex < 1100
        assert 160 <= ey < sy < 160 + height
        assert 0.57 * height - 2 <= sy - ey <= 0.60 * height + 2
        assert 0.045 <= raw.swipe.call_args.kwargs["duration"] <= 0.11
    raw.swipe_points.assert_not_called()


def test_horizontal_paging_is_distinct_and_uses_the_usable_image_band():
    phone, raw, _ = session()
    for _ in range(30):
        phone.gesture("horizontal", "left", (0, 136, 900, 1500)).require()
        sx, sy, ex, ey = raw.swipe.call_args.args
        assert sx - ex > 900 * 0.55
        assert 136 < sy < 1500 and 136 < ey < 1500
        assert abs(sy - ey) < 50
        assert raw.swipe.call_args.kwargs["duration"] >= 0.16


def test_precise_drag_preserves_requested_displacement_and_does_not_fling():
    phone, raw, _ = session()
    for _ in range(10):
        phone.drag(
            (400, 1400, 500, 1440), (400, 1100, 500, 1140), region=(0, 500, 1000, 1800)
        ).require()
        path = raw.swipe_points.call_args.args[0]
        assert path[0][1] - path[-1][1] == 300
        assert path[0][0] == path[-1][0]
        assert len(path) >= 3
    raw.swipe.assert_not_called()


def test_uncertain_path_injection_is_not_repeated_with_a_fallback():
    phone, raw, _ = session()
    raw.swipe_points.side_effect = OSError("reply lost")
    result = phone.drag(
        (400, 1400, 500, 1440), (400, 1100, 500, 1140), region=(0, 500, 1000, 1800)
    )
    assert result.status == Status.UNCERTAIN
    raw.swipe_points.assert_called_once()
    raw.swipe.assert_not_called()


def test_seeds_replay_without_sharing_behavior_between_devices():
    first, _, _ = session()
    second, _, _ = session()
    assert (
        first.tap((100, 100, 300, 300)).require()
        == second.tap((100, 100, 300, 300)).require()
    )
    first.gesture("page", "up", (0, 100, 800, 1800)).require()
    assert len(first._behavior.gesture_history) == 2
    assert len(second._behavior.gesture_history) == 1
    first.enter_text("search", "hi").require()
    assert len(first._behavior.gesture_history) == 2  # The field is already focused.
    assert len(second._behavior.gesture_history) == 1


@pytest.mark.parametrize(
    "text", ["חתולים cats", "  two  spaces ", "cat 🐈 👩🏽‍🔧", "a\nb"]
)
def test_keyboard_clears_types_exact_unicode_and_restores(text):
    phone, raw, _ = session()
    phone.enter_text("search", text, submit="enter").require()
    assert raw.info["text"] == text
    raw.press.assert_called_once_with("enter")
    phone.close().require()
    assert raw.ime == "user/.Keyboard"
    assert raw.ime in raw.enabled


@pytest.mark.parametrize("problem", ["lost_text", "clear_works"])
def test_partial_or_uncleared_input_is_never_submitted(problem):
    phone, raw, _ = session()
    setattr(raw, problem, problem == "lost_text")
    result = phone.enter_text("search", "cats", submit="enter")
    assert result.status == Status.FAILED
    raw.press.assert_not_called()
    phone.close(home=False).require()
    assert raw.ime == "user/.Keyboard"


def test_cancellation_during_typing_drains_chunk_before_cleanup():
    phone, raw, clock = session()
    phone.configure(cancelled=lambda: len(raw.info["text"]) == 8)
    with pytest.raises(InteractionCancelled):
        phone.enter_text("search", "1234567890123456", submit="enter")
    assert raw.info["text"] == "12345678"
    assert clock.now >= 0.4 + keyboard.typing_seconds("12345678") + 0.15
    raw.press.assert_not_called()
    phone.close().require()
    assert raw.ime == "user/.Keyboard"
    raw.press.assert_called_once_with("home")


def test_deadline_interrupts_readiness_and_prevents_next_touch():
    phone, raw, clock = session()
    phone.configure(deadline=0.25)
    with pytest.raises(SessionExpired):
        phone.wait(10, purpose="readiness")
    assert clock() == pytest.approx(0.25)
    with pytest.raises(SessionExpired):
        phone.tap((100, 100, 300, 300))
    raw.long_click.assert_not_called()
    phone.close().require()


def test_diagnostics_report_failures_without_recording_search_text():
    phone, _, _ = session()
    diagnostic = Mock()
    phone.configure(diagnostic=diagnostic)
    phone.enter_text("search", "private text", submit="enter").require()
    assert "private text" not in repr(diagnostic.call_args_list)
    assert any(
        c.args[0]["action"] == "text_verified" for c in diagnostic.call_args_list
    )


def test_excluded_region_cannot_shorten_a_pager_below_its_advancement_threshold():
    phone, raw, _ = session()
    result = phone.gesture(
        "page", "up", (0, 100, 900, 1900), exclude=[(0, 1000, 900, 1900)]
    )
    assert result.status == Status.FAILED
    raw.swipe.assert_not_called()


def test_home_framing_integration_uses_the_session_and_propagates_uncertain_gesture():
    from pathlib import Path

    from taktik.core.social_media.instagram.services.browsing.framing import HomeScroll

    phone, raw, _ = session()
    xml = (
        Path(__file__).parent / "fixtures/framed-buttons-below-screen.xml"
    ).read_text()
    raw.dump_hierarchy = Mock(return_value=xml)
    scroll = HomeScroll(phone)
    identity = scroll.framed_post_identity()
    assert identity
    raw.swipe_points.side_effect = OSError("injected, reply lost")
    with pytest.raises(InteractionError) as error:
        scroll.show_framed_post_row_of(identity, "like")
    assert error.value.result.status == Status.UNCERTAIN
    raw.swipe_points.assert_called_once()
    raw.swipe.assert_not_called()
    assert scroll._engine.behavior_state is phone._behavior


def test_home_recovery_resolves_bounds_then_uses_shared_tap():
    from taktik.core.social_media.instagram.services.browsing.framing import HomeScroll

    phone, raw, _ = session()
    raw.dump_hierarchy = Mock(
        return_value='<hierarchy><node text="Back" bounds="[20,100][120,200]"/></hierarchy>'
    )
    scroll = HomeScroll(phone)
    assert scroll._engine._tap_xpath('//*[@text="Back"]')
    x, y, duration = raw.long_click.call_args.args
    assert 20 < x < 120 and 100 < y < 200
    assert duration < 0.12
    raw.click.assert_not_called()


def test_home_read_failure_cannot_fall_through_to_a_recovery_swipe():
    from taktik.core.social_media.instagram.services.browsing.framing import HomeScroll

    phone, raw, _ = session()
    raw.dump_hierarchy = Mock(side_effect=OSError("read disconnected"))
    with pytest.raises(InteractionError) as error:
        HomeScroll(phone).scroll_feed_to_next_post()
    assert error.value.result.status == Status.UNCERTAIN
    raw.swipe.assert_not_called()
    raw.swipe_points.assert_not_called()


def test_home_requested_viewing_uses_session_clock_and_viewing_wait():
    from taktik.core.social_media.instagram.services.browsing.framing import HomeScroll

    phone, raw, clock = session()
    raw.dump_hierarchy = Mock(return_value="<hierarchy />")
    phone.wait = Mock(wraps=phone.wait)
    elapsed = HomeScroll(phone).human_reading_pause(
        dwell_s=2, read_captions=False, browse_carousels=False
    )
    assert elapsed == 2
    assert clock.now == pytest.approx(2)
    phone.wait.assert_called_once_with(2, purpose="viewing")


@pytest.mark.parametrize("available", [[], [UIAUTOMATOR_IME]])
def test_missing_taktik_keyboard_fails_before_touching_the_app(available):
    phone, raw, _ = session()
    raw.available = [raw.ime, *available]
    result = phone.enter_text("search", "cats", submit="enter")
    assert result.status == Status.FAILED
    assert "Taktik Keyboard is required" in result.detail
    raw.long_click.assert_not_called()
    raw.press.assert_not_called()
    assert raw.edits == []
    assert raw.ime == "user/.Keyboard"


def test_chunks_use_real_taktik_pacing_without_per_character_field_reads():
    phone, raw, clock = session()
    phone.enter_text("search", "123456789012345678901234", submit="enter").require()
    broadcasts = [
        call.args[0]
        for call in raw.shell.call_args_list
        if call.args[0][:2] == ["am", "broadcast"] and "ADB_INPUT_B64" in call.args[0]
    ]
    assert len(broadcasts) == 3
    assert all(args[args.index("delay_mean") + 1] == "80" for args in broadcasts)
    assert all(args[args.index("delay_deviation") + 1] == "30" for args in broadcasts)
    assert raw.field_reads <= 7
    assert raw.edits == []
    assert clock.now >= 3 * (keyboard.typing_seconds("12345678") + 0.15)


def test_taktik_typos_are_enabled_and_corrected_before_submission():
    phone, raw, _ = session(seed=1)
    query = "abcdefghijklmnopqrstuvwxyz" * 2
    phone.enter_text("search", query, submit="enter").require()
    assert any(
        call.args[0][:2] == ["input", "keyevent"] for call in raw.shell.call_args_list
    )
    assert raw.info["text"] == query
    raw.press.assert_called_once_with("enter")


def test_os_interrupt_drains_pending_input_before_restoring_keyboard():
    phone, raw, clock = session()
    original = clock.sleep

    def interrupt_wait(seconds):
        if raw.info["text"] == "12345678":
            raise KeyboardInterrupt
        original(seconds)

    clock.sleep = interrupt_wait
    with pytest.raises(KeyboardInterrupt):
        phone.enter_text("search", "1234567890123456", submit="enter")
    assert clock.now >= 0.4 + keyboard.typing_seconds("12345678") + 0.3
    assert raw.info["text"] == "12345678"
    raw.press.assert_not_called()
    phone.close().require()
    assert raw.ime == "user/.Keyboard"


def test_final_verification_rejects_whitespace_normalization():
    phone, raw, _ = session()
    original = raw._shell

    def normalize(args, **kwargs):
        result = original(args, **kwargs)
        if "ADB_INPUT_B64" in args:
            raw.info["text"] = " ".join(raw.info["text"].split())
        return result

    raw.shell.side_effect = normalize
    assert phone.enter_text("search", "a  b", submit="enter").status == Status.FAILED
    raw.press.assert_not_called()


def test_keyboard_preflight_prevents_connecting_an_unprepared_phone(monkeypatch):
    phone, raw, _ = session()
    raw.available = [raw.ime]
    manager = Mock()
    monkeypatch.setattr("taktik.core.shared.device.manager.DeviceManager", manager)
    with pytest.raises(InteractionError, match="Taktik Keyboard is required"):
        Phone.connect(phone._backend.serial)
    manager.assert_not_called()
