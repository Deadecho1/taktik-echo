"""Shared long detail replay for named regression scenarios."""

from unit.social_media.x.services.detail_inputs import document
from unit.social_media.x.services.detail_replay import MainReplay
from unit.x_fixtures import SIZE

from taktik.core.social_media.x.services.browsing.navigation import X
from taktik.core.social_media.x.ui.screen import read_screen


def started():
    replay = MainReplay()
    replay.results = replay.latest = document("long-run-source")
    replay.restored = document("long-run-return")
    replay.detail = document("long-step-0-ordinary")
    replay.native = document("long-step-0-native")
    gesture = replay.gesture
    replay.stage = 0

    def scroll(intent, direction, region, distance, exclude):
        gesture(intent, direction, region, distance, exclude)
        replay.stage += 1
        replay.xml = document(f"long-step-{replay.stage}-ordinary")
        replay.native = document(f"long-step-{replay.stage}-native")

    replay.gesture = scroll
    app = X(replay.phone)
    app.start(
        "fixture_owner",
        "search",
        query=read_screen(replay.results, SIZE).query,
        result_tab="latest",
    )
    return replay, app
