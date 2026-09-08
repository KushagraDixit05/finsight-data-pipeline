"""create_schema_and_seed

Revision ID: 96bfe2f853f3
Revises: 
Create Date: 2026-09-08 13:02:21.774229

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96bfe2f853f3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # news_sources
    op.execute("""
    CREATE TABLE news_sources (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        base_url TEXT,
        license_type TEXT,
        stores_full_content BOOLEAN NOT NULL DEFAULT FALSE
    );
    """)
    op.execute("""
    INSERT INTO news_sources (id, display_name, base_url, license_type, stores_full_content) VALUES
    ('marketaux', 'Marketaux', 'https://marketaux.com', 'paid-commercial', FALSE),
    ('finnhub', 'Finnhub', 'https://finnhub.io', 'paid-commercial', FALSE),
    ('newsdata', 'NewsData.io', 'https://newsdata.io', 'free-metadata-only', FALSE),
    ('gdelt', 'GDELT', 'https://gdeltproject.org', 'open-data', FALSE);
    """)

    # news_categories
    op.execute("""
    CREATE TABLE news_categories (
        id TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        description TEXT
    );
    """)
    op.execute("""
    INSERT INTO news_categories (id, label, description) VALUES
    ('company', 'Company', 'Single-company news: earnings, M&A, IPO, leadership changes, litigation.'),
    ('markets', 'Markets', 'Market-wide news: index moves, sector rotation, trading halts, sentiment.'),
    ('economy_macro', 'Economy & Macro', 'Macroeconomic indicators: GDP, inflation, employment, PMI, trade balance.'),
    ('central_bank_monetary_policy', 'Central Bank & Monetary Policy', 'Central bank actions: rate decisions, QE/QT, RBI/Fed/ECB statements.'),
    ('government_regulation', 'Government & Regulation', 'Fiscal/regulatory events: laws, SEBI changes, tax policy, budgets.'),
    ('geopolitical', 'Geopolitical', 'Cross-border political/military/diplomatic events, trade policy.'),
    ('commodities_energy', 'Commodities & Energy', 'Commodity, energy, and supply-chain events: oil, metals, shipping.');
    """)

    # news_articles
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("""
    CREATE TABLE news_articles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source TEXT NOT NULL REFERENCES news_sources(id),
        source_article_id TEXT,
        url TEXT NOT NULL,
        canonical_url TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        content TEXT,
        author TEXT,
        image_url TEXT,
        published_at TIMESTAMPTZ NOT NULL,
        fetched_at TIMESTAMPTZ NOT NULL,
        language TEXT,
        country TEXT,
        category TEXT NOT NULL REFERENCES news_categories(id),
        subcategory TEXT,
        topics TEXT[],
        entities TEXT[],
        tickers TEXT[],
        companies JSONB,
        sentiment JSONB,
        importance NUMERIC CHECK (importance IS NULL OR (importance >= 0 AND importance <= 1)),
        content_hash TEXT NOT NULL,
        duplicate_of_id UUID REFERENCES news_articles(id) ON DELETE SET NULL,
        raw_payload_ref TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

        CONSTRAINT uq_news_articles_canonical_url UNIQUE (canonical_url),
        CONSTRAINT uq_news_articles_content_hash UNIQUE (content_hash)
    );
    """)
    op.execute("""
    CREATE UNIQUE INDEX uq_news_articles_source_article_id
        ON news_articles (source, source_article_id)
        WHERE source_article_id IS NOT NULL;
    """)
    op.execute("CREATE INDEX idx_news_articles_published_at ON news_articles (published_at DESC);")
    op.execute("CREATE INDEX idx_news_articles_source ON news_articles (source);")
    op.execute("CREATE INDEX idx_news_articles_category ON news_articles (category);")
    op.execute("CREATE INDEX idx_news_articles_country ON news_articles (country);")
    op.execute("CREATE INDEX idx_news_articles_tickers ON news_articles USING GIN (tickers);")

    # entities & topics
    op.execute("""
    CREATE TABLE news_entities (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL,
        entity_type TEXT,
        ticker TEXT,
        UNIQUE (name, entity_type)
    );
    """)
    op.execute("""
    CREATE TABLE news_article_entities (
        article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
        entity_id UUID NOT NULL REFERENCES news_entities(id) ON DELETE CASCADE,
        role TEXT,
        PRIMARY KEY (article_id, entity_id)
    );
    """)
    op.execute("""
    CREATE TABLE news_topics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name TEXT NOT NULL UNIQUE
    );
    """)
    op.execute("""
    CREATE TABLE news_article_topics (
        article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
        topic_id UUID NOT NULL REFERENCES news_topics(id) ON DELETE CASCADE,
        PRIMARY KEY (article_id, topic_id)
    );
    """)

    # news_ingestion_logs
    op.execute("""
    CREATE TABLE news_ingestion_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        source TEXT REFERENCES news_sources(id),
        run_started_at TIMESTAMPTZ NOT NULL,
        run_finished_at TIMESTAMPTZ,
        status TEXT NOT NULL CHECK (status IN ('success', 'partial_failure', 'failure')),
        articles_fetched INT DEFAULT 0,
        articles_inserted INT DEFAULT 0,
        articles_duplicate INT DEFAULT 0,
        articles_failed_validation INT DEFAULT 0,
        error_summary TEXT
    );
    """)
    op.execute("CREATE INDEX idx_news_ingestion_logs_run_started_at ON news_ingestion_logs (run_started_at DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE news_ingestion_logs;")
    op.execute("DROP TABLE news_article_topics;")
    op.execute("DROP TABLE news_topics;")
    op.execute("DROP TABLE news_article_entities;")
    op.execute("DROP TABLE news_entities;")
    op.execute("DROP TABLE news_articles;")
    op.execute("DROP TABLE news_categories;")
    op.execute("DROP TABLE news_sources;")

