"""
src/news/normalizers/datetime_utils.py — Robust datetime parsing to UTC.

Each provider uses a different datetime format; this module normalises them
all to timezone-aware UTC datetimes before the article enters the pipeline.

Supported formats
─────────────────
  - datetime object (with or without tzinfo)
  - ISO 8601 string (with Z, +00:00, or other offsets)
  - Unix timestamps (int or float seconds since epoch)
  - GDELT compact: YYYYMMDDTHHMMSSZ or YYYYMMDDHHMMSS
  - Common formats: "%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z", etc.

All returned values are timezone-aware with tzinfo=UTC.
None is returned (with a log.warning) on unparseable input.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

log = logging.getLogger(__name__)

# Ordered list of strptime format strings to try for string inputs.
# Most-common formats first for efficiency.
_STRING_FORMATS = [
    "%Y-%m-%dT%H:%M:%SZ",          # ISO 8601 Z-suffix (Marketaux, GDELT)
    "%Y-%m-%dT%H:%M:%S%z",         # ISO 8601 with offset
    "%Y-%m-%dT%H:%M:%S.%fZ",       # ISO 8601 with microseconds + Z
    "%Y-%m-%dT%H:%M:%S.%f%z",      # ISO 8601 with microseconds + offset
    "%Y-%m-%d %H:%M:%S",            # NewsData.io pubDate (naive, treated as UTC)
    "%Y-%m-%dT%H:%M",               # Truncated ISO
    "%Y-%m-%d",                     # Date-only
    "%a, %d %b %Y %H:%M:%S %z",    # RFC 2822 (some RSS feeds)
    "%a, %d %b %Y %H:%M:%S GMT",   # RFC 2822 without offset
    "%d %b %Y %H:%M:%S %z",
    # GDELT compact forms
    "%Y%m%dT%H%M%SZ",
    "%Y%m%d%H%M%S",
    "%Y%m%dT%H%M%S",
]

UTC = datetime.timezone.utc


def _ensure_utc(dt: datetime.datetime, source_hint: str = "") -> datetime.datetime:
    """Convert a datetime to UTC. Treat naive datetimes as UTC."""
    if dt.tzinfo is None:
        if source_hint:
            log.warning(
                "datetime_utils: naive datetime treated as UTC (source=%r). "
                "Adapter should produce timezone-aware values.",
                source_hint,
            )
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_utc(value: Any, source_hint: str = "") -> datetime.datetime | None:
    """
    Parse a datetime value (any supported format) to UTC-aware datetime.

    Args:
        value:       datetime, int/float (unix timestamp), or string.
        source_hint: Provider name for log context ("finnhub", "gdelt", etc.)

    Returns:
        UTC-aware datetime, or None on failure.
    """
    if value is None:
        return None

    # Already a datetime
    if isinstance(value, datetime.datetime):
        return _ensure_utc(value, source_hint)

    # Unix timestamp
    if isinstance(value, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(value, tz=UTC)
        except (OSError, OverflowError, ValueError):
            log.warning("datetime_utils: unix timestamp %r out of range (source=%r)", value, source_hint)
            return None

    # String parsing
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None

        # Python 3.11+ handles Z suffix natively via fromisoformat
        try:
            dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            return _ensure_utc(dt, source_hint)
        except ValueError:
            pass

        # Try each explicit format
        for fmt in _STRING_FORMATS:
            try:
                dt = datetime.datetime.strptime(s, fmt)
                return _ensure_utc(dt, source_hint)
            except ValueError:
                continue

        log.warning(
            "datetime_utils: could not parse %r as datetime (source=%r)",
            s[:80], source_hint,
        )
        return None

    log.warning(
        "datetime_utils: unsupported type %s for value %r (source=%r)",
        type(value).__name__, str(value)[:40], source_hint,
    )
    return None
