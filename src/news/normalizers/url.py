"""
src/news/normalizers/url.py — URL normalization for canonical deduplication.

The canonical_url is the primary deduplication key (Level-1 dedup,
07-deduplication.md). Two articles with the same canonical_url are considered
the same article regardless of which provider returned them.

Normalization rules applied (06-normalization-validation.md, rule 10):
  1. Require an absolute URL (http:// or https://). Relative URLs → None.
  2. Lowercase scheme and host.
  3. Strip known tracking query parameters (utm_*, fbclid, gclid, etc.).
  4. Remove URL fragment (#...).
  5. Remove trailing slash from path ONLY if path has more content
     (preserves bare "https://example.com/" → "example.com").
  6. Rebuild canonical_url as "host/path[?remaining_params]" without scheme
     (scheme-agnostic, so http: and https: variants are the same article).
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

log = logging.getLogger(__name__)

# Query parameters to strip from all URLs before canonicalization.
TRACKING_PARAMS: frozenset[str] = frozenset([
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_reader", "utm_name", "utm_cid",
    "fbclid", "gclid", "gad_source", "gbraid", "wbraid",
    "ref", "src", "source", "origin",
    "mc_cid", "mc_eid",                # Mailchimp
    "_hsenc", "_hsmi",                  # HubSpot
    "mkt_tok",                          # Marketo
    "vero_id",                          # Vero
    "s",                                # Some CMS short params
    "WT.mc_id",                         # Microsoft
    "igshid",                           # Instagram
])


def normalize_url(url: str | None) -> str | None:
    """
    Normalize a URL and return its canonical form (scheme-free).

    Returns None if ``url`` is None, empty, or not a valid absolute HTTP/S URL.

    Example:
        >>> normalize_url("https://Example.com/article/?utm_source=twitter#section")
        'example.com/article'
    """
    if not url:
        return None

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        log.debug("url.py: not an absolute http(s) URL: %r", url[:80])
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    # Lowercase host
    host = (parsed.hostname or "").lower()
    if not host:
        return None

    # Strip tracking params
    qs = parse_qs(parsed.query, keep_blank_values=False)
    qs_clean = {k: v for k, v in qs.items() if k.lower() not in TRACKING_PARAMS}
    new_query = urlencode(qs_clean, doseq=True) if qs_clean else ""

    # Reconstruct path: remove trailing slash if path is non-trivial
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Reconstruct scheme-free canonical URL
    # We keep port if non-standard
    port = parsed.port
    if port and ((parsed.scheme == "http" and port != 80) or
                 (parsed.scheme == "https" and port != 443)):
        host_part = f"{host}:{port}"
    else:
        host_part = host

    canonical = host_part + path
    if new_query:
        canonical += "?" + new_query

    return canonical
