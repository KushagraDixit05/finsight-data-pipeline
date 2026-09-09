"""
src/news/adapters/base.py — Shared foundation for all FinSight API adapters.

Defines:
  - Exception hierarchy so callers can react differently to auth failures vs
    transient rate-limit errors vs generic fetch problems.
  - ProviderConfig dataclass that every adapter accepts — decoupled from the
    global config module so adapters are unit-testable without env vars.

Design decisions
----------------
* Exception hierarchy is kept flat (3 classes) — we only need enough
  granularity to decide "back off immediately", "retry with delay", or
  "skip provider for this run".  More granularity can be added in Phase 11
  (retries/circuit-breakers) without changing caller code.
* ProviderConfig is a plain dataclass (not Pydantic) because it is
  constructed in the collector from already-validated config values and
  doesn't need its own validation layer.
* max_articles_per_request caps per-call return size; free-tier limits
  (Marketaux: 3) are handled inside each adapter and override this if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Exception Hierarchy ───────────────────────────────────────────────────────

class AdapterFetchError(Exception):
    """
    Base exception for all adapter retrieval failures.

    Raised when an HTTP request to a news provider fails for any reason other
    than authentication or rate-limiting.  Callers catching this class will
    also catch the two specialisations below.
    """


class AdapterAuthError(AdapterFetchError):
    """
    Raised when a provider returns HTTP 401 or 403.

    Indicates an invalid/expired API key or insufficient plan permissions.
    The collector treats this as a *skip-for-this-run* condition and emits
    a warning so the operator can rotate the key without crashing the pipeline.
    """


class AdapterRateLimitError(AdapterFetchError):
    """
    Raised when a provider returns HTTP 429 (Too Many Requests).

    The collector records this in the ProviderResult summary.  A future
    circuit-breaker layer (Phase 11) will use this to enforce per-provider
    cool-down windows rather than hammering an already-throttled endpoint.
    """


# ── Provider Configuration ────────────────────────────────────────────────────

@dataclass
class ProviderConfig:
    """
    Runtime configuration bundle passed to every adapter's fetch_and_map().

    All adapters receive this object rather than reading from the global
    config module directly.  This separation allows:
      1. Unit tests to construct arbitrary configs without setting env vars.
      2. The collector to gate on ``api_key`` being non-empty before calling
         any adapter that requires authentication.

    Attributes
    ----------
    api_key:
        Provider API key.  Empty string means "no key" — the collector skips
        providers for which this is empty (where a key is required).
    base_url:
        Root URL for the provider's API.  Defaults to empty string; each
        adapter module provides a sensible default when constructing its config.
    timeout_seconds:
        Per-request HTTP timeout.  Matches NEWS_COLLECTOR_TIMEOUT_SECONDS
        from the global config by default.
    max_articles_per_request:
        Soft cap on the number of articles requested per API call.  Free-tier
        providers (e.g. Marketaux free = 3) may return fewer regardless.
    """

    api_key: str = field(default="")
    base_url: str = field(default="")
    timeout_seconds: int = field(default=15)
    max_articles_per_request: int = field(default=15)


def sanitize_error_msg(msg: str, config: ProviderConfig) -> str:
    """Redact the API key from the error message to prevent secrets leakage."""
    if config.api_key and config.api_key in msg:
        return msg.replace(config.api_key, "***REDACTED***")
    return msg
