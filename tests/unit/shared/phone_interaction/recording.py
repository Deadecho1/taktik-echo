"""Shared recording for named regression scenarios."""

from unit.shared.phone_interaction.session_transport import Clock, Device

from taktik.core.shared.phone_interaction import (
    Phone,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice


def recording_session(seed=0, size=(1080, 2340)):
    raw, clock = Device(), Clock()
    raw.window_size.return_value = size
    phone = Phone(
        TaktikDevice(raw, "gesture-fixture"), seed=seed, clock=clock, sleep=clock.sleep
    )
    return phone, raw, clock
