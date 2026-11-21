"""Explicit Taktik backend. Raw device access never leaves this package."""

from types import SimpleNamespace

from taktik.core.shared.behavior.tap import (
    free_tap_zone,
    sample_tap_point,
)
from taktik.core.shared.device.facade import BaseDeviceFacade

from ._session import InteractionError, Result, Status, _ExecutionAborted


class TaktikDevice:
    def __init__(self, device, serial):
        self._raw, self.serial = device, serial
        self._keyboard = None
        self._transport_instance = None
        self._facade_instance = None

    @classmethod
    def connect(cls, serial):
        from ._keyboard import Keyboard

        Keyboard.require_installed(serial)

        from taktik.cli.hosts.selector_platforms import register_selector_platforms
        from taktik.cli.support.language import set_language
        from taktik.core.shared.device.manager import DeviceManager

        register_selector_platforms()
        set_language("en")
        manager = DeviceManager(serial)
        if not manager.connect():
            raise InteractionError(
                "Could not connect to the configured Android device."
            )
        return cls(manager.device, serial)

    def bind(self, phone):
        from ._gestures import Gestures

        self.phone = phone
        self._gestures = Gestures(self)

    def _call(self, method, *args, **kwargs):
        self.phone._check()
        function = getattr(self._raw, method, None)
        if not callable(function):
            raise NotImplementedError(f"Device does not support {method}.")
        try:
            value = function(*args, **kwargs)
            if value is False:
                raise RuntimeError("Device rejected the operation.")
            return value
        except Exception as error:
            raise InteractionError(
                f"{method} execution is uncertain: {error}",
                result=Result(Status.UNCERTAIN, detail=f"{method}: {error}"),
            ) from error

    def read(self, what):
        if what == "size":
            return self._call("window_size")
        if what == "hierarchy":
            return self._call("dump_hierarchy")
        if what == "screenshot":
            return self._call("screenshot")
        if what == "app":
            return self._call("app_current")
        if what == "clipboard":
            try:
                return self._raw.clipboard or ""
            except Exception as error:
                raise NotImplementedError(
                    "Android clipboard read is unavailable."
                ) from error
        raise NotImplementedError(f"Unknown phone read: {what}")

    def command(self, name, value):
        if name in {"back", "home"}:
            return getattr(self._facade(), "press_" + name)()
        if name == "enter":
            return self._call("press", name)
        if name in {"launch", "stop"}:
            if name == "launch":
                self._require_pinned_app(value)
            return self._call("app_start" if name == "launch" else "app_stop", value)
        if name == "open_url":
            package, url = value
            self._require_pinned_app(package)
            return self.shell(
                [
                    "am",
                    "start",
                    "-W",
                    "-a",
                    "android.intent.action.VIEW",
                    "-d",
                    url,
                    package,
                ]
            )
        raise NotImplementedError(f"Unknown Android command: {name}")

    def _require_pinned_app(self, package):
        from taktik.core.shared.device.app_versions import (
            AppVersionRefused,
            require_pinned_app_version,
        )

        try:
            require_pinned_app_version(self.serial, package)
        except AppVersionRefused as error:
            # A preflight refusal means no mutation ran, not uncertain execution.
            raise InteractionError(str(error)) from error

    def shell(self, args):
        reply = self._call("shell", args, timeout=10)
        if reply.exit_code != 0:
            raise InteractionError("Android command failed: " + reply.output.strip())
        return reply.output

    def zone(self, bounds, exclude=()):
        w, h = self.read("size")
        left, top, right, bottom = bounds
        clipped = (max(0, int(left)), max(0, int(top)), min(w, int(right)), min(h, int(bottom)))
        if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
            raise InteractionError("Target has no usable on-screen area.")
        zone = free_tap_zone(clipped, exclude)
        if zone is None:
            raise InteractionError("Excluded controls leave no usable touch region.")
        return zone

    def beat(self, gesture):
        return self.phone._behavior.plan_directional_gesture(
            context="phone_" + gesture, gesture=gesture
        )

    def tap(self, target, exclude, kind):
        zone = self.zone(target, exclude)
        self.beat(kind)
        if kind in {"tap", "immediate"}:
            if kind == "tap" and not callable(getattr(self._raw, "long_click", None)):
                raise NotImplementedError(
                    "Variable-contact taps require long_click support."
                )
            point = self._facade().human_tap(
                zone, rng=self.phone._rng, quick=kind == "immediate"
            )
        elif kind == "long_press":
            point = sample_tap_point(zone, rng=self.phone._rng)
            self._facade().long_click(*point)
        elif kind == "double_tap":
            point = self._facade().human_double_tap(zone, rng=self.phone._rng)
        else:
            raise NotImplementedError("Unknown tap intent: " + kind)
        if point is None:
            raise InteractionError("Taktik could not execute the requested tap.")
        self.phone._emit(kind + "_geometry", point=point, bounds=zone)
        return point

    def _transport(self):
        if self._transport_instance is not None:
            return self._transport_instance
        backend = self

        class Transport:
            def get_screen_size(self):
                return backend.read("size")

            def __getattr__(self, name):
                if name not in {
                    "long_click",
                    "click",
                    "double_click",
                    "press",
                    "swipe",
                    "swipe_points",
                    "window_size",
                }:
                    raise AttributeError(name)

                def invoke(*args, **kwargs):
                    try:
                        return backend._call(name, *args, **kwargs)
                    except InteractionError as error:
                        raise _ExecutionAborted(error) from error
                    except NotImplementedError as error:
                        raise _ExecutionAborted(
                            InteractionError(
                                str(error),
                                result=Result(Status.UNSUPPORTED, detail=str(error)),
                            )
                        ) from error

                return invoke

        self._transport_instance = Transport()
        return self._transport_instance

    def _facade(self):
        if self._facade_instance is None:
            self._facade_instance = BaseDeviceFacade(self._transport())
        return self._facade_instance

    def gesture(self, intent, direction, region, distance, exclude):
        region = self.zone(region)
        if distance is None:
            distance = (
                (region[2] - region[0]) * 0.65
                if intent == "horizontal"
                else (region[3] - region[1]) * (0.6 if intent == "page" else 0.4)
            )
        return self._gestures.perform(
            intent, direction, self.zone(region, exclude), distance
        )

    def drag(self, start, end, region):
        return self._gestures.drag(start, end, self.zone(region))

    def enter_text(self, field, text, submit):
        from ._keyboard import Keyboard

        if self._keyboard is None:
            self._keyboard = Keyboard(self)
        return self._keyboard.enter(field, text, submit)

    def field(self, resource_id):
        self.phone._check()
        query = self._raw(resourceId=resource_id)
        if query.count != 1:
            raise InteractionError("The text field is missing or ambiguous.")
        return query.info

    def close(self):
        if self._keyboard:
            self._keyboard.restore()

    def gesture_host(self):
        from loguru import logger

        from taktik.core.shared.behavior.gesture_primitives import GestureMixin

        host = GestureMixin()
        host.device = SimpleNamespace(_device=self._transport())
        host.screen_width, host.screen_height = self.read("size")
        host.logger = logger
        host._interaction_rng = self.phone._rng
        host._interaction_clock = self.phone._clock
        host._interaction_sleep = lambda seconds: self.phone.wait(
            seconds, purpose="pacing"
        )
        return host
