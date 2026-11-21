"""Publishing behavior on an explicitly pinned build; refusals live in shared/device."""

import pytest

from taktik.core.shared.device import app_inspection


@pytest.fixture(autouse=True)
def installed_pinned_build(monkeypatch):
    monkeypatch.setattr(app_inspection, "get_installed_app_version", lambda *_: "447.0.0.55.81")
