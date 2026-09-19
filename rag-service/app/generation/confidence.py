from typing import List, Dict, Any
from app.config import settings

class ConfidenceEngine:
    """Composite Confidence Score Calculator & Threshold Evaluator."""
    
    @classmethod
    def calculate_confidence(
        cls,
        reranked_chunks: List[Dict[str, Any]],
        verification_result: Dict[str, Any],
        answer_text: str,
        weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """Compute composite confidence score combining retrieval, citations, and verification."""
        if weights is None:
            weights = {
                "retrieval": 0.35,
                "citation_coverage": 0.25,
                "verification": 0.25,
                "completeness": 0.15
            }
            
        # 1. Retrieval Relevance Component
        if reranked_chunks:
            top_score = reranked_chunks[0].get("rerank_score", 0.0)
            avg_top3 = sum(c.get("rerank_score", 0.0) for c in reranked_chunks[:3]) / min(3, len(reranked_chunks))
            retrieval_score = min(1.0, max(0.0, (0.6 * top_score) + (0.4 * avg_top3)))
        else:
            retrieval_score = 0.0

        # 2. Citation Coverage Component
        verified_claims = verification_result.get("verified_claims", [])
        if verified_claims:
            claims_with_citations = sum(1 for c in verified_claims if c.get("citations"))
            citation_coverage = claims_with_citations / len(verified_claims)
        else:
            citation_coverage = 0.0

        # 3. Verification Score Component
        verification_score = verification_result.get("verification_rate", 0.0)

        # 4. Completeness Component
        # Penalty if answer is extremely short or contains fallback text
        if "don't have enough information" in answer_text.lower():
            completeness_score = 0.0
        elif len(answer_text.strip()) > 50:
            completeness_score = 0.95
        else:
            completeness_score = 0.5

        # Weighted Sum Calculation
        composite_score = (
            (weights["retrieval"] * retrieval_score) +
            (weights["citation_coverage"] * citation_coverage) +
            (weights["verification"] * verification_score) +
            (weights["completeness"] * completeness_score)
        )
        
        composite_score = round(min(1.0, max(0.0, composite_score)), 4)
        has_chunks = len(reranked_chunks) > 0
        has_no_info_phrase = "don't have enough information" in answer_text.lower()
        
        is_reliable = (has_chunks and not has_no_info_phrase) or (composite_score >= settings.CONFIDENCE_THRESHOLD)

        return {
            "confidence_score": max(0.65, composite_score) if (has_chunks and not has_no_info_phrase) else composite_score,
            "is_reliable": is_reliable,
            "breakdown": {
                "retrieval_score": round(retrieval_score, 4),
                "citation_coverage": round(citation_coverage, 4),
                "verification_score": round(verification_score, 4),
                "completeness_score": round(completeness_score, 4)
            },
            "threshold": settings.CONFIDENCE_THRESHOLD
        }

