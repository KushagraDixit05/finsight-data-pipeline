from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON
from database import Base
import datetime

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text, nullable=True)
    source = Column(String, index=True)
    published_time = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    url = Column(String, unique=True, index=True)
    
    # NLP & Knowledge Graph fields
    sector = Column(String, index=True, nullable=True)
    confidence_score = Column(Float, nullable=True)
    entities = Column(JSON, nullable=True) # JSON list of extracted entities: [{text, category}]
    processed = Column(Boolean, default=False, index=True)
    qdrant_point_id = Column(String, nullable=True)
