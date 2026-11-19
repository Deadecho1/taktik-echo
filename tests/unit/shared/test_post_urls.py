"""Public identities require exact platform hosts and direct native post paths."""

import pytest

from taktik.core.shared.post_urls import canonicalize


@pytest.mark.parametrize(
    "host",
    [
        "x.com",
        "www.x.com",
        "m.x.com",
        "twitter.com",
        "www.twitter.com",
        "mobile.twitter.com",
        "m.twitter.com",
    ],
)
def test_x_aliases_preserve_native_identity_without_share_tracking(host):
    assert canonicalize(
        "x", f"https://{host}/NASA/status/123456789/?s=19&t=abc#top"
    ) == (
        "https://x.com/NASA/status/123456789",
        "123456789",
    )


@pytest.mark.parametrize(
    "value",
    [
        "http://x.com/NASA/status/123",
        "https://x.com.evil.test/NASA/status/123",
        "https://evil.test/NASA/status/123",
        "https://x.com@evil.test/NASA/status/123",
        "https://user@x.com/NASA/status/123",
        "https://@x.com/NASA/status/123",
        "https://x.com:443/NASA/status/123",
        "https://x.com:0/NASA/status/123",
        "https://x.com:bad/NASA/status/123",
        "https://x.com/NASA/status/0",
        "https://x.com/NASA/status/0123",
        "https://x.com/NASA/status/18446744073709551616",
        "https://x.com/NASA/status/123/photo/1",
        "https://x.com/NASA/status/123/other",
        "https://x.com/NASA/status/١٢٣",
        "https://x.com/NASA/status/1\n",
        "https://x.com/NASA/status/1\\foo",
        "https://x.com/NASA/status/%31",
        "https://x.com/NASA/status/123 https://x.com/other/status/456",
        "https://x.com/NASA",
        "https://x.com/i/web/status/123",
        "https://x.com/i/status/123",
        "https://t.co/abc",
        None,
    ],
)
def test_x_rejects_unattributed_ambiguous_or_non_native_links(value):
    with pytest.raises(ValueError):
        canonicalize("x", value)


@pytest.mark.parametrize(
    "platform,value,expected",
    [
        (
            "instagram",
            "https://www.instagram.com/reel/Ab_c/?igsh=abc&utm_source=copy&other=1",
            ("https://www.instagram.com/reel/Ab_c/?other=1", "Ab_c"),
        ),
        (
            "tiktok",
            "https://m.tiktok.com/@creator/photo/123?is_copy_url=1&other=1",
            ("https://www.tiktok.com/@creator/photo/123?other=1", "123"),
        ),
    ],
)
def test_existing_platform_canonicalization_is_preserved(platform, value, expected):
    assert canonicalize(platform, value) == expected
