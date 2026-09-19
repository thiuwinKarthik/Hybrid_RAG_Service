from typing import List, Dict, Any
from app.config import settings

class HybridRRFEngine:
    """Reciprocal Rank Fusion (RRF) Hybrid Search Merger."""
    
    @staticmethod
    def combine_results(
        dense_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        dense_weight: float = 0.7,
        bm25_weight: float = 0.3,
        rrf_k: int = 60,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """Combine dense and sparse search rankings using Reciprocal Rank Fusion."""
        candidates: Dict[str, Dict[str, Any]] = {}
        
        # Process Dense Search Results
        for rank, item in enumerate(dense_results, start=1):
            cid = item["chunk_id"]
            if cid not in candidates:
                candidates[cid] = {
                    "chunk_id": cid,
                    "document_id": item.get("document_id"),
                    "text": item.get("text"),
                    "section": item.get("section"),
                    "page": item.get("page"),
                    "source": item.get("source"),
                    "strategy": item.get("strategy"),
                    "dense_rank": rank,
                    "dense_score": item.get("dense_score", 0.0),
                    "bm25_rank": None,
                    "bm25_score": 0.0,
                    "rrf_score": 0.0
                }
            rrf_score = dense_weight * (1.0 / (rrf_k + rank))
            candidates[cid]["rrf_score"] += rrf_score
            candidates[cid]["dense_rank"] = rank

        # Process BM25 Search Results
        for rank, item in enumerate(bm25_results, start=1):
            cid = item["chunk_id"]
            if cid not in candidates:
                candidates[cid] = {
                    "chunk_id": cid,
                    "document_id": item.get("document_id"),
                    "text": item.get("text"),
                    "section": item.get("section"),
                    "page": item.get("page"),
                    "source": item.get("source"),
                    "strategy": item.get("strategy"),
                    "dense_rank": None,
                    "dense_score": 0.0,
                    "bm25_rank": rank,
                    "bm25_score": item.get("bm25_score", 0.0),
                    "rrf_score": 0.0
                }
            rrf_score = bm25_weight * (1.0 / (rrf_k + rank))
            candidates[cid]["rrf_score"] += rrf_score
            candidates[cid]["bm25_rank"] = rank
            candidates[cid]["bm25_score"] = item.get("bm25_score", 0.0)

        # Sort combined candidates by RRF score descending
        sorted_candidates = sorted(candidates.values(), key=lambda x: x["rrf_score"], reverse=True)
        
        # Assign final RRF rank
        for rank, cand in enumerate(sorted_candidates[:top_k], start=1):
            cand["rrf_rank"] = rank

        return sorted_candidates[:top_k]
