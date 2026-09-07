from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any

class EntityItem(BaseModel):
    text: str
    category: str  # ORG, LOC, COMMODITY, FINANCIAL_EVENT, etc.

class ArticleBase(BaseModel):
    title: str
    content: Optional[str] = None
    source: str
    published_time: datetime
    url: str

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    id: int
    sector: Optional[str] = None
    confidence_score: Optional[float] = None
    entities: Optional[List[Dict[str, str]]] = None
    processed: Optional[bool] = False
    qdrant_point_id: Optional[str] = None

    class Config:
        from_attributes = True

class SearchQuery(BaseModel):
    query_text: str
    sector_filter: Optional[str] = None
    limit: Optional[int] = 10

class SearchResult(BaseModel):
    article_id: int
    score: float
    title: str
    content: Optional[str]
    sector: Optional[str]
    entities: Optional[List[Dict[str, str]]]
    published_time: str
    url: str

class ImpactAnalysisRequest(BaseModel):
    sector_or_event: str
    limit_articles: Optional[int] = 5
    as_of: Optional[str] = None
    window_days: Optional[int] = None

class ImpactedSector(BaseModel):
    sector: str
    relationship: str
    impact_level: str  # High, Medium, Low
    explanation: str

class ImpactAnalysisResponse(BaseModel):
    source_sector: str
    event_summary: str
    direct_impacts: List[ImpactedSector]
    indirect_impacts: List[ImpactedSector]
    relevant_articles: List[SearchResult]
    ai_briefing: Optional[str] = None
    risk_metrics: Optional[List[str]] = None

class KnowledgeGraphNode(BaseModel):
    id: str
    label: str
    type: str  # sector, commodity, company
    group: str

class KnowledgeGraphEdge(BaseModel):
    from_node: str
    to_node: str
    relationship: str
    weight: float
    description: str

class KnowledgeGraphResponse(BaseModel):
    nodes: List[KnowledgeGraphNode]
    edges: List[KnowledgeGraphEdge]

class SimilarArticleLink(BaseModel):
    article_id: int
    title: str
    sector: Optional[str] = None
    similarity: float

class ArticleImpactNetworkResponse(BaseModel):
    article_id: int
    found: bool
    sector: Optional[str] = None
    similar_articles: Optional[List[SimilarArticleLink]] = None
    sector_cascade: Optional[Dict[str, Any]] = None

class TickerItem(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    percent_change: float