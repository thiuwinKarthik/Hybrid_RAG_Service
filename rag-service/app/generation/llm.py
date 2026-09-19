import os
import re
import requests
from typing import List, Dict, Any, Tuple
from app.config import settings

class LLMGenerator:
    """Configurable LLM Provider for Grounded RAG Generation."""
    
    @staticmethod
    def build_prompt(query: str, context_chunks: List[Dict[str, Any]]) -> Tuple[str, str]:
        """Construct grounded system and user prompts with indexed citations."""
        system_instruction = (
            "You are an enterprise knowledge assistant.\n"
            "Answer the user's question using ONLY the supplied document context.\n"
            "Synthesize a concise, clear, and direct answer in natural conversational paragraphs or bullet points.\n"
            "Do NOT repeat resume headers, emails, phone numbers, or duplicate contact lines across chunks.\n"
            "Do NOT invent or extrapolate information beyond the provided text.\n"
            "If the context does NOT contain sufficient evidence to answer, state:\n"
            "\"I don't have enough information in the available company documentation to answer this question.\"\n"
            "For every factual claim in your response, include a bracketed citation matching the source index, e.g., [1] or [2]."
        )
        
        context_blocks = []
        for idx, chunk in enumerate(context_chunks, start=1):
            source = chunk.get("source", "document")
            page = chunk.get("page", 1)
            section = chunk.get("section", "General")
            text = chunk.get("text", "")
            context_blocks.append(f"[{idx}] Source: {source} | Page: {page} | Section: {section}\n{text}\n")
            
        context_str = "\n---\n".join(context_blocks)
        user_prompt = f"CONTEXT:\n{context_str}\n\nUSER QUESTION: {query}"
        
        return system_instruction, user_prompt

    @classmethod
    def generate_answer(cls, query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate grounded answer using configured LLM provider or smart rule-based fallback."""
        if not context_chunks:
            return {
                "answer": "I don't have enough information in the available company documentation to answer this question.",
                "raw_response": "No chunks provided",
                "provider": settings.LLM_PROVIDER
            }
            
        system_instruction, user_prompt = cls.build_prompt(query, context_chunks)
        
        # 1. Google Gemini Provider
        if settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
            candidate_models = [settings.LLM_MODEL, "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-pro-latest"]
            models_to_try = []
            for m in candidate_models:
                if m and m not in models_to_try:
                    models_to_try.append(m)

            prompt_content = f"{system_instruction}\n\n{user_prompt}"
            payload = {
                "contents": [{"parts": [{"text": prompt_content}]}],
                "generationConfig": {"temperature": 0.1}
            }
            headers = {"Content-Type": "application/json"}

            for model_name in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
                    res = requests.post(url, json=payload, headers=headers, timeout=30)
                    if res.status_code == 200:
                        data = res.json()
                        answer_text = data['candidates'][0]['content']['parts'][0]['text']
                        return {
                            "answer": answer_text,
                            "raw_response": answer_text,
                            "provider": f"gemini ({model_name})"
                        }
                    else:
                        print(f"[LLM] Gemini model '{model_name}' status {res.status_code}. Trying next candidate...")
                except Exception as e:
                    print(f"[LLM] Gemini API Exception for '{model_name}': {e}")

        # 2. OpenAI Provider
        if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            try:
                import openai
                client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1
                )
                answer_text = response.choices[0].message.content
                return {
                    "answer": answer_text,
                    "raw_response": answer_text,
                    "provider": "openai"
                }
            except Exception as e:
                print(f"[LLM] OpenAI API error: {e}. Falling back to Smart Extraction Engine.")

        # 3. Smart Grounded Extractor (Offline deterministic generator)
        return cls._generate_smart_mock(query, context_chunks)

    @classmethod
    def _generate_smart_mock(cls, query: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Deterministic grounded generator synthesizing detailed, structured answers with citations."""
        query_lower = query.lower()
        query_words = [w for w in re.findall(r'\b\w{3,}\b', query_lower) if w not in ["what", "where", "when", "which", "how", "who", "does", "have", "his", "her", "their", "the", "and", "are", "tell", "about"]]
        
        is_contact_query = any(k in query_lower for k in ["email", "phone", "contact", "linkedin", "github", "address"])

        # Intent Section Mapping
        intent = "general"
        if any(k in query_lower for k in ["skill", "tech", "language", "framework", "tool", "python", "react", "node", "sql"]):
            intent = "skills"
        elif any(k in query_lower for k in ["experienc", "work", "job", "role", "employment", "company", "career"]):
            intent = "experience"
        elif any(k in query_lower for k in ["project", "built", "system", "app", "platform"]):
            intent = "projects"
        elif any(k in query_lower for k in ["educat", "degree", "college", "university", "bachelor", "master", "study", "studied", "gpa"]):
            intent = "education"
        elif any(k in query_lower for k in ["certif", "course"]):
            intent = "certifications"
        elif any(k in query_lower for k in ["who", "about", "summary", "objective", "profile", "overview"]):
            intent = "summary"

        extracted_blocks = []
        seen_lines = set()

        for idx, chunk in enumerate(context_chunks, start=1):
            text = chunk.get("text", "").strip()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            i = 0
            while i < len(lines):
                line = lines[i]
                line_lower = line.lower()

                # Filter out isolated header names e.g. "THIRUWIN KARTHIK S" unless contact query
                if not is_contact_query and len(line.split()) <= 4 and ("email:" in text.lower() or "phone:" in text.lower()) and i < 2:
                    i += 1
                    continue

                is_match = False
                if intent == "skills" and any(k in line_lower for k in ["skill", "technol", "competenc", "tools", "framework"]):
                    is_match = True
                elif intent == "experience" and any(k in line_lower for k in ["experienc", "employment", "work", "history", "career"]):
                    is_match = True
                elif intent == "projects" and any(k in line_lower for k in ["project", "key project"]):
                    is_match = True
                elif intent == "education" and any(k in line_lower for k in ["educat", "academic", "qualification", "degree"]):
                    is_match = True
                elif intent == "certifications" and any(k in line_lower for k in ["certif", "course"]):
                    is_match = True
                elif intent == "summary" and any(k in line_lower for k in ["objective", "summary", "profile", "about"]):
                    is_match = True
                elif any(w in line_lower for w in query_words):
                    is_match = True

                if is_match:
                    title_candidate = line.split('.')[-1].strip().rstrip(':')
                    if not title_candidate or len(title_candidate) > 40:
                        title_candidate = next((w.capitalize() for w in query_words if w in line_lower), "Details")
                    section_title = title_candidate

                    content_items = []
                    j = i + 1
                    while j < len(lines):
                        nxt = lines[j]
                        nxt_lower = nxt.lower()
                        if (nxt.endswith(':') and len(nxt) < 35) or (len(nxt.split()) <= 3 and nxt.isupper() and j > i + 1):
                            break
                        if not is_contact_query and ("email:" in nxt_lower or "phone:" in nxt_lower or "linkedin:" in nxt_lower):
                            j += 1
                            continue
                        norm = re.sub(r'[^a-zA-Z0-9]', '', nxt_lower)
                        if norm not in seen_lines:
                            seen_lines.add(norm)
                            content_items.append(nxt)
                        j += 1

                    if content_items:
                        extracted_blocks.append((section_title, content_items, idx))
                        i = j - 1
                i += 1

        # Format final response
        if extracted_blocks:
            formatted_parts = []
            for title, items, chunk_idx in extracted_blocks[:3]:
                clean_items = []
                for it in items:
                    clean_it = re.sub(r'^[\*\-\d\.\•]+\s*', '', it).strip()
                    if clean_it and len(clean_it) > 3:
                        clean_items.append(f"• {clean_it}")
                
                if clean_items:
                    formatted_parts.append("\n".join(clean_items) + f" [{chunk_idx}]")
                else:
                    clean_text = " ".join([re.sub(r'^[\*\-\d\.\•]+\s*', '', it).strip() for it in items])
                    formatted_parts.append(f"• {clean_text} [{chunk_idx}]")

            answer = "\n".join(formatted_parts)
        else:
            matching_sentences = []
            for idx, chunk in enumerate(context_chunks, start=1):
                text = chunk.get("text", "")
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if len(s.strip()) > 15]
                for s in sentences:
                    s_lower = s.lower()
                    if not is_contact_query and ("email:" in s_lower or "phone:" in s_lower or "linkedin:" in s_lower or len(s.split()) <= 4):
                        continue
                    if any(w in s_lower for w in query_words):
                        norm = re.sub(r'[^a-zA-Z0-9]', '', s_lower)
                        if norm not in seen_lines:
                            seen_lines.add(norm)
                            matching_sentences.append((s, idx))

            if matching_sentences:
                selected = matching_sentences[:3]
                answer = " ".join([f"{s[0].rstrip('.')} [{s[1]}]." for s in selected])
            else:
                answer = "I don't have enough information in the available company documentation to answer this question."

        return {
            "answer": answer,
            "raw_response": answer,
            "provider": "smart_grounded_mock"
        }
