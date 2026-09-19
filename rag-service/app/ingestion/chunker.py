import re
from typing import List, Dict, Any
import numpy as np

class ChunkerEngine:
    """Configurable Chunking Engine for RAG pipeline."""
    
    @staticmethod
    def fixed_chunking(
        parsed_sections: List[Dict[str, Any]], 
        chunk_size: int = 500, 
        overlap: int = 100
    ) -> List[Dict[str, Any]]:
        """Fixed-size character/word window chunking with overlap."""
        chunks = []
        chunk_index = 0
        
        for section_item in parsed_sections:
            text = section_item["text"]
            words = text.split()
            if not words:
                continue
                
            # Words-based approximation (~5 chars/word)
            word_chunk_size = max(50, chunk_size // 5)
            word_overlap = max(10, overlap // 5)
            
            i = 0
            while i < len(words):
                chunk_words = words[i : i + word_chunk_size]
                chunk_text = " ".join(chunk_words)
                
                if len(chunk_text.strip()) > 20:
                    chunks.append({
                        "chunk_index": chunk_index,
                        "strategy": "fixed",
                        "text": chunk_text,
                        "section": section_item.get("section", "General"),
                        "page": section_item.get("page", 1),
                        "source": section_item.get("source", "unknown"),
                        "char_count": len(chunk_text)
                    })
                    chunk_index += 1
                
                i += (word_chunk_size - word_overlap)
                if i <= 0:  # Safety boundary
                    break
        return chunks

    @staticmethod
    def recursive_chunking(
        parsed_sections: List[Dict[str, Any]], 
        max_chunk_size: int = 600
    ) -> List[Dict[str, Any]]:
        """Structure-aware recursive paragraph and sentence splitter."""
        chunks = []
        chunk_index = 0
        
        for section_item in parsed_sections:
            text = section_item["text"]
            # Split by double newline (paragraphs), then single newline, then sentences
            paragraphs = re.split(r'\n\n+', text)
            
            current_buffer = []
            current_length = 0
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                    
                if current_length + len(para) <= max_chunk_size:
                    current_buffer.append(para)
                    current_length += len(para) + 2
                else:
                    if current_buffer:
                        chunk_text = "\n\n".join(current_buffer)
                        chunks.append({
                            "chunk_index": chunk_index,
                            "strategy": "recursive",
                            "text": chunk_text,
                            "section": section_item.get("section", "General"),
                            "page": section_item.get("page", 1),
                            "source": section_item.get("source", "unknown"),
                            "char_count": len(chunk_text)
                        })
                        chunk_index += 1
                    
                    # If paragraph itself exceeds max_chunk_size, split by sentences
                    if len(para) > max_chunk_size:
                        sentences = re.split(r'(?<=[.!?])\s+', para)
                        s_buffer = []
                        s_len = 0
                        for s in sentences:
                            if s_len + len(s) <= max_chunk_size:
                                s_buffer.append(s)
                                s_len += len(s) + 1
                            else:
                                if s_buffer:
                                    stext = " ".join(s_buffer)
                                    chunks.append({
                                        "chunk_index": chunk_index,
                                        "strategy": "recursive",
                                        "text": stext,
                                        "section": section_item.get("section", "General"),
                                        "page": section_item.get("page", 1),
                                        "source": section_item.get("source", "unknown"),
                                        "char_count": len(stext)
                                    })
                                    chunk_index += 1
                                s_buffer = [s]
                                s_len = len(s)
                        if s_buffer:
                            stext = " ".join(s_buffer)
                            current_buffer = [stext]
                            current_length = len(stext)
                    else:
                        current_buffer = [para]
                        current_length = len(para)
                        
            if current_buffer:
                chunk_text = "\n\n".join(current_buffer)
                chunks.append({
                    "chunk_index": chunk_index,
                    "strategy": "recursive",
                    "text": chunk_text,
                    "section": section_item.get("section", "General"),
                    "page": section_item.get("page", 1),
                    "source": section_item.get("source", "unknown"),
                    "char_count": len(chunk_text)
                })
                chunk_index += 1
                
        return chunks

    @staticmethod
    def semantic_chunking(
        parsed_sections: List[Dict[str, Any]], 
        embed_fn=None,
        threshold: float = 0.65
    ) -> List[Dict[str, Any]]:
        """Semantic similarity boundary detection chunker."""
        chunks = []
        chunk_index = 0
        
        for section_item in parsed_sections:
            text = section_item["text"]
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 10]
            if not sentences:
                continue
                
            if embed_fn is None or len(sentences) < 3:
                # Fallback to recursive if sentence count is tiny or embed_fn is omitted
                sub_chunks = ChunkerEngine.recursive_chunking([section_item])
                for sc in sub_chunks:
                    sc["strategy"] = "semantic"
                    sc["chunk_index"] = chunk_index
                    chunks.append(sc)
                    chunk_index += 1
                continue
                
            # Generate sentence embeddings
            embeddings = embed_fn(sentences)
            
            # Compute cosine similarities between consecutive sentences
            current_chunk_sentences = [sentences[0]]
            
            for i in range(len(sentences) - 1):
                vec1 = embeddings[i]
                vec2 = embeddings[i + 1]
                sim = float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2) + 1e-9))
                
                if sim >= threshold and sum(len(s) for s in current_chunk_sentences) < 800:
                    current_chunk_sentences.append(sentences[i + 1])
                else:
                    # Semantic topic boundary detected
                    ctext = " ".join(current_chunk_sentences)
                    chunks.append({
                        "chunk_index": chunk_index,
                        "strategy": "semantic",
                        "text": ctext,
                        "section": section_item.get("section", "General"),
                        "page": section_item.get("page", 1),
                        "source": section_item.get("source", "unknown"),
                        "char_count": len(ctext)
                    })
                    chunk_index += 1
                    current_chunk_sentences = [sentences[i + 1]]
                    
            if current_chunk_sentences:
                ctext = " ".join(current_chunk_sentences)
                chunks.append({
                    "chunk_index": chunk_index,
                    "strategy": "semantic",
                    "text": ctext,
                    "section": section_item.get("section", "General"),
                    "page": section_item.get("page", 1),
                    "source": section_item.get("source", "unknown"),
                    "char_count": len(ctext)
                })
                chunk_index += 1
                
        return chunks
