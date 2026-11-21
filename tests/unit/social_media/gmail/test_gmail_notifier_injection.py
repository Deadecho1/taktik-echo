import pytest

from taktik.core.shared.device import app_inspection, apps
from taktik.core.social_media.gmail.workflows.account import GmailWorkflow


@pytest.fixture(autouse=True)
def pinned_test_build(monkeypatch):
    monkeypatch.setitem(apps.PINNED_VERSIONS, "gmail", ("test-build",))
    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "test-build")


class _FakeNotifier:
    def __init__(self):
        self.status_calls = []
        self.log_calls = []

    def status(self, status: str, message: str = "") -> None:
        self.status_calls.append((status, message))

    def log(self, level: str, message: str) -> None:
        self.log_calls.append((level, message))


class _FakeDevice:
    def app_start(self, *args, **kwargs):
        return None


def test_gmail_workflow_uses_injected_notifier(monkeypatch):
    notifier = _FakeNotifier()
    workflow = GmailWorkflow(_FakeDevice(), "device-1", notifier=notifier)

    monkeypatch.setattr(
        workflow,
        "_switch_to_account",
        lambda email: {"success": False, "message": "missing", "error_type": "missing"},
    )

    result = workflow.get_latest_verification_code("user@example.com")

    assert result["success"] is False
    assert notifier.status_calls == [("running", "Waiting for verification email…")]
    assert notifier.log_calls == []


def test_gmail_workflow_without_notifier_stays_callable(monkeypatch):
    workflow = GmailWorkflow(_FakeDevice(), "device-2")

    monkeypatch.setattr(
        workflow,
        "_switch_to_account",
        lambda email: {"success": False, "message": "missing", "error_type": "missing"},
    )

    result = workflow.get_latest_verification_code("user@example.com")

    assert result["success"] is False
