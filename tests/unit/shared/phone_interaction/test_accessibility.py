"""Native reader ownership, restoration, and uncertainty through the real Phone."""

import base64
import hashlib
import json
import re
from types import SimpleNamespace

import pytest
from unit.paths import CORE

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    SessionExpired,
    Status,
)
from taktik.core.shared.phone_interaction._accessibility import _decode
from taktik.core.shared.phone_interaction._device import TaktikDevice

XML = '<hierarchy rotation="0"><node package="fixture"/></hierarchy>'


class NativeDevice:
    def __init__(self):
        self._process = object()
        self.events = []
        self.config = {"waitForIdleTimeout": 321, "waitForSelectorTimeout": 123}
        self.jsonrpc = SimpleNamespace(
            getConfigurator=lambda: self.config.copy(),
            setConfigurator=self.restore_config,
        )
        self.adb_device = SimpleNamespace(sync=SimpleNamespace(push=self.push))
        self.output = "TAKTIK_HIERARCHY_V1:" + base64.b64encode(XML.encode()).decode()
        self.native_exit = 0
        self.native_callback = lambda: None
        self.now = 0
        self.cancelled = False
        self.fail_at = None
        self.bad_config = False
        self.release_reads = 0

    def event(self, name):
        self.events.append(name)
        if self.fail_at == name:
            raise OSError(f"Transport lost at {name}")

    def push(self, local, remote, check):
        assert local.endswith("hierarchy-reader.dex") and check is True
        assert re.fullmatch(
            r"/data/local/tmp/taktik-hierarchy-[0-9a-f]{32}\.dex", remote
        )
        self.remote = remote
        self.event("push")

    def stop_uiautomator(self, *, wait):
        assert wait is False
        self._process = None
        self.event("stop")

    def start_uiautomator(self):
        self.event("start")
        self._process = object()

    def restore_config(self, config):
        self.event("restore_config")
        assert config == self.config
        return {} if self.bad_config else config

    def shell(self, command, *, timeout):
        if command == ["dumpsys", "accessibility"]:
            self.release_reads += 1
            return SimpleNamespace(
                exit_code=0, output="" if self.release_reads > 1 else "Ui Automation["
            )
        if isinstance(command, str):
            assert self._process is None
            assert (
                command
                == f"CLASSPATH={self.remote}:/data/local/tmp/u2.jar app_process / taktik.phone.HierarchyReader"
            )
            self.event("native")
            self.native_callback()
            return SimpleNamespace(exit_code=self.native_exit, output=self.output)
        assert command == ["rm", "-f", self.remote]
        self.event("remove")
        return SimpleNamespace(exit_code=0, output="")

    def sleep(self, duration):
        self.now += duration


def session():
    raw = NativeDevice()
    phone = Phone(
        TaktikDevice(raw, "native-fixture"), clock=lambda: raw.now, sleep=raw.sleep
    )
    phone.configure(cancelled=lambda: raw.cancelled)
    return raw, phone


def test_read_restores_reader_configuration_before_returning_native_xml():
    raw, phone = session()
    assert phone.read("screen_reader_hierarchy") == XML
    assert raw.events == ["push", "stop", "native", "start", "restore_config", "remove"]
    assert raw._process is not None and raw.release_reads == 3


def test_read_requires_ownership_without_interfering_with_another_server():
    raw, phone = session()
    raw._process = None
    with pytest.raises(InteractionError) as error:
        phone.read("screen_reader_hierarchy")
    assert error.value.result.status == Status.UNSUPPORTED
    assert raw.events == []


@pytest.mark.parametrize(
    "failure", ["push", "stop", "native", "start", "restore_config", "remove"]
)
def test_transport_failure_is_uncertain_and_is_never_retried(failure):
    raw, phone = session()
    raw.fail_at = failure
    with pytest.raises(InteractionError) as error:
        phone.read("screen_reader_hierarchy")
    assert error.value.result.status == Status.UNCERTAIN
    assert raw.events.count(failure) == 1
    assert raw.events[-1] == "remove"
    if failure in {"stop", "native"}:
        assert raw.events[-3:] == ["start", "restore_config", "remove"]
    if failure == "push":
        assert "stop" not in raw.events


@pytest.mark.parametrize("failure", ["native_exit", "bad_payload", "bad_config"])
def test_reported_failure_never_returns_a_hierarchy(failure):
    raw, phone = session()
    if failure == "native_exit":
        raw.native_exit = 1
    elif failure == "bad_payload":
        raw.output = "missing hierarchy"
    else:
        raw.bad_config = True
    with pytest.raises(InteractionError):
        phone.read("screen_reader_hierarchy")
    assert raw.events[-3:] == ["start", "restore_config", "remove"]


