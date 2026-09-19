import os
import uuid
from typing import List, Dict, Any, Optional
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except ImportError:
    QdrantClient = None
    qmodels = None

from app.config import settings

class VectorStoreManager:
    """Qdrant Vector Database & Dense Similarity Search Engine."""
    
    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.model_name = settings.EMBEDDING_MODEL
        self.memory_points: List[Dict[str, Any]] = []
        
        # Initialize Embedding Model
        if SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer(self.model_name)
                self.vector_dim = self.model.get_sentence_embedding_dimension()
            except Exception as e:
                print(f"[Warning] Could not initialize transformer '{self.model_name}': {e}")
                self.model = None
                self.vector_dim = 384
        else:
            self.model = None
            self.vector_dim = 384

        # Initialize Qdrant Client (or memory list fallback)
        if QdrantClient is not None:
            try:
                self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=2)
                self._ensure_collection()
                self.is_remote = True
            except Exception:
                try:
                    self.client = QdrantClient(":memory:")
                    self._ensure_collection()
                    self.is_remote = False
                except Exception:
                    self.client = None
                    self.is_remote = False
        else:
            self.client = None
            self.is_remote = False


    def _ensure_collection(self):
        """Create Qdrant collection with HNSW index if it does not exist."""
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=self.vector_dim,
                        distance=qmodels.Distance.COSINE
                    ),
                    hnsw_config=qmodels.HnswConfigDiff(
                        m=16,
                        ef_construct=100
                    )
                )
                print(f"[VectorStore] Collection '{self.collection_name}' initialized.")
        except Exception as e:
            print(f"[VectorStore] Collection setup error: {e}")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Convert list of strings into dense vector representations."""
        if not texts:
            return []
        if self.model:
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings.tolist()
        else:
            # Deterministic pseudo-embedding for testing environment when torch model offline
            results = []
            for t in texts:
                np.random.seed(abs(hash(t)) % (2**32))
                vec = np.random.randn(self.vector_dim)
                vec = vec / (np.linalg.norm(vec) + 1e-9)
                results.append(vec.tolist())
            return results

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Index document chunks into Qdrant collection or in-memory fallback."""
        if not chunks:
            return []
            
        texts = [c["text"] for c in chunks]
        embeddings = self.embed_texts(texts)
        point_ids = []
        
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            chunk["embedding_id"] = point_id
            
            payload = {
                "document_id": str(chunk.get("document_id", "")),
                "chunk_id": str(chunk.get("chunk_id", point_id)),
                "chunk_index": chunk.get("chunk_index", idx),
                "text": chunk["text"],
                "section": chunk.get("section", ""),
                "page": chunk.get("page", 1),
                "source": chunk.get("source", ""),
                "strategy": chunk.get("strategy", "fixed")
            }
            
            self.memory_points.append({
                "id": point_id,
                "vector": emb,
                "payload": payload
            })
            
        if self.client is not None and qmodels is not None:
            try:
                points = [
                    qmodels.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
                    for p in self.memory_points[-len(chunks):]
                ]
                self.client.upsert(collection_name=self.collection_name, points=points)
            except Exception as e:
                print(f"[VectorStore] Upsert warning: {e}")

        return point_ids

    def search_dense(self, query: str, top_k: int = 10, threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Perform Approximate Nearest Neighbor (ANN) dense retrieval or cosine fallback."""
        query_vector = np.array(self.embed_texts([query])[0])
        
        if self.client is not None and qmodels is not None:
            try:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vector.tolist(),
                    limit=top_k,
                    score_threshold=threshold
                )
                retrieved = []
                for rank, res in enumerate(results, start=1):
                    payload = res.payload
                    retrieved.append({
                        "chunk_id": payload.get("chunk_id", res.id),
                        "document_id": payload.get("document_id"),
                        "text": payload.get("text"),
                        "section": payload.get("section"),
                        "page": payload.get("page"),
                        "source": payload.get("source"),
                        "strategy": payload.get("strategy"),
                        "dense_score": float(res.score),
                        "dense_rank": rank
                    })
                return retrieved
            except Exception:
                pass

        # In-memory numpy cosine similarity fallback
        scored = []
        for pt in self.memory_points:
            v = np.array(pt["vector"])
            sim = float(np.dot(query_vector, v) / (np.linalg.norm(query_vector) * np.linalg.norm(v) + 1e-9))
            scored.append((sim, pt["payload"]))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        retrieved = []
        for rank, (sim, payload) in enumerate(scored[:top_k], start=1):
            retrieved.append({
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "text": payload.get("text"),
                "section": payload.get("section"),
                "page": payload.get("page"),
                "source": payload.get("source"),
                "strategy": payload.get("strategy"),
                "dense_score": sim,
                "dense_rank": rank
            })
        return retrieved


    def delete_document_chunks(self, document_id: str):
        """Remove indexed points for a deleted document."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="document_id",
                                match=qmodels.MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
        except Exception as e:
            print(f"[VectorStore] Error deleting doc chunks: {e}")
