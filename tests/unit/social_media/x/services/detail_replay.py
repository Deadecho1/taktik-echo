"""Shared detail replay for named regression scenarios."""

from unit.social_media.x.services.detail_inputs import document
from unit.social_media.x.services.inspection_replay import InspectionReplay


class MainReplay(InspectionReplay):
    def __init__(self):
        super().__init__()
        self.results = self.latest = document("image-source")
        self.restored = document("image-return")
        self.detail = document("image-ordinary")
        self.native = document("image-main")
        self.native_error = None
        self.native_reads = 0

    def read(self, what):
        if what == "screen_reader_hierarchy":
            self.native_reads += 1
            if self.native_error:
                raise self.native_error
            return self.native
        return super().read(what)
