import os

try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        class BaseSettings:
            pass

class Settings(BaseSettings):
    APP_NAME: str = "Enterprise Hybrid RAG Service"
    DEBUG: bool = True
    
    # Qdrant settings
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "enterprise_documents")
    
    # NLP / Models
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    
    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-pro")

    
    # RAG Defaults
    DEFAULT_TOP_K: int = 10
    DEFAULT_FINAL_K: int = 5
    DEFAULT_RRF_K: int = 60
    DEFAULT_DENSE_WEIGHT: float = 0.7
    DEFAULT_BM25_WEIGHT: float = 0.3
    CONFIDENCE_THRESHOLD: float = 0.20



    class Config:
        env_file = ".env"

settings = Settings()
