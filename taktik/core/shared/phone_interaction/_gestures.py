"""Compose Taktik sampling and execution with usable regions and precise intent."""

from taktik.core.shared.behavior.gesture import FULL_REACH_H
from taktik.core.shared.behavior.gesture_primitives import (
    _drag_duration,
    human_drag_between_raw,
)
from taktik.core.shared.behavior.tap import sample_tap_point

from ._session import InteractionError


class Gestures:
    def __init__(self, backend):
        self.backend = backend

    def perform(self, intent, direction, zone, distance):
        backend = self.backend
        phone = backend.phone
        motor = backend.beat(intent)
        host = backend.gesture_host()
        l, t, r, b = zone
        w, h = r - l, b - t
        if intent == "horizontal":
            if direction not in {"left", "right"}:
                raise InteractionError("Horizontal paging needs left or right.")
            ratio = (distance / w) if distance is not None else 0.65
            if not 0 < ratio <= 0.75:
                raise InteractionError(
                    "Horizontal page travel does not fit its usable region."
                )
            ok = host._human_horizontal_swipe(
                direction, ratio, bounds=zone, velocity_scale=motor["velocity_scale"]
            )
            if not ok:
                raise InteractionError("Taktik horizontal paging failed.")
            return
        if intent not in {"scroll", "flick", "page"} or direction not in {"up", "down"}:
            raise NotImplementedError("Unsupported gesture intent or direction.")
        distance = (
            distance if distance is not None else h * (0.6 if intent == "page" else 0.4)
        )
        if not 0 < distance <= h * 0.8:
            raise InteractionError(
                "Requested gesture travel does not fit the usable region."
            )

        geometry = {}
        prepare = host._prepare_gesture_path

        def validate_path(path, **kwargs):
            path = prepare(path, **kwargs)
            travel = abs(path[-1][1] - path[0][1])
            if not distance * 0.95 - 2 <= travel <= distance + 2:
                raise InteractionError(
                    "Sampled gesture cannot satisfy the requested reach."
                )
            if not all(l <= x < r and t <= y < b for x, y in path):
                raise InteractionError("Sampled gesture leaves the usable region.")
            geometry.update(start=path[0], end=path[-1])
            return path

        report = host._report_gesture

        def record(action, direction, start, end, duration, **details):
            geometry["duration"] = duration
            injection = getattr(host, "_last_gesture_injection", None) or {}
            if "release_hold_min_ms" in injection:
                geometry["release_hold_min_ms"] = injection["release_hold_min_ms"]
            report(action, direction, start, end, duration, **details)

        host._prepare_gesture_path = validate_path
        host._report_gesture = record
        options = {
            "direction": direction,
            "distance_px": distance,
            "bounds": zone,
            "velocity_scale": motor["velocity_scale"],
        }
        if intent in {"page", "flick"}:
            ok = host._strong_flick(**options, dist_cap_h=FULL_REACH_H)
        else:
            ok = host._human_swipe(**options, controlled=True)
        if not ok:
            raise InteractionError("Taktik could not execute the requested gesture.")
        phone._emit("gesture_geometry", intent=intent, region=zone, **geometry)
        return geometry

    def drag(self, start, end, zone):
        backend = self.backend
        phone = backend.phone
        motor = backend.beat("drag")
        start_zone, end_zone = backend.zone(start), backend.zone(end)
        # Sample one offset and reuse it at both ends. The relative displacement is
        # exact, allowing a metadata peek and its inverse to preserve framing.
        point = sample_tap_point(start_zone, rng=phone._rng)
        dx = (end_zone[0] + end_zone[2] - start_zone[0] - start_zone[2]) / 2
        dy = (end_zone[1] + end_zone[3] - start_zone[1] - start_zone[3]) / 2
        finish = (round(point[0] + dx), round(point[1] + dy))
        if not (
            end_zone[0] <= finish[0] < end_zone[2]
            and end_zone[1] <= finish[1] < end_zone[3]
        ):
            raise InteractionError(
                "Precise drag endpoints must offer matching usable regions."
            )
        if not all(
            zone[0] <= x < zone[2] and zone[1] <= y < zone[3]
            for x, y in (point, finish)
        ):
            raise InteractionError("Precise drag leaves its usable region.")
        distance = (dx * dx + dy * dy) ** 0.5
        duration = _drag_duration(
            distance,
            tuple(v * motor["velocity_scale"] for v in (1500, 2200)),
            rng=phone._rng,
        )
        if not human_drag_between_raw(
            backend._transport(), point, finish, duration=duration
        ):
            raise NotImplementedError(
                "Precise drags require device-paced path injection."
            )
        phone._emit(
            "gesture_geometry",
            intent="drag",
            start=point,
            end=finish,
            duration=duration,
            region=zone,
        )
        return {"start": point, "end": finish}
