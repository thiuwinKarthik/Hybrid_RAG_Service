from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time

from app.api.ingestion_router import vector_store, bm25_engine
from app.retrieval.hybrid_rrf import HybridRRFEngine
from app.retrieval.reranker import RerankerEngine
from app.generation.llm import LLMGenerator
from app.generation.citation_verifier import CitationVerifier
from app.generation.confidence import ConfidenceEngine
from app.config import settings

router = APIRouter(prefix="/rag", tags=["Hybrid RAG Intelligence"])

reranker_engine = RerankerEngine()

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 10
    final_k: Optional[int] = 5
    dense_weight: Optional[float] = 0.7
    bm25_weight: Optional[float] = 0.3
    rrf_k: Optional[int] = 60
    retrieval_mode: Optional[str] = "hybrid" # hybrid, dense_only, bm25_only

@router.post("/query")
async def execute_rag_query(req: QueryRequest):
    """Execute complete Hybrid RAG pipeline with developer trace explainability."""
    start_time = time.time()
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    t_start = time.time()
    
    # 1. Dense Vector Search (Qdrant ANN)
    dense_results = []
    if req.retrieval_mode in ["hybrid", "dense_only"]:
        dense_results = vector_store.search_dense(query, top_k=req.top_k)
    dense_time = round((time.time() - t_start) * 1000, 2)
    
    # 2. Sparse Lexical Search (BM25)
    t_bm25 = time.time()
    bm25_results = []
    if req.retrieval_mode in ["hybrid", "bm25_only"]:
        bm25_results = bm25_engine.search_sparse(query, top_k=req.top_k)
    bm25_time = round((time.time() - t_bm25) * 1000, 2)
    
    # 3. Reciprocal Rank Fusion (RRF)
    t_rrf = time.time()
    if req.retrieval_mode == "dense_only":
        rrf_results = dense_results
    elif req.retrieval_mode == "bm25_only":
        rrf_results = bm25_results
    else:
        rrf_results = HybridRRFEngine.combine_results(
            dense_results,
            bm25_results,
            dense_weight=req.dense_weight,
            bm25_weight=req.bm25_weight,
            rrf_k=req.rrf_k,
            top_k=req.top_k * 2
        )
    rrf_time = round((time.time() - t_rrf) * 1000, 2)
    
    # 4. Cross-Encoder Reranking
    t_rerank = time.time()
    reranked_chunks = reranker_engine.rerank(query, rrf_results, top_k=req.final_k)
    rerank_time = round((time.time() - t_rerank) * 1000, 2)
    
    # 5. Grounded LLM Generation
    t_llm = time.time()
    llm_res = LLMGenerator.generate_answer(query, reranked_chunks)
    llm_time = round((time.time() - t_llm) * 1000, 2)
    
    raw_answer = llm_res["answer"]
    
    # 6. Citation Mapping & Verification
    citations = CitationVerifier.extract_citations(raw_answer, reranked_chunks)
    verification_res = CitationVerifier.verify_claims(raw_answer, reranked_chunks)
    
    # 7. Composite Confidence Calculation & Threshold Evaluation
    confidence_res = ConfidenceEngine.calculate_confidence(
        reranked_chunks=reranked_chunks,
        verification_result=verification_res,
        answer_text=raw_answer
    )
    
    final_answer = raw_answer
    if not reranked_chunks and not confidence_res["is_reliable"]:
        final_answer = "I don't have enough information in the available company documentation to answer this question reliably."


    total_latency_ms = int((time.time() - start_time) * 1000)

    # Detailed Developer Trace for Explainability Panel (Module 20)
    pipeline_trace = {
        "query": query,
        "retrieval_mode": req.retrieval_mode,
        "dense_results": dense_results,
        "bm25_results": bm25_results,
        "rrf_results": rrf_results,
        "reranked_results": reranked_chunks,
        "verification": verification_res,
        "confidence": confidence_res,
        "latencies_ms": {
            "dense": dense_time,
            "bm25": bm25_time,
            "rrf": rrf_time,
            "rerank": rerank_time,
            "llm": llm_time,
            "total": total_latency_ms
        }
    }

    return {
        "query": query,
        "answer": final_answer,
        "citations": citations,
        "confidence_score": confidence_res["confidence_score"],
        "is_reliable": confidence_res["is_reliable"],
        "pipeline_trace": pipeline_trace,
        "execution_time_ms": total_latency_ms
    }
