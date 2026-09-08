"""
src/news/models/enums.py — Canonical enumerations for the FinSight news pipeline.

These 7 news categories and 4 news sources are the single source of truth
(per 01-news-classification.md and 02-api-selection.md). Every adapter must
map its provider-specific categories/sources to exactly these values.
"""

from enum import Enum


class NewsCategory(str, Enum):
    """
    The 7 top-level categories that describe WHY a news article matters to
    financial markets. Rationale for each: 01-news-classification.md.

    Adapters must always produce one of these values; unknown provider
    categories fall back to ``MARKETS``.
    """

    COMPANY = "company"
    """Single-company news: earnings, M&A, IPO, leadership changes, litigation."""

    MARKETS = "markets"
    """Market-wide news: index moves, sector rotation, trading halts, sentiment."""

    ECONOMY_MACRO = "economy_macro"
    """Macroeconomic indicators: GDP, inflation, employment, PMI, trade balance."""

    CENTRAL_BANK_MONETARY_POLICY = "central_bank_monetary_policy"
    """Central bank actions: rate decisions, QE/QT, RBI/Fed/ECB statements."""

    GOVERNMENT_REGULATION = "government_regulation"
    """Fiscal/regulatory events: laws, SEBI changes, tax policy, budgets."""

    GEOPOLITICAL = "geopolitical"
    """Cross-border political/military/diplomatic events, trade policy."""

    COMMODITIES_ENERGY = "commodities_energy"
    """Commodity, energy, and supply-chain events: oil, metals, shipping."""


class NewsSource(str, Enum):
    """
    Internal provider keys. The value matches the ``news_sources.id`` seeded in
    the database (08-postgresql-schema.md). Adapters must always set
    ``source`` to one of these values — never a raw provider string.
    """

    MARKETAUX = "marketaux"
    FINNHUB = "finnhub"
    NEWSDATA = "newsdata"
    GDELT = "gdelt"
