import pytest
from unittest.mock import MagicMock, patch
from src.news.embeddings.generator import generate_embedding, get_embedding_model
import src.news.embeddings.generator as generator_module

@pytest.fixture(autouse=True)
def mock_sentence_transformer():
    """Mock the SentenceTransformer to avoid downloading weights during tests."""
    with patch("src.news.embeddings.generator.SentenceTransformer") as mock_st:
        mock_instance = MagicMock()
        import numpy as np
        # Mock the encode method to return a dummy 384-dimensional list/array
        mock_instance.encode.return_value = np.array([0.1] * 384)
        mock_st.return_value = mock_instance
        
        # Reset the global model before each test
        generator_module._model = None
        
        yield mock_st

def test_generate_embedding_with_title_and_content(mock_sentence_transformer):
    title = "Test Article"
    content = "This is the content of the article."
    
    embedding = generate_embedding(title=title, content=content)
    
    assert len(embedding) == 384
    assert embedding[0] == 0.1
    
    # Verify the mock was called with the correct formatted text
    instance = mock_sentence_transformer.return_value
    instance.encode.assert_called_once_with("Title: Test Article\n\nThis is the content of the article.")

def test_generate_embedding_with_title_only(mock_sentence_transformer):
    title = "Test Article No Content"
    
    embedding = generate_embedding(title=title)
    
    assert len(embedding) == 384
    instance = mock_sentence_transformer.return_value
    instance.encode.assert_called_once_with("Title: Test Article No Content")

def test_generate_embedding_with_description_fallback(mock_sentence_transformer):
    title = "Test Article"
    description = "This is the description."
    
    # Content is None, so it should fallback to description
    embedding = generate_embedding(title=title, content=None, description=description)
    
    assert len(embedding) == 384
    instance = mock_sentence_transformer.return_value
    instance.encode.assert_called_once_with("Title: Test Article\n\nThis is the description.")

def test_model_is_loaded_lazily_and_cached(mock_sentence_transformer):
    # First call should initialize the model
    model1 = get_embedding_model()
    mock_sentence_transformer.assert_called_once()
    
    # Second call should return the cached instance
    model2 = get_embedding_model()
    assert model1 is model2
    assert mock_sentence_transformer.call_count == 1
