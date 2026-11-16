"""Unattributed leading content, using synthetic text on captured geometry."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).parent / "fixtures"
SIZE = (1080, 2340)


def document(stage):
    return (FIXTURES / f"missing-handle-{stage}.xml").read_bytes()


def screens():
    return [read_screen(document(stage), SIZE) for stage in ("before", "after")]


def test_leading_header_without_handle_preserves_unattributed_content():
    before, after = screens()

    assert not before.rejected_posts
    assert len(before.fragments) == 2
    fragment = before.fragments[1]
    assert fragment.body == "Fixture unattributed body\u00a0Show more"
    assert fragment.body_visibility.unobscured
    assert not hasattr(fragment, "author")
    assert not hasattr(fragment, "content_key")
    assert [p.author for p in before.observable_posts] == ["@fixture_next"]
    assert after.fragments[0].body == fragment.body
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "handle",
        "partial_handle",
        "missing_name",
        "missing_age",
        "bad_age",
        "missing_badge",
        "unknown_badge",
        "badge_text",
        "nested_name",
        "interactive_name",
        "interactive_badge",
        "disabled_header",
        "hidden_name",
        "name_geometry",
        "badge_geometry",
        "age_geometry",
        "covered_header",
        "missing_body",
        "covered_body",
        "extra_body",
        "unknown_content",
        "after_attributed_post",
        "after_rejected_post",
    ],
)
def test_missing_handle_fragment_requires_known_structure_and_leading_position(
    mutation,
):
    root = etree.fromstring(document("before"))
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    container = header.getparent()
    body = container.xpath('./node[@class="android.widget.TextView"]')[0]
    if mutation == "handle":
        header[0].set("text", "@fixture_bad")
    elif mutation == "partial_handle":
        header[0].set("text", "Fixture @partial…")
    elif mutation == "missing_name":
        header[0].set("text", "")
    elif mutation == "missing_age":
        header.remove(header[-1])
    elif mutation == "bad_age":
        header[-1].set("text", "Unknown")
    elif mutation == "missing_badge":
        header.remove(header[1])
    elif mutation == "unknown_badge":
        header[1].set("content-desc", "Unknown")
    elif mutation == "badge_text":
        header[1].set("text", "Unexpected")
    elif mutation == "nested_name":
        header[0].append(deepcopy(header[1]))
    elif mutation in {"interactive_name", "interactive_badge"}:
        header[0 if mutation == "interactive_name" else 1].set("clickable", "true")
    elif mutation == "disabled_header":
        header.set("enabled", "false")
    elif mutation == "hidden_name":
        header[0].set("visible-to-user", "false")
    elif mutation == "name_geometry":
        header[0].set("bounds", "[172,430][745,501]")
    elif mutation == "badge_geometry":
        header[1].set("bounds", "[700,456][795,497]")
    elif mutation == "age_geometry":
        header[2].set("bounds", "[813,452][950,501]")
    elif mutation == "covered_header":
        root.xpath('//*[@resource-id="ntp"]')[0].set("bounds", "[389,420][691,552]")
    elif mutation == "missing_body":
        container.remove(body)
    elif mutation == "covered_body":
        body.set("bounds", "[176,100][1047,887]")
    elif mutation == "extra_body":
        container.insert(list(container).index(body), deepcopy(body))
    elif mutation == "unknown_content":
        child = deepcopy(header[1])
        child.set("content-desc", "Unknown post decoration")
        container.append(child)
    elif mutation in {"after_attributed_post", "after_rejected_post"}:
        preceding = deepcopy(
            root.xpath('//*[@resource-id="timeline_post"]')[1].getparent()
        )
        if mutation == "after_rejected_post":
            preceding.xpath('.//*[@text="@fixture_next"]')[0].set("text", "@invalid…")
        container.getparent().insert(1, preceding)

    screen = read_screen(etree.tostring(root), SIZE)

    assert not any(
        f.body == "Fixture unattributed body\u00a0Show more" for f in screen.fragments
    )
    assert any(p.bounds == (0, 419, 1080, 1503) for p in screen.rejected_posts)


@pytest.mark.parametrize(
    "mutation", ["body", "width", "movement", "duplicate_before", "duplicate_after"]
)
def test_unattributed_transition_requires_exact_content_unique_match_and_movement(
    mutation,
):
    before, after = screens()
    fragment = after.fragments[0]
    if mutation == "body":
        fragment = replace(fragment, body="Different body")
    elif mutation == "width":
        fragment = replace(
            fragment,
            body_visibility=replace(
                fragment.body_visibility, bounds=(180, 0, 1047, 375)
            ),
        )
    elif mutation == "movement":
        media = fragment.media[0]
        fragment = replace(
            fragment,
            media=(
                replace(
                    media,
                    visibility=replace(media.visibility, bounds=(176, 407, 1047, 897)),
                ),
            ),
        )
    elif mutation == "duplicate_before":
        before = replace(before, fragments=(*before.fragments, before.fragments[-1]))
    after = replace(
        after, fragments=(fragment,) * (2 if mutation == "duplicate_after" else 1)
    )

    with pytest.raises(XError, match="uniquely"):
        _alignment(before, after, scrolling=True)


def test_missing_header_during_refresh_still_requires_account_reverification():
    before, after = screens()
    assert _alignment(before, before) == (0, False)
    with pytest.raises(XError, match="outside adapter scrolling"):
        _alignment(before, after)
