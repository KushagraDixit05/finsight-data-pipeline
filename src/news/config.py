"""
src/news/config.py — Single entry point for all environment configuration.

Reads env vars at import time and fails fast with a clear error message if any
*required* variable is missing, so misconfiguration surfaces immediately rather
than at the point of first use.

Optional variables (API keys for providers not yet active, embedding model, etc.)
are read with defaults and will NOT cause a startup failure — they just reduce the
number of active providers or features.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Return env var value, raising a clear error if it is missing."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Copy .env.example to .env and fill in your values."
        )
    return value


def _optional(name: str, default: str = "") -> str:
    """Return env var value or a default; never raises."""
    return os.getenv(name, default)


# ── Database ─────────────────────────────────────────────────────────────────
# Required at runtime for the scheduler and repository layer.
# Not required for tests (tests use TEST_DATABASE_URL).
DATABASE_URL: str = _optional("DATABASE_URL", "")
TEST_DATABASE_URL: str = _optional("TEST_DATABASE_URL", "")

# ── News API Keys (all optional — missing key = that provider skipped) ────────
MARKETAUX_API_KEY: str = _optional("MARKETAUX_API_KEY")
FINNHUB_API_KEY: str = _optional("FINNHUB_API_KEY")
NEWSDATA_API_KEY: str = _optional("NEWSDATA_API_KEY")
# GDELT requires no API key

# ── Scheduler ─────────────────────────────────────────────────────────────────
NEWS_INGESTION_INTERVAL_HOURS: int = int(_optional("NEWS_INGESTION_INTERVAL_HOURS", "2"))
NEWS_OVERLAP_WINDOW_MINUTES: int = int(_optional("NEWS_OVERLAP_WINDOW_MINUTES", "30"))
NEWS_MAX_ARTICLE_AGE_DAYS: int = int(_optional("NEWS_MAX_ARTICLE_AGE_DAYS", "30"))
NEWS_ADVISORY_LOCK_KEY: int = int(_optional("NEWS_ADVISORY_LOCK_KEY", "487219"))
NEWS_COLLECTOR_TIMEOUT_SECONDS: int = int(_optional("NEWS_COLLECTOR_TIMEOUT_SECONDS", "15"))

# ── Rate limits (read from config, never hardcoded in adapter logic) ──────────
MARKETAUX_RATE_LIMIT_PER_DAY: int = int(_optional("MARKETAUX_RATE_LIMIT_PER_DAY", "100"))
FINNHUB_RATE_LIMIT_PER_MINUTE: int = int(_optional("FINNHUB_RATE_LIMIT_PER_MINUTE", "60"))
NEWSDATA_RATE_LIMIT_PER_DAY: int = int(_optional("NEWSDATA_RATE_LIMIT_PER_DAY", "200"))

# ── Embedding (Phase 10 — DESIGN DECISION PENDING: see DESIGN_DECISIONS.md) ──
# Defaults target OpenAI text-embedding-3-small (1536-dim).
# Change EMBEDDING_MODEL_NAME + EMBEDDING_MODEL_DIMENSION together if switching models.
EMBEDDING_MODEL_NAME: str = _optional("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
EMBEDDING_MODEL_DIMENSION: int = int(_optional("EMBEDDING_MODEL_DIMENSION", "1536"))
EMBEDDING_API_KEY: str = _optional("EMBEDDING_API_KEY")
EMBEDDING_BATCH_SIZE: int = int(_optional("EMBEDDING_BATCH_SIZE", "50"))

# ── GDELT ─────────────────────────────────────────────────────────────────────
# GDELT DOC 2.0 API public endpoint — no key required.
GDELT_BASE_URL: str = "https://api.gdeltproject.org/api/v2/doc/doc"
# Max keyword/theme queries per scheduler run to be a good citizen.
GDELT_MAX_QUERIES_PER_RUN: int = int(_optional("GDELT_MAX_QUERIES_PER_RUN", "6"))
# Small inter-query delay (seconds) for GDELT self-throttling.
GDELT_INTER_QUERY_DELAY_SECONDS: float = float(_optional("GDELT_INTER_QUERY_DELAY_SECONDS", "1.0"))
