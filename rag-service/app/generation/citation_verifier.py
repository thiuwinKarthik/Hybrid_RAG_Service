import re
from typing import List, Dict, Any, Tuple

class CitationVerifier:
    """Citation Parsing and Claim Verification Engine."""
    
    @classmethod
    def extract_citations(cls, answer: str, context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract [N] citation markers from LLM response and link to retrieved chunks."""
        citation_indices = sorted(list(set(int(m) for m in re.findall(r'\[(\d+)\]', answer))))
        citations = []
        
        for c_idx in citation_indices:
            # 1-based index matching context chunk order
            if 1 <= c_idx <= len(context_chunks):
                chunk = context_chunks[c_idx - 1]
                citations.append({
                    "citation_id": c_idx,
                    "chunk_id": chunk.get("chunk_id"),
                    "document_id": chunk.get("document_id"),
                    "source": chunk.get("source"),
                    "page": chunk.get("page"),
                    "section": chunk.get("section"),
                    "snippet": chunk.get("text", "")[:200] + "..."
                })
        return citations

    @classmethod
    def verify_claims(cls, answer: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse claim-citation pairs and verify whether referenced chunk supports claim."""
        # Split answer into claims (by sentence)
        claims = [s.strip() for s in re.split(r'(?<=[.!?])\s+', answer) if s.strip()]
        verified_claims = []
        supported_count = 0
        total_citations = 0
        
        for claim in claims:
            matches = [int(m) for m in re.findall(r'\[(\d+)\]', claim)]
            if not matches:
                verified_claims.append({
                    "claim": claim,
                    "citations": [],
                    "status": "UNSUPPORTED",
                    "reason": "Claim lacks inline source citation."
                })
                continue
                
            total_citations += len(matches)
            claim_text = re.sub(r'\[\d+\]', '', claim).strip().lower()
            claim_words = set(re.findall(r'\b\w{3,}\b', claim_text))
            
            claim_supported = False
            partially_supported = False
            matched_sources = []
            
            for c_idx in matches:
                if 1 <= c_idx <= len(context_chunks):
                    chunk = context_chunks[c_idx - 1]
                    chunk_text = chunk.get("text", "").lower()
                    chunk_words = set(re.findall(r'\b\w{3,}\b', chunk_text))
                    
                    matched_sources.append(chunk.get("source"))
                    overlap = len(claim_words.intersection(chunk_words))
                    coverage = overlap / max(1, len(claim_words))
                    
                    if coverage >= 0.4:
                        claim_supported = True
                    elif coverage >= 0.2:
                        partially_supported = True
                        
            if claim_supported:
                status = "SUPPORTED"
                supported_count += 1
            elif partially_supported:
                status = "PARTIALLY_SUPPORTED"
                supported_count += 0.5
            else:
                status = "UNSUPPORTED"
                
            verified_claims.append({
                "claim": claim,
                "citations": matches,
                "sources": matched_sources,
                "status": status
            })
            
        verification_rate = (supported_count / len(claims)) if claims else 0.0
        
        return {
            "verified_claims": verified_claims,
            "verification_rate": round(verification_rate, 4),
            "total_claims": len(claims),
            "supported_claims_count": supported_count
        }
