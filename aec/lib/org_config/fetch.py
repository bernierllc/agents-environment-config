"""TLS-verified HTTPS GET for remote org configs and well-known pubkeys.

The actual network call is isolated behind an injectable ``opener`` so the
rest of the code (and every test) can run without touching the network. The
default opener uses ``urllib`` with a default SSL context — TLS verification
is always on and must never be disabled.

Only ``https://`` URLs are accepted; plaintext and local schemes are refused
before any connection is attempted.
"""
from __future__ import annotations

import ssl
import urllib.request
from typing import Callable, Optional

from .errors import OrgConfigFetchError

# A response larger than this is almost certainly not an org config / pubkey;
# refuse it rather than buffering an unbounded body into memory.
DEFAULT_MAX_BYTES = 1_000_000

Opener = Callable[[str, int], bytes]


def _default_opener(url: str, timeout: int) -> bytes:
    context = ssl.create_default_context()
    with urllib.request.urlopen(url, timeout=timeout, context=context) as resp:
        return resp.read()


def fetch_bytes(
    url: str,
    *,
    opener: Optional[Opener] = None,
    timeout: int = 10,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> bytes:
    """Fetch ``url`` over https and return its body.

    Raises ``OrgConfigFetchError`` for a non-https URL, an oversized body, or
    any error raised by the opener.
    """
    if not url.startswith("https://"):
        raise OrgConfigFetchError(
            f"refusing to fetch non-https URL: {url!r} (only https:// is allowed)"
        )

    open_fn = opener if opener is not None else _default_opener
    try:
        body = open_fn(url, timeout)
    except OrgConfigFetchError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize any transport error
        raise OrgConfigFetchError(f"failed to fetch {url}: {exc}") from exc

    if len(body) > max_bytes:
        raise OrgConfigFetchError(
            f"fetched body too large: {len(body)} bytes exceeds limit of {max_bytes}"
        )
    return body
