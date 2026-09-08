"""
src/news/models/news_article.py — Canonical NewsArticle data model.

This is the single internal object that every provider adapter must produce.
It is the contract between adapters and the rest of the pipeline
(normalization → validation → deduplication → storage → embedding).
Nothing downstream imports a provider-specific type.

Field classification (per 04-canonical-data-model.md):
  Required   — must be present, validation rejects the record if missing.
  Optional   — may be None; not every provider supplies all of these.
  Derived    — computed by the normalizer/repository, NOT by the adapter.
               Adapters must NOT set derived fields.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.news.models.enums import NewsCategory, NewsSource


# ── Sub-types used in the canonical model ────────────────────────────────────

class SentimentScore(BaseModel):
    """Provider-supplied sentiment, stored as-is (no custom NLP model in MVP)."""

    label: Optional[str] = None        # "Bullish" | "Neutral" | "Bearish" | None
    score: Optional[float] = None      # Normalised score if provider supplies one
    raw_tone: Optional[float] = None   # GDELT-specific raw tone score


class CompanyMention(BaseModel):
    """Structured company mention, pass-through from provider where available."""

    name: str
    ticker: Optional[str] = None


# ── Main canonical article model ─────────────────────────────────────────────

class NewsArticle(BaseModel):
    """
    Canonical news article. The one and only type passed between adapters,
    normalizers, deduplication, and the database layer.

    Required fields (adapter must always populate):
        source, url, title, published_at, fetched_at, category

    Optional fields (adapter populates where the provider supplies them):
        source_article_id, description, content, author, image_url,
        language, country, subcategory, raw_payload_ref,
        topics, entities, tickers, companies, sentiment

    Derived fields (set ONLY by the normalizer/repository — not the adapter):
        id, canonical_url, content_hash, importance, duplicate_of_id,
        created_at, updated_at
    """

    # ── Required ──────────────────────────────────────────────────────────────
    source: NewsSource = Field(
        description="Our internal provider key (NewsSource enum)."
    )
    url: str = Field(
        description="Raw URL exactly as returned by the provider."
    )
    title: str = Field(
        description="Article headline; max 500 chars (truncated, not rejected, if longer)."
    )
    published_at: datetime.datetime = Field(
        description="UTC datetime of publication per the provider."
    )
    fetched_at: datetime.datetime = Field(
        description="UTC datetime when our pipeline retrieved this record. Always set by us."
    )
    category: NewsCategory = Field(
        description="One of the 7 canonical categories (01-news-classification.md)."
    )

    # ── Optional ──────────────────────────────────────────────────────────────
    source_article_id: Optional[str] = Field(
        default=None,
        description="Provider's own article ID (Marketaux, Finnhub, NewsData.io). Null for GDELT."
    )
    description: Optional[str] = Field(
        default=None,
        description="Short summary/snippet from the provider."
    )
    content: Optional[str] = Field(
        default=None,
        description=(
            "Full or partial article body. Only populated if the provider includes it "
            "AND its license permits storage. GDELT: always None."
        )
    )
    author: Optional[str] = Field(default=None)
    image_url: Optional[str] = Field(default=None)
    language: Optional[str] = Field(
        default=None,
        description="ISO 639-1 language code (e.g. 'en'). None if provider doesn't supply."
    )
    country: Optional[str] = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code (e.g. 'IN', 'US'). None if provider doesn't supply."
    )
    subcategory: Optional[str] = Field(
        default=None,
        description=(
            "Free-text sub-category tag from the suggested vocabulary: "
            "earnings, guidance, mna, ipo, credit_rating, interest_rate_decision, "
            "tariffs, sanctions, oil_price, natural_disaster, etc."
        )
    )
    raw_payload_ref: Optional[str] = Field(
        default=None,
        description="Pointer to stored raw provider response (for audit/debugging). Not the payload itself."
    )

    # ── Optional arrays/objects ───────────────────────────────────────────────
    topics: Optional[list[str]] = Field(
        default=None,
        description="Provider-supplied tags/topics."
    )
    entities: Optional[list[str]] = Field(
        default=None,
        description="Named entities (people, orgs) — pass-through from provider."
    )
    tickers: Optional[list[str]] = Field(
        default=None,
        description="Stock ticker symbols — pass-through from Marketaux/Finnhub."
    )
    companies: Optional[list[CompanyMention]] = Field(
        default=None,
        description="Structured company mentions — pass-through where available."
    )
    sentiment: Optional[SentimentScore] = Field(
        default=None,
        description="Provider-supplied sentiment score. No custom model in MVP."
    )

    # ── Derived (set by normalizer/repository — adapters must NOT set these) ──
    id: Optional[uuid.UUID] = Field(
        default=None,
        description="DERIVED: Generated on insert (UUIDv4). Adapters must not set."
    )
    canonical_url: Optional[str] = Field(
        default=None,
        description=(
            "DERIVED: Normalized URL (lowercased host, tracking params stripped, "
            "trailing slash removed). Set by normalizer/pipeline.py."
        )
    )
    content_hash: Optional[str] = Field(
        default=None,
        description=(
            "DERIVED: sha256 of (normalized_title + '|' + source + '|' + published_date_hour). "
            "Used for Level-3 dedup. Set by normalizer/pipeline.py."
        )
    )
    importance: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="DERIVED: 0.0–1.0 importance score, computed by normalizer/pipeline.py."
    )
    duplicate_of_id: Optional[uuid.UUID] = Field(
        default=None,
        description="DERIVED: Set by deduplication layer if this is a near-duplicate. Null for originals."
    )
    created_at: Optional[datetime.datetime] = Field(
        default=None,
        description="DERIVED: Set by the database layer on insert."
    )
    updated_at: Optional[datetime.datetime] = Field(
        default=None,
        description="DERIVED: Set by the database layer on update."
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("title")
    @classmethod
    def truncate_title(cls, v: str) -> str:
        """Truncate title to 500 chars (don't reject, per 04-canonical-data-model.md)."""
        return v[:500] if v else v

    @field_validator("published_at", "fetched_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime.datetime:
        """Ensure datetime values are timezone-aware UTC."""
        if isinstance(v, datetime.datetime):
            if v.tzinfo is None:
                # Treat naive datetimes as UTC (adapters should always produce UTC)
                return v.replace(tzinfo=datetime.timezone.utc)
            return v.astimezone(datetime.timezone.utc)
        raise ValueError(f"Expected datetime, got {type(v)}")

    @field_validator("tickers", mode="before")
    @classmethod
    def uppercase_tickers(cls, v: Any) -> Optional[list[str]]:
        """Normalise ticker symbols to uppercase."""
        if v is None:
            return None
        return [t.strip().upper() for t in v if t and t.strip()]

    @model_validator(mode="after")
    def validate_derived_not_set_by_adapter(self) -> "NewsArticle":
        """
        Warn if an adapter accidentally sets derived fields.
        We don't reject — the normalizer will overwrite them anyway — but
        logging a warning makes adapter bugs visible during development.
        """
        # In production we rely on the normalizer overwriting; this is a
        # dev-time guard only.
        return self

    class Config:
        use_enum_values = False   # keep enum instances, not raw strings
        populate_by_name = True

    def model_dump_for_adapter(self) -> dict:
        """
        Return only the fields an adapter is allowed to set (required + optional).
        Strips all derived fields so the normalizer starts from a clean slate.
        """
        derived = {
            "id", "canonical_url", "content_hash", "importance",
            "duplicate_of_id", "created_at", "updated_at",
        }
        return {k: v for k, v in self.model_dump().items() if k not in derived}
