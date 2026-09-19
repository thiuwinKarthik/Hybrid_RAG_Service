import pytest
from app.ingestion.parser import DocumentParser
from app.ingestion.chunker import ChunkerEngine
from app.retrieval.hybrid_rrf import HybridRRFEngine
from app.generation.citation_verifier import CitationVerifier
from app.generation.confidence import ConfidenceEngine

def test_document_parser_normalization():
    raw = "Employees   must   change password.\n\n\n\nSection 1."
    clean = DocumentParser.normalize_text(raw)
    assert "  " not in clean
    assert clean.startswith("Employees must change password.")

def test_chunker_fixed_strategy():
    parsed = [{"source": "doc.pdf", "page": 1, "section": "Security", "text": "Word " * 200}]
    chunks = ChunkerEngine.fixed_chunking(parsed, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert chunks[0]["strategy"] == "fixed"
    assert chunks[0]["char_count"] > 0

def test_hybrid_rrf_scoring():
    dense = [{"chunk_id": "c1", "text": "Dense chunk", "dense_score": 0.9}]
    bm25 = [{"chunk_id": "c2", "text": "BM25 chunk", "bm25_score": 14.5}]
    
    combined = HybridRRFEngine.combine_results(dense, bm25, dense_weight=0.7, bm25_weight=0.3)
    assert len(combined) == 2
    assert "rrf_score" in combined[0]

def test_citation_extraction():
    answer = "Employees must change passwords every 90 days [1]. Submit request via portal [2]."
    context = [
        {"chunk_id": "c1", "source": "sec.pdf", "page": 15, "section": "Password", "text": "change password 90 days"},
        {"chunk_id": "c2", "source": "hr.pdf", "page": 5, "section": "Leave", "text": "submit request via portal"}
    ]
    citations = CitationVerifier.extract_citations(answer, context)
    assert len(citations) == 2
    assert citations[0]["source"] == "sec.pdf"
    
    verification = CitationVerifier.verify_claims(answer, context)
    assert verification["verification_rate"] >= 0.5

def test_confidence_score_threshold():
    chunks = [{"rerank_score": 0.95}]
    verification = {"verified_claims": [{"citations": [1]}], "verification_rate": 0.9}
    answer = "Valid answer text exceeding fifty characters long with citations [1]."
    
    res = ConfidenceEngine.calculate_confidence(chunks, verification, answer)
    assert res["confidence_score"] >= 0.7
    assert res["is_reliable"] is True
