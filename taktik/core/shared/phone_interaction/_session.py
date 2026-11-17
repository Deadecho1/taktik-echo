"""Session ownership, cancellation, diagnostics and the public interaction seam."""

import random
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.shared.telemetry import emit_step


class Status(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"

    def __str__(self):
        return self.value


@dataclass(frozen=True)
class Result:
    status: Status
    value: object = None
    detail: str = ""

    def require(self):
        if self.status != Status.SUCCESS:
            raise InteractionError(self.detail or self.status, result=self)
        return self.value


class InteractionError(RuntimeError):
    def __init__(self, message, *, result=None):
        super().__init__(message)
        self.result = result or Result(Status.FAILED, detail=message)


class InteractionCancelled(KeyboardInterrupt):
    """Escapes upstream recovery loops that catch Exception and retry."""


class SessionExpired(InteractionCancelled):
    pass


class _ExecutionAborted(BaseException):
    """Carry uncertain execution through upstream catch-and-fallback handlers."""

    def __init__(self, error):
        self.error = error


class Phone:
    """One running device session, with one Taktik behavior state.

    Mutations return Result; callers must require success before proceeding.
    Reads raise InteractionError. Cancellation always raises, including in compositions.
    The private backend is the only owner of the raw device.
    """

    def __init__(self, backend, *, seed=None, clock=time.monotonic, sleep=time.sleep):
        self._backend = backend
        self._clock, self._sleep = clock, sleep
        self._rng = random.Random(seed)
        self._behavior = BehaviorSessionState(seed=seed)
        self._deadline = float("inf")
        self._cancelled = lambda: False
        self._cleaning = 0
        self._closed = False
        self._diagnostic = None
        backend.bind(self)

    @classmethod
    def connect(cls, serial, **options):
        from ._device import TaktikDevice

        return cls(TaktikDevice.connect(serial), **options)

    def configure(self, *, deadline=None, cancelled=None, diagnostic=None):
        if deadline is not None:
            self._deadline = deadline
        if cancelled is not None:
            self._cancelled = cancelled
        if diagnostic is not None:
            self._diagnostic = diagnostic

    def reading_scale(self):
        """The session's attention multiplier for workflow-owned dwell planning."""
        self._check()
        return self._behavior.reading_scale(context="phone_viewing")

    def _check(self):
        if self._cleaning:
            return
        if self._closed:
            raise InteractionError("The phone session is closed.")
        if self._cancelled():
            raise InteractionCancelled("Phone session interrupted.")
        if self._clock() >= self._deadline:
            raise SessionExpired("Phone session deadline reached.")

    def _emit(self, action, **details):
        emit_step("phone", action=action, **details)
        if self._diagnostic:
            self._diagnostic(
                {"event": "phone_interaction", "action": action, **details}
            )

    def wait(self, seconds, *, purpose):
        if purpose not in {"pacing", "readiness", "viewing", "frame", "backoff"}:
            raise ValueError("A wait must declare its purpose.")
        self._check()
        remaining = max(0.0, float(seconds))
        while remaining > 0:
            self._check()
            chunk = min(remaining, 0.1)
            if not self._cleaning:
                chunk = min(chunk, max(0, self._deadline - self._clock()))
            self._sleep(chunk)
            remaining -= chunk
        self._check()

    @contextmanager
    def cleanup(self):
        """Permit narrowly scoped restoration even after cancellation or expiry."""
        self._cleaning += 1
        try:
            yield
        finally:
            self._cleaning -= 1

    def _run(self, action, operation):
        started = self._clock()
        try:
            self._check()
            value = operation()
            result = Result(Status.SUCCESS, value)
        except _ExecutionAborted as abort:
            result = abort.error.result
        except InteractionError as error:
            result = error.result
        except NotImplementedError as error:
            result = Result(Status.UNSUPPORTED, detail=str(error))
        except Exception as error:  # noqa: BLE001 - The interface reports transport uncertainty.
            result = Result(
                Status.UNCERTAIN, detail=f"{action}: {type(error).__name__}: {error}"
            )
        except KeyboardInterrupt:
            self._emit(action, status="cancelled", seconds=self._clock() - started)
            raise
        self._emit(
            action,
            status=result.status,
            seconds=self._clock() - started,
            detail=result.detail,
        )
        return result

    def read(self, what):
        """Read screenshot, hierarchy, screen_reader_hierarchy, size, clipboard or app."""
        return self._run("read_" + what, lambda: self._backend.read(what)).require()

    def command(self, name, value=None):
        """Android back/home/enter, launch, stop, or a package-scoped VIEW intent."""
        return self._run(name, lambda: self._backend.command(name, value))

    def tap(self, target, *, exclude=(), kind="tap"):
        """Tap bounded geometry; kind is tap, immediate, long_press, or double_tap."""
        return self._run(kind, lambda: self._backend.tap(target, exclude, kind))

    def gesture(self, intent, direction, region, *, distance=None, exclude=()):
        """Finger direction; intent is scroll, flick, page, or horizontal.

        Distance is pixels along the movement axis. Page enforces pager reach;
        scroll tracks the finger without coast. Region excludes chrome and controls.
        """
        return self._run(
            intent,
            lambda: self._backend.gesture(intent, direction, region, distance, exclude),
        )

    def drag(self, start, end, *, region):
        """Precise displacement between bounded endpoints, with no momentum."""
        return self._run("drag", lambda: self._backend.drag(start, end, region))

    def enter_text(self, field, text, *, submit=None):
        """Focus a resource ID or scoped TextField, type and verify exactly.

        A callable submission resolves the current platform control after verification.
        No submission takes place after partial input, failed verification or cancellation.
        """
        return self._run(
            "text_entry", lambda: self._backend.enter_text(field, text, submit)
        )

    def close(self, *, home=True):
        if self._closed:
            return Result(Status.SUCCESS)
        with self.cleanup():
            result = self._run("keyboard_restore", self._backend.close)
            home_result = self.command("home") if home else Result(Status.SUCCESS)
        if result.status == home_result.status == Status.SUCCESS:
            self._closed = True
        return result if result.status != Status.SUCCESS else home_result
