from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time

from app.api.ingestion_router import router as ingestion_router
from app.api.rag_router import router as rag_router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Microservice providing multi-format parsing, chunking, dense vector Qdrant search, sparse BM25 retrieval, RRF fusion, Cross-Encoder reranking, grounded LLM generation, citation verification, and confidence evaluation."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)
app.include_router(rag_router)

@app.get("/")
def health_check():
    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "embedding_model": settings.EMBEDDING_MODEL,
        "reranker_model": settings.RERANKER_MODEL,
        "llm_provider": settings.LLM_PROVIDER,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
