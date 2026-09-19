import re
from typing import List, Dict, Any

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

class BM25SearchEngine:
    """Sparse Retrieval Engine using BM25 Okapi Algorithm."""
    
    def __init__(self):
        self.chunks_corpus: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25_index: Any = None

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text into lowercase alphanumeric and technical tokens."""
        if not text:
            return []
        # Keep alphanumeric, underscores, hyphens for error codes & technical terms
        tokens = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
        return tokens

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        """Build or update the BM25 sparse index."""
        if not chunks:
            return
        
        # Append new chunks to corpus
        self.chunks_corpus.extend(chunks)
        self.tokenized_corpus = [self.tokenize(c["text"]) for c in self.chunks_corpus]
        if self.tokenized_corpus and BM25Okapi is not None:
            self.bm25_index = BM25Okapi(self.tokenized_corpus)
            print(f"[BM25] Indexed {len(self.chunks_corpus)} chunks into BM25 engine.")

    def search_sparse(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Query BM25 index and return ranked candidate chunks."""
        if not self.chunks_corpus:
            return []
            
        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            return []
            
        if self.bm25_index is not None:
            doc_scores = self.bm25_index.get_scores(tokenized_query)
        else:
            # Fallback keyword match scoring when rank_bm25 module not installed
            doc_scores = []
            q_set = set(tokenized_query)
            for tokens in self.tokenized_corpus:
                match_count = sum(1 for t in tokens if t in q_set)
                doc_scores.append(float(match_count * 2.5))

        top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:top_k]
        
        results = []
        for rank, idx in enumerate(top_indices, start=1):
            score = float(doc_scores[idx])
            if score <= 0.0:
                continue
            chunk = self.chunks_corpus[idx]
            results.append({
                "chunk_id": chunk.get("chunk_id", str(idx)),
                "document_id": chunk.get("document_id"),
                "text": chunk["text"],
                "section": chunk.get("section"),
                "page": chunk.get("page"),
                "source": chunk.get("source"),
                "strategy": chunk.get("strategy"),
                "bm25_score": score,
                "bm25_rank": rank
            })
        return results


    def remove_document(self, document_id: str):
        """Rebuild BM25 index excluding document."""
        self.chunks_corpus = [c for c in self.chunks_corpus if str(c.get("document_id")) != str(document_id)]
        self.tokenized_corpus = [self.tokenize(c["text"]) for c in self.chunks_corpus]
        if self.tokenized_corpus:
            self.bm25_index = BM25Okapi(self.tokenized_corpus)
        else:
            self.bm25_index = None