@pytest.mark.parametrize("expired", [False, True])
def test_cancellation_during_native_read_restores_the_server_and_removes_the_asset(
    expired,
):
    raw, phone = session()
    if expired:
        phone.configure(deadline=1)
        raw.native_callback = lambda: setattr(raw, "now", 2)
    else:
        raw.native_callback = lambda: setattr(raw, "cancelled", True)
    with pytest.raises(SessionExpired if expired else InteractionCancelled):
        phone.read("screen_reader_hierarchy")
    assert raw.events[-3:] == ["start", "restore_config", "remove"]


@pytest.mark.parametrize("failure", ["start", "restore_config", "remove", "bad_config"])
@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("raised", [False, True])
def test_cleanup_failure_preserves_cancellation_and_expiry(failure, expired, raised):
    raw, phone = session()
    expected = SessionExpired if expired else InteractionCancelled
    original = expected("Original interruption")
    if expired:
        phone.configure(deadline=1)

    def interrupt():
        if raised:
            raise original
        if expired:
            raw.now = 2
        else:
            raw.cancelled = True

    raw.native_callback = interrupt
    raw.fail_at = failure
    raw.bad_config = failure == "bad_config"
    with pytest.raises(expected) as error:
        phone.read("screen_reader_hierarchy")
    if raised:
        assert error.value is original
    assert error.value.__cause__ is not None
    assert raw.events.count("native") == 1
    assert raw.events.count("start") == 1
    assert raw.events.count("remove") == 1
    assert phone._cleaning == 0


def test_restoration_failure_does_not_downgrade_uncertain_native_execution():
    raw, phone = session()
    raw.fail_at = "native"
    raw.bad_config = True
    with pytest.raises(InteractionError) as error:
        phone.read("screen_reader_hierarchy")
    assert error.value.result.status == Status.UNCERTAIN
    assert "native" in error.value.result.detail
    assert raw.events == ["push", "stop", "native", "start", "restore_config", "remove"]


@pytest.mark.parametrize("read_failed", [False, True])
@pytest.mark.parametrize("remove_failed", [False, True])
def test_new_cancellation_during_restoration_escapes_a_prior_read_failure(
    read_failed, remove_failed
):
    raw, phone = session()
    raw.fail_at = "native" if read_failed else None
    original = InteractionCancelled("Cancelled during restoration")
    shell = raw.shell

    def cleanup_shell(command, *, timeout):
        if remove_failed and command == ["rm", "-f", raw.remote]:
            raw.events.append("remove")
            raise OSError("Cleanup transport failure")
        return shell(command, timeout=timeout)

    def interrupt():
        raw.events.append("start")
        raise original

    raw.start_uiautomator = interrupt
    raw.shell = cleanup_shell
    with pytest.raises(InteractionCancelled) as error:
        phone.read("screen_reader_hierarchy")
    assert error.value is original
    assert raw.events == ["push", "stop", "native", "start", "remove"]
    assert phone._cleaning == 0


@pytest.mark.parametrize(
    "payload", ["", "garbage", "TAKTIK_HIERARCHY_V1:!", "TAKTIK_HIERARCHY_V1:eA=="]
)
def test_invalid_native_payload_is_rejected(payload):
    with pytest.raises(InteractionError):
        _decode(payload)


@pytest.mark.parametrize(
    "xml",
    ["<other/>", '<!DOCTYPE hierarchy [<!ENTITY x "test">]><hierarchy>&x;</hierarchy>'],
)
def test_non_hierarchy_or_doctype_is_rejected(xml):
    with pytest.raises(InteractionError):
        _decode("TAKTIK_HIERARCHY_V1:" + base64.b64encode(xml.encode()).decode())


def test_duplicate_native_responses_are_rejected():
    _, phone = session()
    raw = phone._backend._raw
    raw.output += "\n" + raw.output
    with pytest.raises(InteractionError):
        phone.read("screen_reader_hierarchy")


def test_packaged_native_asset_matches_its_source_manifest():
    native = CORE / "taktik/core/shared/phone_interaction/native"
    manifest = json.loads((native / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((native / name).read_bytes()).hexdigest() == digest
    assert (native / "hierarchy-reader.dex").read_bytes().startswith(b"dex\n")
