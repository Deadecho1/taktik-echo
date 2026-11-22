"""Shared feedback visibility replay for named regression scenarios."""

from lxml import etree
from unit.scripts.eval.feedback_replay import FeedbackReplay, document

from taktik.core.social_media.x.ui.screen import _rect


def translated(xml, bounds, offset):
    root = etree.fromstring(xml.encode())
    container = root.xpath(".//*[@bounds=$bounds]", bounds=bounds)[0]
    for node in container.iter():
        if node.get("bounds"):
            left, top, right, bottom = _rect(node)
            node.set("bounds", f"[{left},{top + offset}][{right},{bottom + offset}]")
    return etree.tostring(root, encoding="unicode")


def source_document(offset):
    root = etree.fromstring(document("source").encode())
    quote = root.xpath('.//*[@bounds="[176,1359][1047,2235]"]')[0]
    quote.getparent().remove(quote)
    body = root.xpath('.//*[@bounds="[176,1013][1047,1337]"]')[0]
    body.set("bounds", "[176,1013][809,1067]")
    body.set("text", "A short synthetic post.")
    return translated(
        etree.tostring(root, encoding="unicode"), "[0,924][1080,2340]", offset
    )


def receipt_document(offset):
    return translated(document("receipt"), "[0,924][1080,1456]", offset)


class ObscuredFeedbackReplay(FeedbackReplay):
    def __init__(self, offset=780):
        super().__init__()
        self.offset = offset
        self.documents["source"] = source_document(offset)
        self.documents["receipt"] = receipt_document(offset)
        self.xml = self.documents["source"]
        self.scroll_offset = -220

    def long_click(self, x, y, duration):
        self.actions.append(("tap", self.stage))
        if self.stage == "source":
            assert 1019 <= x < 1080 and 957 + self.offset <= y < 1006 + self.offset
            self.stage = "options"
        elif self.stage == "options":
            assert 0 <= x < 1080 and 888 <= y < 1042
            self.stage = "receipt"
        elif self.stage == "receipt":
            assert 853 <= x < 1047 and 988 + self.offset <= y < 1120 + self.offset
            self.stage = "source"
        else:
            raise AssertionError("Unexpected feedback tap.")
        self.xml = self.documents[self.stage]

    def swipe_points(self, path, duration):
        assert self.stage == "receipt"
        assert path[0][1] > path[-1][1]
        assert path[0][1] - path[-1][1] <= 240
        self.actions.append(("scroll", self.stage))
        self.offset += self.scroll_offset
        self.documents["receipt"] = receipt_document(self.offset)
        self.documents["source"] = source_document(self.offset)
        self.xml = self.documents["receipt"]
