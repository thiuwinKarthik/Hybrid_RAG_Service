from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
from app.config import settings
import numpy as np

class RerankerEngine:
    """Cross-Encoder Reranker for Candidate Refinement."""
    
    def __init__(self):
        self.model_name = settings.RERANKER_MODEL
        try:
            self.model = CrossEncoder(self.model_name)
        except Exception as e:
            print(f"[Reranker] Warning: Could not load CrossEncoder model '{self.model_name}': {e}. Using fallback heuristic.")
            self.model = None

    def rerank(self, query: str, candidate_chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Rerank candidates using Cross-Encoder model or keyword overlap fallback."""
        if not candidate_chunks:
            return []
            
        pairs = [[query, c["text"]] for c in candidate_chunks]
        
        if self.model:
            scores = self.model.predict(pairs)
            # Sigmoid normalization for human-readable 0..1 scale
            scores = 1 / (1 + np.exp(-scores))
        else:
            # Fallback heuristic: weighted combination of RRF score and query term overlap
            scores = []
            q_words = set(query.lower().split())
            for c in candidate_chunks:
                text_words = set(c["text"].lower().split())
                overlap = len(q_words.intersection(text_words)) / max(1, len(q_words))
                score = (0.6 * c.get("rrf_score", 0.01) * 100) + (0.4 * overlap)
                scores.append(score)

        for chunk, score in zip(candidate_chunks, scores):
            chunk["rerank_score"] = float(score)

        sorted_chunks = sorted(candidate_chunks, key=lambda x: x["rerank_score"], reverse=True)
        
        for rank, chunk in enumerate(sorted_chunks[:top_k], start=1):
            chunk["rerank_rank"] = rank
            
        return sorted_chunks[:top_k]
