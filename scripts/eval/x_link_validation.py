"""Select and verify native Copy link opportunities without premature credit."""

from functools import partial

from taktik.core.shared.phone_interaction import Status
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.services.browsing.selection import _control, _source


def check_copy_link_roundtrip(browser, observation):
    link = browser.copy_link(observation)
    current = browser.observe(previous=observation)
    assert current.source_key == observation.source_key == link.source_key
    assert current.native_post_id == link.post_id
    assert current.post_url == link.url
    return link


def select_copy_link_check(browser, observation, *, features, skipped):
    """Return a named round trip; credit it only after the operation returns."""
    if "copy_link" in features:
        return None
    app = browser.browser
    with app._operation():
        browser._selected(observation)
        source = _source(app)
    try:
        _control(source.actions, "Share")
    except XError as error:
        if error.result.status != Status.UNSUPPORTED:
            raise
        skipped(
            {
                "source_identity": observation.identity,
                "source_key": source.content_key,
                "reason": str(error),
            }
        )
        return None
    return "copy_link", partial(check_copy_link_roundtrip, browser, observation)
