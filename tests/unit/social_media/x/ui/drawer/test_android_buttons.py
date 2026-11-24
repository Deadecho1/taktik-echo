"""Captured full-width drawer and Android navigation stay separately owned."""

from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.x.ui.screen import read_screen

FIXTURE = Path(__file__).parents[2] / "fixtures/startup/android-buttons-drawer.xml"
SIZE = (1440, 3216)


def document():
    return etree.fromstring(FIXTURE.read_bytes())


def test_captured_android_buttons_do_not_become_clipboard_evidence():
    screen = read_screen(FIXTURE.read_text(), SIZE)
    assert screen.kind == "drawer", screen.reason
    assert screen.active_account == "@fixture_user"
    assert screen.clipboard_text is None
    assert screen.clipboard_bounds is None
    assert (0, 3040, 1440, 3216) in screen.overlaps
    assert screen.drawer_back
    assert {t.label for t in screen.controls} == {"Profile"}


@pytest.mark.parametrize(
    "fixture, kind",
    [
        ("android-buttons-drawer.xml", "drawer"),
        ("android-buttons-search.xml", "search_input"),
    ],
)
def test_oem_navigation_keeps_system_controls_excluded(fixture, kind):
    root = etree.fromstring(FIXTURE.with_name(fixture).read_bytes())
    nav = root.xpath(
        './/*[@resource-id="com.android.systemui:id/navigation_bar_frame"]'
    )[0]
    root.xpath('.//*[@resource-id="com.android.systemui:id/recent_apps"]')[0].set(
        "content-desc", "Recents"
    )
    widget = etree.SubElement(nav, "node", attrib=dict(nav.attrib))
    widget.set("resource-id", "com.android.systemui:id/nav_bar_widget")
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == kind, screen.reason
    assert (0, 3040, 1440, 3216) in screen.overlaps
    assert screen.clipboard_text is None
    assert not {"Back", "Home", "Recents"} & {t.label for t in screen.controls}


@pytest.mark.parametrize("change", ["text", "content-desc", "package", "child"])
def test_nav_bar_widget_does_not_hide_unknown_content(change):
    root = document()
    widget = etree.SubElement(root[0], "node", attrib=dict(root[0].attrib))
    widget.set("resource-id", "com.android.systemui:id/nav_bar_widget")
    if change == "child":
        child = etree.SubElement(widget, "node", attrib=dict(widget.attrib))
        child.set("resource-id", "com.android.systemui:id/unknown")
    else:
        widget.set(change, "Unknown")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


@pytest.mark.parametrize(
    "identity, label",
    [
        ("recent_apps", "Recent apps"),
        ("recent_apps", ""),
        ("home", "Recents"),
        ("back", "Recents"),
    ],
)
def test_button_label_alias_is_specific_to_recent_apps(identity, label):
    root = document()
    root.xpath(f'.//*[@resource-id="com.android.systemui:id/{identity}"]')[0].set(
        "content-desc", label
    )
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


@pytest.mark.parametrize("change", ["package", "control", "geometry", "extra"])
def test_unrecognized_system_windows_still_block_browsing(change):
    root = document()
    nav = root[0]
    if change == "package":
        nav[0].set("package", "com.example.overlay")
    elif change == "control":
        nav.xpath('.//*[@resource-id="com.android.systemui:id/home"]')[0].set(
            "content-desc", "Clipboard"
        )
    elif change == "geometry":
        nav.set("bounds", "[0,1000][1440,3216]")
    else:
        etree.SubElement(nav, "node", attrib={"text": "Unknown popup"})
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


@pytest.mark.parametrize("change", ["narrow", "handle", "header", "overlay"])
def test_full_width_drawer_requires_visible_native_account_and_structure(change):
    root = document()
    handle = root.xpath('.//*[@text="@fixture_user"]')[0]
    header = handle.getparent()
    if change == "narrow":
        header.getparent().set("bounds", "[0,160][1200,3040]")
    elif change == "handle":
        handle.set("text", "Not an account")
    elif change == "header":
        header.xpath('.//*[@text="Followers"]')[0].set("text", "Unknown")
    else:
        root[-1].set("bounds", "[0,0][1440,900]")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


def test_search_keyboard_keeps_native_buttons_outside_x_controls():
    xml = FIXTURE.with_name("android-buttons-search.xml").read_text()
    screen = read_screen(xml, SIZE)
    assert screen.kind == "search_input", screen.reason
    assert screen.clipboard_text is None
    assert (0, 3040, 1440, 3216) in screen.overlaps


def test_keyboard_overlap_does_not_expose_a_native_back_target():
    xml = FIXTURE.with_name("android-buttons-search.xml").read_text()
    assert read_screen(xml, SIZE).android_back is None


def test_duplicate_navigation_bars_block_browsing():
    from copy import deepcopy

    root = document()
    root.insert(0, deepcopy(root[0]))
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == "unsupported"
    assert screen.reason == "Ambiguous Android navigation bars."
