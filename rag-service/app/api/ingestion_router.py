from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, List
import time

from app.ingestion.parser import DocumentParser
from app.ingestion.chunker import ChunkerEngine
from app.retrieval.vector_store import VectorStoreManager
from app.retrieval.bm25_search import BM25SearchEngine

import os
import json

router = APIRouter(prefix="/ingest", tags=["Ingestion Pipeline"])

# Shared singletons across requests
vector_store = VectorStoreManager()
bm25_engine = BM25SearchEngine()

CHUNKS_STORE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../database/chunks_store.json"))

def load_chunks_from_disk():
    try:
        if os.path.exists(CHUNKS_STORE_PATH):
            with open(CHUNKS_STORE_PATH, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
                if chunks:
                    vector_store.add_chunks(chunks)
                    bm25_engine.index_chunks(chunks)
                    print(f"[ChunkStore] Successfully hydrated {len(chunks)} chunks into Vector Store and BM25 index from disk.")
    except Exception as e:
        print(f"[ChunkStore] Failed to load chunks from disk: {e}")

def save_chunks_to_disk(all_chunks):
    try:
        os.makedirs(os.path.dirname(CHUNKS_STORE_PATH), exist_ok=True)
        with open(CHUNKS_STORE_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, indent=2)
    except Exception as e:
        print(f"[ChunkStore] Failed to save chunks to disk: {e}")

# Hydrate stored chunks on startup
all_indexed_chunks = []
if os.path.exists(CHUNKS_STORE_PATH):
    try:
        with open(CHUNKS_STORE_PATH, 'r', encoding='utf-8') as f:
            all_indexed_chunks = json.load(f)
            if all_indexed_chunks:
                vector_store.add_chunks(all_indexed_chunks)
                bm25_engine.index_chunks(all_indexed_chunks)
    except Exception as e:
        print(f"[ChunkStore] Hydration error: {e}")

@router.post("/process")
async def process_document(
    file: UploadFile = File(...),
    document_id: str = Form(...),
    strategy: str = Form("recursive"), # recursive, fixed, semantic
    chunk_size: int = Form(1000),
    overlap: int = Form(200)
):
    """Asynchronous Document Ingestion Pipeline Execution."""
    start_time = time.time()
    file_bytes = await file.read()
    filename = file.filename or "unknown_doc"
    file_ext = filename.split('.')[-1].lower()
    
    # 1. Parse Document & Extract Normalized Sections
    if file_ext == "pdf":
        sections = DocumentParser.parse_pdf(file_bytes, filename)
    elif file_ext in ["html", "htm"]:
        sections = DocumentParser.parse_html(file_bytes.decode('utf-8', errors='ignore'), filename)
    elif file_ext in ["md", "markdown"]:
        sections = DocumentParser.parse_markdown(file_bytes.decode('utf-8', errors='ignore'), filename)
    else:
        sections = DocumentParser.parse_text(file_bytes.decode('utf-8', errors='ignore'), filename)
        
    if not sections:
        raise HTTPException(status_code=400, detail="Failed to extract readable text from document.")
        
    # 2. Chunk Document based on requested strategy
    if strategy == "recursive":
        chunks = ChunkerEngine.recursive_chunking(sections, max_chunk_size=chunk_size)
    elif strategy == "semantic":
        chunks = ChunkerEngine.semantic_chunking(sections, embed_fn=vector_store.embed_texts)
    else:
        chunks = ChunkerEngine.fixed_chunking(sections, chunk_size=chunk_size, overlap=overlap)
        
    for c in chunks:
        c["document_id"] = document_id
        
    # 3. Vector Database Indexing (Qdrant Dense ANN)
    point_ids = vector_store.add_chunks(chunks)
    
    # 4. Sparse BM25 Indexing
    bm25_engine.index_chunks(chunks)
    
    # Save to disk store for persistence
    all_indexed_chunks.extend(chunks)
    save_chunks_to_disk(all_indexed_chunks)
    
    processing_time = round(time.time() - start_time, 3)
    
    return {
        "status": "COMPLETED",
        "document_id": document_id,
        "filename": filename,
        "strategy": strategy,
        "chunk_count": len(chunks),
        "processing_time_sec": processing_time,
        "chunks": chunks[:3] # Preview first 3 chunks
    }

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Remove document from Qdrant vector store and BM25 index."""
    vector_store.delete_document_chunks(document_id)
    bm25_engine.remove_document(document_id)
    
    global all_indexed_chunks
    all_indexed_chunks = [c for c in all_indexed_chunks if str(c.get("document_id")) != str(document_id)]
    save_chunks_to_disk(all_indexed_chunks)
    
    return {"status": "DELETED", "document_id": document_id}

