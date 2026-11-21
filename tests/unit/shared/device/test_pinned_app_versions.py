"""No phone mutation may start automation on an app version outside its pins."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from taktik.core.shared.device import app_inspection
from taktik.core.shared.device.app_manager import AppService
from taktik.core.shared.device.app_versions import (
    AppVersionRefused,
    require_pinned_app_version,
)
from taktik.core.shared.device.apps import APPS, PINNED_VERSIONS
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.shared.phone_interaction import Phone, Status
from taktik.core.shared.phone_interaction._device import TaktikDevice


def test_phone_refuses_updated_tiktok_before_launch(monkeypatch):
    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "47.7.3")
    raw = Mock()
    phone = Phone(TaktikDevice(raw, "SERIAL"))

    result = phone.command("launch", "com.zhiliaoapp.musically")

    assert result.status == Status.FAILED
    assert "47.7.3" in result.detail
    assert "43.1.4" in result.detail and "47.0.3" in result.detail
    raw.app_start.assert_not_called()


def test_manager_refuses_unknown_version_before_stopping_or_launching(monkeypatch):
    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: None)
    manager = DeviceManager("SERIAL")
    manager.device = Mock()

    with pytest.raises(RuntimeError, match="version.*unverified|[Cc]annot verify"):
        manager.launch_app("com.instagram.android", stop_first=True)

    manager.device.app_start.assert_not_called()
    manager.device.app_stop.assert_not_called()


@pytest.mark.parametrize("platform,version", [
    (platform, version) for platform, versions in PINNED_VERSIONS.items() for version in versions
])
def test_every_declared_pin_is_accepted_exactly(monkeypatch, platform, version):
    read = Mock(return_value=version)
    monkeypatch.setattr(app_inspection, "get_installed_app_version", read)
    package = APPS[platform]["package"]
    assert require_pinned_app_version("SERIAL", package) == version
    read.assert_called_once_with("SERIAL", package, platform)


@pytest.mark.parametrize("platform,version", [
    ("tiktok", "47.7.3"), ("tiktok", "47.6.3"), ("tiktok", "47.0.4"),
    ("tiktok", "43.1.3"), ("tiktok", "47.0.3-beta"),
    ("instagram", "456.1.0.56.78"), ("instagram", "447.0.0.55.82"),
    ("instagram", "410.0.0.53.70"), ("instagram", "447"),
])
def test_nearby_newer_older_and_family_versions_are_refused(monkeypatch, platform, version):
    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: version)
    with pytest.raises(AppVersionRefused, match="Unsupported") as caught:
        require_pinned_app_version("SERIAL", APPS[platform]["package"])
    assert version in str(caught.value)
    assert all(pin in str(caught.value) for pin in PINNED_VERSIONS[platform])
    assert "disable automatic updates" in str(caught.value)


@pytest.mark.parametrize("version", [None, "", RuntimeError("ADB unavailable")])
def test_unreadable_version_never_uses_a_cached_value(monkeypatch, version):
    read = Mock(side_effect=["47.0.3", version])
    monkeypatch.setattr(app_inspection, "get_installed_app_version", read)
    assert require_pinned_app_version("SERIAL", APPS["tiktok"]["package"]) == "47.0.3"
    with pytest.raises(AppVersionRefused, match="Cannot verify"):
        require_pinned_app_version("SERIAL", APPS["tiktok"]["package"])


def test_updated_version_is_rechecked_on_the_same_phone(monkeypatch):
    read = Mock(side_effect=["47.0.3", "47.7.3"])
    monkeypatch.setattr(app_inspection, "get_installed_app_version", read)
    phone = Phone(TaktikDevice(Mock(), "SERIAL"))
    assert phone.command("launch", APPS["tiktok"]["package"]).status == Status.SUCCESS
    assert phone.command("launch", APPS["tiktok"]["package"]).status == Status.FAILED
    phone._backend._raw.app_start.assert_called_once()


@pytest.mark.parametrize("platform", sorted(set(APPS) - set(PINNED_VERSIONS)))
def test_every_app_without_pins_is_refused_before_device_access(monkeypatch, platform):
    read = Mock()
    monkeypatch.setattr(app_inspection, "get_installed_app_version", read)
    with pytest.raises(AppVersionRefused, match="No exact version pins"):
        require_pinned_app_version("SERIAL", APPS[platform]["package"])
    read.assert_not_called()


@pytest.mark.parametrize("package,platform,version", [
    ("com.ss.android.ugc.trill", "tiktok", "47.0.3"),
    ("com.taktik.tt2", "tiktok", "47.0.3"),
    ("com.taktik.ig1", "instagram", "447.0.0.55.81"),
])
def test_variants_and_clones_check_the_actual_package(monkeypatch, package, platform, version):
    read = Mock(return_value=version)
    monkeypatch.setattr(app_inspection, "get_installed_app_version", read)
    assert require_pinned_app_version("SERIAL", package) == version
    read.assert_called_once_with("SERIAL", package, platform)


def test_unknown_packages_are_not_silently_authorized():
    with pytest.raises(AppVersionRefused, match="No exact version pins"):
        require_pinned_app_version("SERIAL", "com.example.unregistered")


@pytest.mark.parametrize("serial", [None, "", " "])
def test_a_missing_serial_never_checks_another_phone(monkeypatch, serial):
    read = Mock(return_value="47.0.3")
    monkeypatch.setattr(app_inspection, "get_installed_app_version", read)
    with pytest.raises(AppVersionRefused, match="without a device serial"):
        require_pinned_app_version(serial, APPS["tiktok"]["package"])
    read.assert_not_called()


def test_package_scoped_url_cannot_bypass_the_pin(monkeypatch):
    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "47.7.3")
    raw = Mock()
    phone = Phone(TaktikDevice(raw, "SERIAL"))
    result = phone.command("open_url", (APPS["tiktok"]["package"], "https://www.tiktok.com/"))
    assert result.status == Status.FAILED
    raw.shell.assert_not_called()


def test_cleanup_remains_available_after_a_version_refusal(monkeypatch):
    read = Mock(return_value="47.7.3")
    monkeypatch.setattr(app_inspection, "get_installed_app_version", read)
    raw = Mock()
    phone = Phone(TaktikDevice(raw, "SERIAL"))
    assert phone.command("launch", APPS["tiktok"]["package"]).status == Status.FAILED
    assert phone.command("stop", APPS["tiktok"]["package"]).status == Status.SUCCESS
    assert phone.command("home").status == Status.SUCCESS
    raw.app_stop.assert_called_once_with(APPS["tiktok"]["package"])
    raw.press.assert_called_once_with("home")
    assert read.call_count == 1


@pytest.mark.parametrize("action", ["launch", "restart"])
def test_app_service_refuses_before_startup_or_stop(monkeypatch, action):
    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "47.7.3")
    manager = Mock()
    service = AppService(SimpleNamespace(device_id="SERIAL", device_manager=manager), "tiktok")
    with pytest.raises(AppVersionRefused, match="47.7.3"):
        getattr(service, action)()
    manager.launch_app.assert_not_called()
    manager.stop_app.assert_not_called()


def test_tiktok_manager_restart_refuses_before_stopping(monkeypatch):
    from taktik.core.social_media.tiktok.manager import TikTokManager

    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "47.7.3")
    manager = TikTokManager("SERIAL")
    manager._detected_package = APPS["tiktok"]["package"]
    manager.device_manager = Mock(device_id="SERIAL")
    with pytest.raises(AppVersionRefused, match="47.7.3"):
        manager.restart()
    manager.device_manager.stop_app.assert_not_called()
    manager.device_manager.device.app_start.assert_not_called()


@pytest.mark.parametrize("action", ["launch", "restart"])
def test_threads_without_pins_refuses_before_any_launch(action):
    from taktik.core.social_media.threads.core.manager import ThreadsManager

    manager = ThreadsManager("SERIAL")
    manager.device_manager = Mock(device_id="SERIAL")
    with pytest.raises(AppVersionRefused, match="No exact version pins"):
        getattr(manager, action)()
    manager.device_manager.device.shell.assert_not_called()
    manager.device_manager.stop_app.assert_not_called()


@pytest.mark.parametrize("app", ["gmail", "youtube", "youtube_account"])
def test_direct_workflow_without_pins_is_refused_before_any_work(app):
    from taktik.core.social_media.gmail.workflows.account import GmailWorkflow
    from taktik.core.social_media.youtube.workflows.account.account_workflow import (
        YouTubeAccountWorkflow,
    )
    from taktik.core.social_media.youtube.workflows.publish.upload_workflow import (
        YouTubeUploadWorkflow,
    )

    raw = Mock()
    with pytest.raises(AppVersionRefused, match="No exact version pins"):
        {"gmail": GmailWorkflow, "youtube": YouTubeUploadWorkflow,
         "youtube_account": YouTubeAccountWorkflow}[app](raw, "SERIAL")
    assert raw.mock_calls == []


def test_instagram_publish_refuses_before_building_device_actions(monkeypatch):
    from taktik.core.social_media.instagram.workflows.publish.post_workflow import (
        InstagramPostWorkflow,
    )

    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "456.1.0.56.78")
    raw = Mock()
    with pytest.raises(AppVersionRefused, match="456.1.0.56.78"):
        InstagramPostWorkflow(raw, "SERIAL", package_name=APPS["instagram"]["package"])
    assert raw.mock_calls == []


def test_tiktok_upload_refuses_before_pushing_or_purging_media(monkeypatch, tmp_path):
    from taktik.core.social_media.tiktok.workflows.publish import upload_workflow

    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "47.7.3")
    purge = Mock()
    monkeypatch.setattr(upload_workflow, "purge_pushed_media", purge)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    with pytest.raises(AppVersionRefused, match="47.7.3"):
        upload_workflow.TikTokUploadWorkflow(Mock(), "SERIAL").execute(
            str(clip), package_name=APPS["tiktok"]["package"]
        )
    purge.assert_not_called()


def test_tiktok_text_publish_refuses_before_first_tap(monkeypatch):
    from taktik.core.social_media.tiktok.services.publish.text_post import (
        publish_text_post,
    )

    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "47.7.3")
    raw = Mock()
    tap = Mock(return_value=False)
    with pytest.raises(AppVersionRefused, match="47.7.3"):
        publish_text_post(raw, "SERIAL", "test", click=tap)
    tap.assert_not_called()
    assert raw.mock_calls == []


@pytest.mark.parametrize("action", ["launch", "restart"])
def test_tiktok_runtime_refusal_never_falls_back_to_another_launcher(monkeypatch, action):
    from taktik.core.social_media.tiktok.services.runtime import app_control

    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "47.7.3")
    run = Mock()
    raw = Mock()
    with pytest.raises(AppVersionRefused, match="47.7.3"):
        if action == "launch":
            app_control.launch_app_non_blocking("SERIAL", APPS["tiktok"]["package"], run=run)
        else:
            app_control.restart_tiktok_package(raw, "SERIAL", APPS["tiktok"]["package"])
    run.assert_not_called()
    assert raw.mock_calls == []


@pytest.mark.parametrize("failed_command", ["pm", "dumpsys"])
def test_failed_adb_with_plausible_stdout_cannot_authorize_a_version(monkeypatch, failed_command):
    package = APPS["tiktok"]["package"]

    def shell(serial, args, **kwargs):
        return SimpleNamespace(
            returncode=1 if args[0] == failed_command else 0,
            stdout=f"package:{package}\n" if args[0] == "pm" else "versionName=47.0.3\n",
        )

    monkeypatch.setattr(app_inspection, "run_adb_shell_process", shell)
    with pytest.raises(AppVersionRefused, match="Cannot verify"):
        require_pinned_app_version("SERIAL", package)
