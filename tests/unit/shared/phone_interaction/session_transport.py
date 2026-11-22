"""Shared session transport for named regression scenarios."""

import base64
from types import SimpleNamespace
from unittest.mock import Mock

from taktik.core.shared.input.taktik_keyboard import (
    TAKTIK_KEYBOARD_IME,
)


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
