"""
src/news/embeddings/generator.py - Generates embeddings using sentence-transformers.
"""

import os
from typing import Optional
from sentence_transformers import SentenceTransformer

# We load the model lazily (singleton pattern) so it's not reloaded on every call.
_model: Optional[SentenceTransformer] = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        model_name = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
        # Initialize sentence-transformer
        _model = SentenceTransformer(model_name)
    return _model

def generate_embedding(title: str, content: Optional[str] = None, description: Optional[str] = None) -> list[float]:
    """
    Generate a 384-dimensional embedding for an article using all-MiniLM-L6-v2.
    Combines the title and the best available content/summary.
    """
    model = get_embedding_model()
    
    # Prioritize content over description, fallback to just title if neither exists
    body_text = content or description or ""
    
    # Construct the text to embed
    # A common pattern is "Title: <title>\n\n<content>"
    text_to_embed = f"Title: {title.strip()}"
    if body_text.strip():
        text_to_embed += f"\n\n{body_text.strip()}"
        
    # Generate embedding
    embedding = model.encode(text_to_embed)
    
    # Return as list of floats
    return embedding.tolist()
