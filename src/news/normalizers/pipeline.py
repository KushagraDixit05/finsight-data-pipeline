"""
src/news/normalizers/pipeline.py — Main normalization pipeline.
"""

from __future__ import annotations

import hashlib
import logging

from src.news.models.news_article import NewsArticle
from src.news.normalizers.text import clean_text, clean_whitespace
from src.news.normalizers.datetime_utils import to_utc
from src.news.normalizers.url import normalize_url
from src.news.normalizers.geo import normalize_country, normalize_language

log = logging.getLogger(__name__)

def normalize(article: NewsArticle) -> NewsArticle:
    """
    Apply deterministic normalization rules to a NewsArticle.
    Returns a new NewsArticle instance (does not mutate in place).
    """
    # 1 & 2. Date/time normalization (already mostly UTC via pydantic, but re-assert)
    # The Pydantic model's field_validator already calls to_utc logic or similar if it's set up that way,
    # but we can explicitly clean it. Actually, pydantic already ensures datetime is UTC.
    pub_at = to_utc(article.published_at, article.source.value) or article.published_at
    
    # 3, 4, 5. Text cleaning (HTML stripping, whitespace collapse, empty->None)
    title = clean_text(article.title) or ""  # title is required, keep empty string if stripped
    description = clean_text(article.description) if article.description else None
    content = clean_text(article.content) if article.content else None
    
    # 8. Country normalization
    country = normalize_country(article.country) if article.country else None
    
    # 9. Language normalization
    language = normalize_language(article.language) if article.language else None
    
    # 10. URL normalization
    canonical_url = normalize_url(article.url)
    
    # 11. Author normalization
    author = clean_whitespace(article.author) if article.author else None
    if author and author.lower() in ("staff", "admin"):
        author = None
        
    # Subcategory normalization (whitespace only)
    subcategory = clean_whitespace(article.subcategory) if article.subcategory else None

    # Compute content_hash (Level-3 dedup)
    # hash = sha256(normalized_title + "|" + source + "|" + published_date_hour)
    date_hour = pub_at.strftime("%Y-%m-%d-%H")
    hash_input = f"{title}|{article.source.value}|{date_hour}"
    content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
    
    # Construct normalized article
    # We use model_dump to extract data, update it, and create a new instance
    data = article.model_dump()
    data.update({
        "title": title,
        "description": description,
        "content": content,
        "country": country,
        "language": language,
        "author": author,
        "subcategory": subcategory,
        "published_at": pub_at,
        "canonical_url": canonical_url,
        "content_hash": content_hash,
    })
    
    # Validation step happens externally in validate.py, but we return the normalized object here
    return NewsArticle(**data)
