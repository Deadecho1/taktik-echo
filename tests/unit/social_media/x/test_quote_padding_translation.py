"""Visible card padding does not make an offscreen translated header readable."""

from pathlib import Path

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage="after"):
    return read_screen(document(f"quote-padding-translation-{stage}"), (1080, 2340))


def test_padding_does_not_erase_native_offscreen_translation():
    s = screen()
    assert not s.rejected_posts
    q = s.posts[0].quoted_post
    assert q.visibility.visible_bounds is not None
    assert q.header_visibility.visible_bounds is None
    assert q.translation_visibility.visible_bounds is None
    assert q.translation == "Translated from Arabic"
    assert q.body is None and not q.observable
    assert _alignment(screen("before"), s, scrolling=True)[1]
