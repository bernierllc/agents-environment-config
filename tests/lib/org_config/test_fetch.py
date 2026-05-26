"""Tests for the TLS-verified, injectable https fetcher."""

import pytest

from aec.lib.org_config.fetch import OrgConfigFetchError, fetch_bytes


def test_rejects_non_https():
    with pytest.raises(OrgConfigFetchError, match="https"):
        fetch_bytes("http://example.com/x", opener=lambda url, timeout: b"x")


def test_rejects_non_url_scheme():
    with pytest.raises(OrgConfigFetchError, match="https"):
        fetch_bytes("file:///etc/passwd", opener=lambda url, timeout: b"x")


def test_passes_through_https_body():
    got = fetch_bytes("https://example.com/x", opener=lambda url, timeout: b"hello")
    assert got == b"hello"


def test_enforces_max_bytes():
    big = b"x" * 1000
    with pytest.raises(OrgConfigFetchError, match="too large"):
        fetch_bytes("https://e/x", opener=lambda url, timeout: big, max_bytes=10)


def test_within_max_bytes_ok():
    body = b"x" * 10
    assert fetch_bytes("https://e/x", opener=lambda url, timeout: body, max_bytes=10) == body


def test_passes_timeout_to_opener():
    seen = {}

    def opener(url, timeout):
        seen["url"] = url
        seen["timeout"] = timeout
        return b"ok"

    fetch_bytes("https://e/x", opener=opener, timeout=3)
    assert seen == {"url": "https://e/x", "timeout": 3}


def test_wraps_opener_errors():
    def opener(url, timeout):
        raise OSError("connection refused")

    with pytest.raises(OrgConfigFetchError, match="failed to fetch"):
        fetch_bytes("https://e/x", opener=opener)
