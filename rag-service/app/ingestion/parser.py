import re
import unicodedata
from typing import Dict, Any, List
import io

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

class DocumentParser:
    """Multi-format Document Parser and Normalizer."""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Clean and normalize raw extracted text."""
        if not text:
            return ""
        # Unicode normalization
        text = unicodedata.normalize("NFKD", text)
        # Fix broken lines and hyphens
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        # Normalize whitespace and blank lines
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Strip control characters
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch in ['\n', '\t'])
        return text.strip()

    @classmethod
    def parse_pdf(cls, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extract pages from PDF document with page-level metadata."""
        pages_content = []
        if PyPDF2 is not None:
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                for page_num, page in enumerate(reader.pages, start=1):
                    raw_text = page.extract_text() or ""
                    clean_text = cls.normalize_text(raw_text)
                    if clean_text:
                        lines = clean_text.split('\n')
                        section = lines[0][:80] if lines else f"Page {page_num}"
                        pages_content.append({
                            "source": filename,
                            "page": page_num,
                            "section": section,
                            "text": clean_text
                        })
            except Exception:
                pass
                
        if not pages_content:
            # Fallback text extraction if PDF reader unavailable or binary
            clean_text = cls.normalize_text(file_bytes.decode('utf-8', errors='ignore'))
            pages_content.append({
                "source": filename,
                "page": 1,
                "section": "Main Document",
                "text": clean_text
            })
        return pages_content

    @classmethod
    def parse_html(cls, html_content: str, filename: str) -> List[Dict[str, Any]]:
        """Extract sections from HTML document using headings."""
        if BeautifulSoup is not None:
            soup = BeautifulSoup(html_content, 'html.parser')
            sections = []
            for script in soup(["script", "style", "nav", "footer"]):
                script.extract()
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
            for h in headings:
                title = h.get_text(strip=True)
                content = []
                curr = h.next_sibling
                while curr and getattr(curr, 'name', None) not in ['h1', 'h2', 'h3', 'h4']:
                    if hasattr(curr, 'get_text'):
                        content.append(curr.get_text())
                    curr = curr.next_sibling
                section_text = cls.normalize_text(" ".join(content))
                if section_text:
                    sections.append({
                        "source": filename,
                        "page": 1,
                        "section": title,
                        "text": section_text
                    })
            if sections:
                return sections
                
        # Regex HTML fallback
        raw_text = re.sub(r'<[^>]+>', ' ', html_content)
        return [{"source": filename, "page": 1, "section": "Main", "text": cls.normalize_text(raw_text)}]


    @classmethod
    def parse_markdown(cls, md_text: str, filename: str) -> List[Dict[str, Any]]:
        """Extract sections from Markdown based on headers (# Header)."""
        clean_text = cls.normalize_text(md_text)
        sections = []
        current_section = "Introduction"
        current_lines = []
        
        for line in clean_text.split('\n'):
            if line.startswith('#'):
                if current_lines:
                    sec_text = "\n".join(current_lines).strip()
                    if sec_text:
                        sections.append({
                            "source": filename,
                            "page": 1,
                            "section": current_section,
                            "text": sec_text
                        })
                    current_lines = []
                current_section = line.lstrip('#').strip()
            else:
                current_lines.append(line)
                
        if current_lines:
            sec_text = "\n".join(current_lines).strip()
            if sec_text:
                sections.append({
                    "source": filename,
                    "page": 1,
                    "section": current_section,
                    "text": sec_text
                })
        return sections if sections else [{"source": filename, "page": 1, "section": "Main", "text": clean_text}]

    @classmethod
    def parse_text(cls, raw_text: str, filename: str) -> List[Dict[str, Any]]:
        """Parse plain text files."""
        clean_text = cls.normalize_text(raw_text)
        return [{"source": filename, "page": 1, "section": "General", "text": clean_text}]
