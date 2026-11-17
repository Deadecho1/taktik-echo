from unittest.mock import Mock

import pytest
from taktik.core.shared.phone_interaction import InteractionError
from taktik.core.shared.phone_interaction._keyboard import Keyboard


@pytest.mark.parametrize(
    "reason", ["device not found", "device offline", "device unauthorized"]
)
def test_keyboard_check_preserves_connection_failure(monkeypatch, reason):
    import adbutils

    device = Mock()
    device.shell.side_effect = RuntimeError(reason)
    monkeypatch.setattr(adbutils.adb, "device", Mock(return_value=device))
    with pytest.raises(InteractionError, match=reason) as error:
        Keyboard.require_installed("missing-phone")
    assert "missing-phone" in str(error.value)
    assert "Install" not in str(error.value)


def test_connected_phone_without_keyboard_still_gets_install_guidance(monkeypatch):
    import adbutils

    device = Mock()
    device.shell.return_value = "user/.Keyboard\n"
    monkeypatch.setattr(adbutils.adb, "device", Mock(return_value=device))
    with pytest.raises(InteractionError, match="Install"):
        Keyboard.require_installed("connected-phone")


@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_keyboard_check_preserves_subprocess_failure(monkeypatch, failure):
    import subprocess
    import sys

    from taktik.core.shared.device import adb

    monkeypatch.setitem(sys.modules, "adbutils", None)
    run = Mock()
    if failure == "exit":
        run.return_value = subprocess.CompletedProcess([], 1, "", "device offline")
        reason = "device offline"
    else:
        run.side_effect = subprocess.TimeoutExpired("adb", 10)
        reason = "timed out"
    monkeypatch.setattr(adb.subprocess, "run", run)
    with pytest.raises(InteractionError, match=reason):
        Keyboard.require_installed("missing-phone")
    assert adb.run_adb_shell("missing-phone", ["ime", "list"]) == ""
