"""Explicit controlled travel is checked through the real Phone/backend boundary."""

import random

import pytest
from unit.shared.phone_interaction.recording import recording_session

from taktik.core.shared.behavior import gesture_primitives
from taktik.core.shared.behavior.gesture import FULL_REACH_H, sample_swipe
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    SessionExpired,
    Status,
)


@pytest.mark.parametrize(
    "region", [(0, 598, 137, 2004), (20, 350, 320, 850), (50, 136, 950, 2036)]
)
@pytest.mark.parametrize("ratio", [0.01, 0.05, 0.085, 0.09, 0.1, 0.3])
@pytest.mark.parametrize("direction", ["up", "down"])
def test_short_and_ordinary_scroll_requests_retain_exact_reach(
    region, ratio, direction
):
    left, top, right, bottom = region
    distance = (bottom - top) * ratio
    for seed in range(20):
        phone, raw, _ = recording_session(seed)
        result = phone.gesture("scroll", direction, region, distance=distance)
        if distance < 75:
            assert result.status == Status.FAILED
            assert "minimum controlled drag" in result.detail
            raw.swipe_points.assert_not_called()
            raw.swipe.assert_not_called()
            phone.close(home=False).require()
            continue
        result.require()
        raw.swipe_points.assert_called_once()
        path = raw.swipe_points.call_args.args[0]
        travel = abs(path[-1][1] - path[0][1])
        assert distance * 0.95 - 2 <= travel <= distance + 2
        assert travel >= 75
        assert (path[-1][1] < path[0][1]) == (direction == "up")
        assert all(left <= x < right and top <= y < bottom for x, y in path)
        raw.swipe.assert_not_called()
        phone.close(home=False).require()


@pytest.mark.parametrize("distance", [1, 1.5, 2.5, 24, 74.9])
def test_tap_sized_requests_fail_before_injection(distance):
    phone, raw, _ = recording_session()
    result = phone.gesture("scroll", "up", (0, 598, 137, 2004), distance=distance)
    assert result.status == Status.FAILED
    assert "minimum controlled drag" in result.detail
    raw.swipe_points.assert_not_called()
    raw.swipe.assert_not_called()


@pytest.mark.parametrize(
    "size,minimum", [((720, 1280), 41), ((1080, 2340), 75), ((1440, 3216), 103)]
)
@pytest.mark.parametrize("offset", [-0.1, 0, 0.5, 1])
def test_minimum_drag_uses_full_screen_height_and_preserves_pixel_rounding(
    size, minimum, offset
):
    for seed in range(20):
        phone, raw, _ = recording_session(seed, size)
        result = phone.gesture(
            "scroll", "up", (0, 200, 137, 700), distance=minimum + offset
        )
        if offset < 0:
            assert result.status == Status.FAILED
            raw.swipe_points.assert_not_called()
        else:
            result.require()
            path = raw.swipe_points.call_args.args[0]
            assert minimum <= abs(path[-1][1] - path[0][1]) <= minimum + offset + 2
        phone.close(home=False).require()


@pytest.mark.parametrize(
    "distance", [0, 0.5, 1, 2.5, 24, 74.9, float("nan"), float("inf")]
)
def test_direct_controlled_sampling_rejects_unrepresentable_requests(distance):
    phone, raw, _ = recording_session()
    host = phone._backend.gesture_host()
    assert not host._human_swipe(
        "up", distance_px=distance, bounds=(0, 0, 137, 1406), controlled=True
    )
    raw.swipe_points.assert_not_called()
    raw.swipe.assert_not_called()


def test_direct_controlled_sampling_rejects_a_prepared_path_below_clearance(
    monkeypatch,
):
    phone, raw, _ = recording_session()
    host = phone._backend.gesture_host()
    monkeypatch.setattr(
        host,
        "_prepare_gesture_path",
        lambda *_args, **_kwargs: [[100, 200], [100, 126]],
    )
    assert not host._human_swipe(
        "up", distance_px=75, bounds=(0, 0, 137, 1406), controlled=True
    )
    raw.swipe_points.assert_not_called()
    raw.swipe.assert_not_called()


@pytest.mark.parametrize("distance", [-1, 0, 0.5, float("nan"), float("inf"), 1200])
def test_unrepresentable_or_out_of_region_requests_fail_before_injection(distance):
    phone, raw, _ = recording_session()
    result = phone.gesture("scroll", "up", (0, 598, 137, 2004), distance=distance)
    assert result.status == Status.FAILED
    assert "travel does not fit" in result.detail
    raw.swipe_points.assert_not_called()
    raw.swipe.assert_not_called()


@pytest.mark.parametrize(
    "path,reason",
    [
        ([[100, 200], [100, 200]], "requested reach"),
        ([[100, 200], [100, 170]], "requested reach"),
        ([[100, 200], [100, 126]], "requested reach"),
        ([[400, 200], [400, 125]], "usable region"),
    ],
)
def test_pre_execution_path_rejection_keeps_its_reason(monkeypatch, path, reason):
    phone, raw, _ = recording_session()
    monkeypatch.setattr(
        gesture_primitives, "sample_swipe", lambda *_, **__: (path, 0.2)
    )
    result = phone.gesture("scroll", "up", (0, 0, 300, 500), distance=75)
    assert result.status == Status.FAILED
    assert reason in result.detail
    raw.swipe_points.assert_not_called()
    raw.swipe.assert_not_called()


def test_short_scroll_transport_uncertainty_is_not_retried():
    phone, raw, _ = recording_session()
    raw.swipe_points.side_effect = OSError("injected, reply lost")
    result = phone.gesture("scroll", "up", (0, 598, 137, 2004), distance=103.5)
    assert result.status == Status.UNCERTAIN
    raw.swipe_points.assert_called_once()
    raw.swipe.assert_not_called()
    phone.close(home=False).require()


@pytest.mark.parametrize("interruption", ["cancel", "deadline"])
def test_interruption_prevents_short_scroll_injection(interruption):
    phone, raw, _ = recording_session()
    if interruption == "cancel":
        phone.configure(cancelled=lambda: True)
    else:
        phone.configure(deadline=0)
    expected = InteractionCancelled if interruption == "cancel" else SessionExpired
    with pytest.raises(expected):
        phone.gesture("scroll", "up", (0, 598, 137, 2004), distance=103.5)
    raw.swipe_points.assert_not_called()
    phone.close(home=False).require()


@pytest.mark.parametrize(
    "controlled,distance", [(False, 103.5), (False, None), (True, None)]
)
def test_other_swipe_profiles_keep_their_original_sampled_path(controlled, distance):
    region = (0, 0, 137, 1406)
    for seed in range(20):
        phone, raw, _ = recording_session(seed)
        host = phone._backend.gesture_host()
        expected, _ = sample_swipe(
            137,
            1406,
            direction="up",
            distance_px=distance,
            dist_cap_h=FULL_REACH_H if controlled else 0.34,
            rng=random.Random(seed),
        )
        assert host._human_swipe(
            "up", distance_px=distance, bounds=region, controlled=controlled
        )
        path = raw.swipe_points.call_args.args[0]
        assert path[0] == expected[0] and path[-1] == expected[-1]
        phone.close(home=False).require()


@pytest.mark.parametrize("intent", ["page", "flick"])
def test_short_flick_and_page_keep_their_existing_floor_rejection(intent):
    phone, raw, _ = recording_session()
    result = phone.gesture(intent, "up", (0, 598, 137, 2004), distance=103.5)
    assert result.status == Status.FAILED
    assert "requested reach" in result.detail
    raw.swipe_points.assert_not_called()
    raw.swipe.assert_not_called()
