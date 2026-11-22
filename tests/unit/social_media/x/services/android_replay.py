"""Clock and recording state for raw transports beneath real Phone execution."""

from unit.x_fixtures import SIZE


class AndroidReplay:
    def __init__(self):
        self.now = 0
        self.actions = []
        self.foreground = "com.twitter.android"

    def app_current(self):
        return {"package": self.foreground}

    def window_size(self):
        return SIZE

    def sleep(self, seconds):
        self.now += seconds
