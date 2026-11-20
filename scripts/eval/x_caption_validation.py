"""Keep inline, native-detail, and recovery evidence distinct during X validation."""

from taktik.core.social_media.x.services.browsing import XInlineExpansionLimit


def check_caption(browser, observation, *, features, covered, max_scrolls=8):
    """Check one caption path using the caller's owned browser and evidence sink."""
    source = browser.observe(previous=observation)
    evidence = {"source_identity": source.identity, "source_key": source.source_key}
    inline = "read_more" not in features and (
        "native_long_caption" in features
        or features.get("inline_caption_attempt", 0)
        <= features.get("native_caption_attempt", 0)
    )
    if not inline:
        result = browser.inspect_thread(source, max_posts=10, max_scrolls=max_scrolls)
        current = browser.observe(previous=source)
        assert result.source_key == current.source_key == source.source_key
        covered("native_caption_attempt", {**evidence, "result": result})
        if result.main_text_complete:
            covered("native_main_text", {**evidence, "result": result})
            if source.caption_type == "truncated" and len(result.main_text) > len(
                source.caption
            ):
                covered("native_long_caption", {**evidence, "result": result})
        return result

    try:
        browser.read_more(source)
    except XInlineExpansionLimit as error:
        covered("inline_caption_attempt", evidence)
        covered(
            "inline_limit",
            {**evidence, "reason": str(error), "original_text_complete": False},
        )
        browser.recover()
        current = browser.observe()
        recovery = {
            **evidence,
            "continuation_identity": current.identity,
            "continuation_source_key": current.source_key,
            "original_text_complete": False,
            "reason": "inline_viewport_limit",
        }
        assert current.identity != source.identity
        covered("recovery", recovery)
        return recovery
    current = browser.observe(previous=source)
    assert current.caption_expanded and current.caption_type == "full"
    assert current.source_key != source.source_key
    covered("inline_caption_attempt", evidence)
    covered("read_more", {**evidence, "expanded_source_key": current.source_key})
    return current
