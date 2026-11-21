"""The native LIVE avatar badge remains separate from post body and reposts."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def test_live_avatar_label_and_covered_business_header_preserve_continuity():
    before, after = [
        read_screen(document(f"avatar-live-badge-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not before.rejected_posts
    p = before.posts[0]
    assert "LIVE" in p.labels
    assert p.reposted_by is None and p.advertising == "unknown"
    assert not p.body.startswith("LIVE")
    fragment = after.fragments[0]
    assert not hasattr(fragment, "author")
    assert fragment.body == p.body
    assert fragment.covered_handle.text == p.author
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "text",
        "control",
        "wrapper_control",
        "nested",
        "outside",
        "no_overlap",
        "different_wrappers",
        "avatar_class",
        "avatar_shape",
        "avatar_control",
    ],
)
def test_live_avatar_requires_exact_native_structure_and_geometry(mutation):
    root = etree.fromstring(document("avatar-live-badge-before").encode())
    label = root.xpath('//*[@text="LIVE"]')[0]
    inner = label.getparent()
    badge = inner.getparent()
    avatar = badge.getprevious()
    if mutation == "text":
        label.set("text", "Unknown badge")
    elif mutation == "control":
        label.set("clickable", "true")
    elif mutation == "wrapper_control":
        badge.set("clickable", "true")
    elif mutation == "nested":
        label.append(etree.fromstring(etree.tostring(label)))
    elif mutation == "outside":
        label.set("bounds", "[59,990][117,1023]")
    elif mutation == "no_overlap":
        badge.set("bounds", "[22,934][154,1066]")
        inner.set("bounds", badge.get("bounds"))
        label.set("bounds", "[59,983][117,1016]")
    elif mutation == "different_wrappers":
        inner.set("bounds", "[22,870][154,996]")
    elif mutation == "avatar_class":
        avatar.set("class", "android.view.View")
    elif mutation == "avatar_shape":
        avatar.set("bounds", "[22,790][154,940]")
    else:
        avatar.set("clickable", "false")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize(
    "badge", ["Verified", "Verified Business", "Verified Governmental Account"]
)
def test_known_native_verification_badges_remain_unattributed_when_covered(badge):
    root = etree.fromstring(document("avatar-live-badge-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    header[1].set("content-desc", badge)
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert screen.fragments[0].covered_handle
    assert not hasattr(screen.fragments[0], "author")


@pytest.mark.parametrize(
    "prefix", ["avatar-live-empty-tail", "avatar-live-clipped-tail"]
)
def test_previously_verified_live_avatar_header_loss_still_replays(prefix):
    before, after = [
        read_screen(document(f"{prefix}-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    assert after.fragments[0].body == before.posts[0].body
    assert not hasattr(after.fragments[0], "author")
    assert _alignment(before, after, scrolling=True)[1]


@pytest.mark.parametrize(
    "mutation", ["text", "control", "description", "shape", "unclipped", "overlap"]
)
def test_empty_avatar_decoration_must_be_noninteractive_clipped_and_beside_body(
    mutation,
):
    root = etree.fromstring(document("avatar-live-empty-tail-after").encode())
    decoration = root.xpath('//*[@scrollable="true"]/*[@clickable="true"]')[0][0]
    if mutation in {"text", "description"}:
        decoration[0].set("text" if mutation == "text" else "content-desc", "Unknown")
    elif mutation == "control":
        decoration.set("clickable", "true")
    else:
        rect = {
            "shape": "[22,45][154,187]",
            "unclipped": "[22,136][154,268]",
            "overlap": "[100,45][232,177]",
        }[mutation]
        decoration.set("bounds", rect)
        decoration[0].set("bounds", rect)
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
