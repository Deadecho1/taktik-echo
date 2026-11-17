"""Field targeting and submission around Taktik's keyboard helpers."""

from taktik.core.shared.input import taktik_keyboard as keyboard

from ._session import InteractionError


class Keyboard:
    # Bound cancellation latency while letting the phone pace each chunk.
    CHUNK_SIZE = 8

    def __init__(self, backend):
        self.backend = backend
        self.restore_needed = False

    @staticmethod
    def require_installed(serial):
        try:
            available = keyboard.run_adb_shell(
                serial, ["ime", "list", "-a", "-s"], strict=True
            )
        except Exception as exc:
            raise InteractionError(
                f"Could not check Taktik Keyboard on device {serial}: {exc}"
            ) from exc
        if keyboard.TAKTIK_KEYBOARD_IME not in available.splitlines():
            raise InteractionError(
                "Taktik Keyboard is required on this phone. "
                "Install the com.alexal1.adbkeyboard APK before starting a session."
            )

    def prepare(self):
        self.backend.phone._check()
        self.require_installed(self.backend.serial)
        self.backend.phone._emit(
            "keyboard_backend",
            ime=keyboard.TAKTIK_KEYBOARD_IME,
        )
        self.restore_needed = True
        if not keyboard.ensure_taktik_keyboard(self.backend.serial):
            raise InteractionError("Taktik Keyboard could not be selected.")

    def _field(self, resource_id):
        info = self.backend.field(resource_id)
        if info.get("className") != "android.widget.EditText":
            raise InteractionError(
                "The requested control is not an editable text field."
            )
        return info

    def _require_focus(self, resource_id):
        if not self._field(resource_id).get("focused"):
            raise InteractionError("Text focus changed; nothing submitted.")

    def _wait_text(self, resource_id, expected):
        for _ in range(15):
            info = self._field(resource_id)
            if info.get("text", "") == expected:
                if not info.get("focused"):
                    raise InteractionError("Text focus changed; nothing submitted.")
                return
            self.backend.phone.wait(0.1, purpose="readiness")
        raise InteractionError(
            "Field does not contain the exact requested text; nothing submitted."
        )

    def _type(self, resource_id, text):
        phone = self.backend.phone
        if not keyboard.clear_text_with_taktik_keyboard(self.backend.serial):
            raise InteractionError("Taktik Keyboard could not clear the field.")
        phone.wait(keyboard._CLEAR_SETTLE_SECONDS, purpose="readiness")
        for start in range(0, len(text), self.CHUNK_SIZE):
            self._require_focus(resource_id)
            chunk = text[start : start + self.CHUNK_SIZE]
            try:
                ok = keyboard.type_text_human(
                    self.backend.serial, chunk, typos=True, rng=phone._rng
                )
            except KeyboardInterrupt:
                # An OS interrupt can break the helper's drain wait. Let any queued
                # characters finish before cleanup changes the keyboard or screen.
                phone._sleep(keyboard.typing_seconds(chunk) + 0.3)
                raise
            phone._check()
            if not ok:
                raise InteractionError("Taktik Keyboard did not complete text entry.")

    def enter(self, resource_id, text, submit):
        phone = self.backend.phone
        if not isinstance(text, str) or not text:
            raise InteractionError("Text entry requires a nonempty string.")
        if submit is not None and submit != "enter" and not callable(submit):
            raise NotImplementedError(
                "Text submission must be Enter or a control resolver."
            )
        self.prepare()
        rect = self._field(resource_id)["bounds"]
        self.backend.tap(
            tuple(rect[k] for k in ("left", "top", "right", "bottom")), (), "tap"
        )
        for _ in range(30):
            if self._field(resource_id).get("focused"):
                break
            phone.wait(0.1, purpose="readiness")
        else:
            raise InteractionError("The requested text field did not receive focus.")
        self._type(resource_id, text)
        self._wait_text(resource_id, text)
        phone._emit("text_verified", length=len(text))
        phone._check()
        if callable(submit):
            result = submit()
            if hasattr(result, "require"):
                result.require()
        elif submit == "enter":
            phone.command("enter").require()
        return text

    def restore(self):
        if self.restore_needed:
            if not keyboard.restore_original_keyboard(self.backend.serial):
                raise InteractionError("Taktik could not restore the user keyboard.")
            self.restore_needed = False
