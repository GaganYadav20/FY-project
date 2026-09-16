"""
Document Service - Handles document parsing, chunking, indexing, retrieval, and LLM Q&A.
Supports PDF, DOCX, XLSX, CSV, and TXT financial documents.
"""

from __future__ import annotations

import os
import re
import csv
import json
import uuid
import math
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import Counter

from app.config import settings
from app.database.documents import DocumentRepository

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".doc": "DOCX",
    ".txt": "TEXT",
    ".csv": "CSV",
    ".xlsx": "XLSX",
    ".xls": "XLSX",
}

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


class DocumentServiceError(Exception):
    """Custom exception for document service errors."""
    pass


class DocumentService:
    """Service for processing financial documents and answering queries grounded in them."""

    def __init__(self):
        self._chunk_stores: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _get_user_chunks_path(self, user_id: str) -> str:
        """Get chunks JSON path for a user."""
        index_dir = os.path.join(settings.FAISS_INDEX_PATH, user_id)
        os.makedirs(index_dir, exist_ok=True)
        return os.path.join(index_dir, "chunks.json")

    def _load_user_chunks(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Load user chunks store from disk or cache."""
        if user_id in self._chunk_stores:
            return self._chunk_stores[user_id]

        chunks_path = self._get_user_chunks_path(user_id)
        chunks = {}
        if os.path.exists(chunks_path):
            try:
                with open(chunks_path, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load chunks file for {user_id}: {e}")
                chunks = {}

        self._chunk_stores[user_id] = chunks
        return chunks

    def _save_user_chunks(self, user_id: str):
        """Persist chunks store to disk."""
        chunks = self._chunk_stores.get(user_id, {})
        chunks_path = self._get_user_chunks_path(user_id)
        try:
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user chunks: {e}")

    def _extract_text_from_file(self, file_path: str, file_type: str) -> str:
        """Extract text content from uploaded file."""
        ext = Path(file_path).suffix.lower()
        text = ""

        try:
            if ext == ".pdf":
                text = self._extract_pdf(file_path)
            elif ext in [".docx", ".doc"]:
                text = self._extract_docx(file_path)
            elif ext == ".txt":
                text = self._extract_txt(file_path)
            elif ext == ".csv":
                text = self._extract_csv(file_path)
            elif ext in [".xlsx", ".xls"]:
                text = self._extract_xlsx(file_path)
            else:
                raise DocumentServiceError(f"Unsupported file type: {ext}")

            if not text or not text.strip():
                raise DocumentServiceError(f"No extractable text found in {os.path.basename(file_path)}")

            return text.strip()

        except DocumentServiceError:
            raise
        except Exception as exc:
            logger.error(f"Text extraction failed for {file_path}: {exc}")
            raise DocumentServiceError(f"Text extraction failed: {exc}")

    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF using PyMuPDF with PyPDF fallback."""
        # 1. Try PyMuPDF
        try:
            import fitz  # pymupdf
            doc = fitz.open(file_path)
            pages = []
            for i, page in enumerate(doc):
                page_text = page.get_text()
                if page_text and page_text.strip():
                    pages.append(f"--- [Page {i+1}] ---\n{page_text.strip()}")
            doc.close()
            if pages:
                return "\n\n".join(pages)
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed for {file_path}, attempting pypdf fallback: {e}")

        # 2. Fallback to pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            pages = []
            for i, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    pages.append(f"--- [Page {i+1}] ---\n{extracted.strip()}")
            if pages:
                return "\n\n".join(pages)
        except Exception as e:
            logger.error(f"pypdf extraction also failed for {file_path}: {e}")

        raise DocumentServiceError("Could not extract readable text from PDF")

    def _extract_docx(self, file_path: str) -> str:
        """Extract text & tables from DOCX using python-docx."""
        try:
            import docx
            doc = docx.Document(file_path)
            parts = []

            # Paragraphs
            for p in doc.paragraphs:
                if p.text.strip():
                    parts.append(p.text.strip())

            # Tables (vital for financial statements)
            for t_idx, table in enumerate(doc.tables):
                parts.append(f"\n--- [Table {t_idx+1}] ---")
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells]
                    if any(row_cells):
                        parts.append(" | ".join(row_cells))

            return "\n\n".join(parts)
        except Exception as exc:
            raise DocumentServiceError(f"DOCX extraction failed: {exc}")

    def _extract_txt(self, file_path: str) -> str:
        """Extract text from plain text file."""
        for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except Exception:
                continue
        raise DocumentServiceError("Failed to decode text file with standard encodings")

    def _extract_csv(self, file_path: str) -> str:
        """Extract text from CSV formatting each row as structured tabular data."""
        for encoding in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
            try:
                rows_text = []
                with open(file_path, "r", encoding=encoding, errors="replace") as f:
                    reader = csv.reader(f)
                    for idx, row in enumerate(reader):
                        if any(cell.strip() for cell in row):
                            rows_text.append(f"Row {idx+1}: " + " | ".join(row))
                if rows_text:
                    return "\n".join(rows_text)
            except Exception:
                continue
        raise DocumentServiceError("Failed to parse CSV file")

    def _extract_xlsx(self, file_path: str) -> str:
        """Extract text and financial tables from XLSX worksheets using openpyxl."""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            sheets_text = []
            for sheetname in wb.sheetnames:
                ws = wb[sheetname]
                sheet_lines = [f"=== Sheet: {sheetname} ==="]
                for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
                    row_vals = [str(val).strip() for val in row if val is not None and str(val).strip()]
                    if row_vals:
                        sheet_lines.append(f"Row {r_idx+1}: " + " | ".join(row_vals))
                if len(sheet_lines) > 1:
                    sheets_text.append("\n".join(sheet_lines))
            wb.close()
            return "\n\n".join(sheets_text)
        except Exception as exc:
            raise DocumentServiceError(f"XLSX extraction failed: {exc}")

    def _chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """Split text into logical, overlapping chunks with boundary detection."""
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            if end < len(text):
                # Try breaking at paragraph or sentence or newline boundary
                break_point = -1
                for delimiter in ["\n\n", ".\n", ". ", "\n", " | "]:
                    pos = chunk.rfind(delimiter)
                    if pos > chunk_size * 0.4:
                        break_point = pos + len(delimiter)
                        break
                if break_point != -1:
                    chunk = chunk[:break_point]
                    end = start + break_point

            clean_chunk = chunk.strip()
            if clean_chunk:
                chunks.append(clean_chunk)
            start = end - overlap

        return chunks if chunks else [text]

    def process_document(self, user_id: str, file_path: str, filename: str, file_size: int) -> Dict[str, Any]:
        """Process and index an uploaded financial document."""
        ext = Path(file_path).suffix.lower()
        file_type = SUPPORTED_EXTENSIONS.get(ext, "UNKNOWN")

        if file_type == "UNKNOWN":
            raise DocumentServiceError(f"Unsupported file type: {ext}. Supported: PDF, DOCX, XLSX, CSV, TXT")

        # 1. Extract text
        raw_text = self._extract_text_from_file(file_path, file_type)

        # 2. Chunk text
        chunks = self._chunk_text(raw_text)
        if not chunks:
            raise DocumentServiceError(f"Document produced no readable content: {filename}")

        # 3. Store chunks under user
        chunk_store = self._load_user_chunks(user_id)
        chunk_ids = []
        for idx, chunk_text in enumerate(chunks):
            chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
            chunk_store[chunk_id] = {
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "text": chunk_text,
                "document_id": None,  # Linked afterwards
                "filename": filename,
                "file_type": file_type,
            }
            chunk_ids.append(chunk_id)

        self._save_user_chunks(user_id)
        logger.info(f"Processed document {filename} for user {user_id}: {len(chunks)} chunks")

        return {
            "chunk_count": len(chunks),
            "chunk_ids": chunk_ids,
        }

    def link_chunks_to_document(self, user_id: str, doc_id: str, chunk_ids: List[str]):
        """Link chunk entries to their parent document ID."""
        chunk_store = self._load_user_chunks(user_id)
        for cid in chunk_ids:
            if cid in chunk_store:
                chunk_store[cid]["document_id"] = doc_id
        self._save_user_chunks(user_id)

    def search_documents(
        self,
        user_id: str,
        query: str,
        top_k: int = 6,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search indexed documents using hybrid relevance scoring."""
        chunk_store = self._load_user_chunks(user_id)
        if not chunk_store:
            return []

        # Tokenize query
        q_tokens = [t.lower() for t in re.findall(r'\w+', query) if len(t) > 1]
        if not q_tokens:
            return []

        q_counter = Counter(q_tokens)
        q_lower = query.lower()

        scored_results = []
        for chunk_id, chunk_data in chunk_store.items():
            if document_ids and chunk_data.get("document_id") not in document_ids:
                continue

            text = chunk_data.get("text", "")
            text_lower = text.lower()
            filename_lower = chunk_data.get("filename", "").lower()

            # 1. Exact phrase boost
            score = 0.0
            if q_lower in text_lower:
                score += 5.0

            # 2. Filename match boost (e.g. asking specifically about "Tesla" or "10K")
            for token in q_tokens:
                if token in filename_lower:
                    score += 2.0

            # 3. Token frequency & TF-IDF term overlap
            text_tokens = re.findall(r'\w+', text_lower)
            text_counter = Counter(text_tokens)
            doc_len = max(len(text_tokens), 1)

            for token, count in q_counter.items():
                if token in text_counter:
                    tf = text_counter[token] / doc_len
                    # Weight numbers & financial tickers heavier
                    weight = 2.0 if token.isnumeric() or len(token) >= 4 else 1.0
                    score += (tf * 100.0) * weight

            if score > 0.0:
                scored_results.append({
                    "chunk_id": chunk_id,
                    "document_id": chunk_data.get("document_id"),
                    "filename": chunk_data.get("filename"),
                    "file_type": chunk_data.get("file_type"),
                    "text": text,
                    "score": round(score, 4)
                })

        # Sort by relevance score descending
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def query_user_documents(
        self,
        user_id: str,
        query: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 6
    ) -> Dict[str, Any]:
        """Answer a financial query directly grounded in the user's uploaded documents."""
        # 1. Search relevant chunks
        chunks = self.search_documents(user_id=user_id, query=query, top_k=top_k, document_ids=document_ids)

        if not chunks:
            # Check if user has ANY documents uploaded
            all_user_docs = DocumentRepository.get_by_user(user_id)
            if not all_user_docs:
                return {
                    "query": query,
                    "reply": "No financial documents have been uploaded yet. Please upload your documents (PDF, CSV, XLSX, DOCX, TXT) to ask document-specific questions.",
                    "source_chunks": [],
                    "documents_used": [],
                    "tier": "document"
                }
            else:
                doc_names = ", ".join([d.get("filename", "") for d in all_user_docs])
                return {
                    "query": query,
                    "reply": f"I reviewed your uploaded documents ({doc_names}), but did not find specific excerpts matching your query '{query}'. Please verify your query or specify which metrics/sections you are looking for.",
                    "source_chunks": [],
                    "documents_used": [d.get("filename", "") for d in all_user_docs],
                    "tier": "document"
                }

        # 2. Build context from top chunks with explicit document headers
        context_parts = []
        docs_used_set = set()
        for idx, chunk in enumerate(chunks):
            fname = chunk.get("filename", "Document")
            docs_used_set.add(fname)
            context_parts.append(
                f"--- [EXCERPT {idx+1} from '{fname}'] ---\n{chunk.get('text')}\n"
            )

        context_text = "\n".join(context_parts)
        docs_list_str = ", ".join(sorted(docs_used_set))

        # 3. Formulate Prompt for LLM
        prompt = f"""You are IRIUM, an expert AI Financial Research Analyst.
The user has uploaded the following financial document(s): {docs_list_str}.

Answer the user's query thoroughly, precisely, and objectively, GROUNDED ENTIRELY in the provided document excerpts.

### GUIDELINES:
1. Provide concrete numbers, percentages, balance sheet data, financial metrics, and exact facts found in the excerpts.
2. Clearly cite the source document filename (e.g. `[Source: {list(docs_used_set)[0]}]`) when referencing facts or figures.
3. If comparing multiple documents (e.g., Q1 vs Q2, Company A vs Company B), structure your analysis with clear headings or bulleted comparison tables.
4. If a specific figure is not mentioned in the excerpts, state clearly that it is not available in the uploaded text rather than guessing.

---
### DOCUMENT EXCERPTS:
{context_text}
---

### USER QUERY:
"{query}"

### FINANCIAL ANALYST ANSWER:"""

        # 4. Generate response with LLM
        try:
            from langchain_groq import ChatGroq
            llm = ChatGroq(model=settings.MODEL_NAME, api_key=settings.GROQ_API_KEY, temperature=0.2)
            response = llm.invoke(prompt)
            reply = response.content.strip()
        except Exception as e:
            logger.error(f"LLM generation failed for document query: {e}")
            reply = f"Here is the relevant excerpt found in your uploaded documents ({docs_list_str}):\n\n" + chunks[0]["text"][:600] + "..."

        return {
            "query": query,
            "reply": reply,
            "source_chunks": chunks,
            "documents_used": list(docs_used_set),
            "tier": "document"
        }

    def analyze_attachments(self, query: str, attachments: List[Dict[str, Any]]) -> str:
        """Process and answer queries on ChatGPT-style in-chat image and document attachments."""
        import base64
        import io

        extracted_parts = []
        attachment_names = []

        for att in attachments:
            name = att.get("name", "uploaded_file")
            att_type = (att.get("type") or "").lower()
            raw_data = att.get("data") or ""
            attachment_names.append(name)

            # Strip data URL prefix if present (e.g. data:image/png;base64,...)
            if "," in raw_data:
                b64_str = raw_data.split(",", 1)[1]
            else:
                b64_str = raw_data

            try:
                file_bytes = base64.b64decode(b64_str)
            except Exception as e:
                logger.warning(f"Failed to decode base64 for {name}: {e}")
                file_bytes = b""

            file_ext = Path(name).suffix.lower()

            # 1. PDF File
            if file_ext == ".pdf" or "pdf" in att_type:
                pdf_text = ""
                try:
                    import fitz
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    pages = []
                    for i, page in enumerate(doc):
                        t = page.get_text()
                        if t and t.strip():
                            pages.append(f"--- [Page {i+1}] ---\n{t.strip()}")
                    doc.close()
                    pdf_text = "\n\n".join(pages)
                except Exception:
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(io.BytesIO(file_bytes))
                        pages = [f"--- [Page {i+1}] ---\n{p.extract_text()}" for i, p in enumerate(reader.pages) if p.extract_text()]
                        pdf_text = "\n\n".join(pages)
                    except Exception as e:
                        pdf_text = f"[Error reading PDF: {e}]"

                extracted_parts.append(f"=== ATTACHED PDF: {name} ===\n{pdf_text}")

            # 2. Image File
            elif "image" in att_type or file_ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]:
                img_info = f"=== ATTACHED FINANCIAL IMAGE: {name} ({len(file_bytes)} bytes) ==="
                # Try reading basic image dimensions / OCR if possible
                try:
                    import fitz
                    pix = fitz.Pixmap(file_bytes)
                    img_info += f"\nImage Dimensions: {pix.width}x{pix.height}, Channels: {pix.n}"
                except Exception:
                    pass
                extracted_parts.append(img_info)

            # 3. CSV File
            elif file_ext == ".csv" or "csv" in att_type:
                try:
                    text_content = file_bytes.decode("utf-8", errors="replace")
                    reader = csv.reader(io.StringIO(text_content))
                    rows = [f"Row {idx+1}: " + " | ".join(r) for idx, r in enumerate(reader) if any(r)]
                    extracted_parts.append(f"=== ATTACHED CSV: {name} ===\n" + "\n".join(rows))
                except Exception as e:
                    extracted_parts.append(f"=== ATTACHED CSV: {name} ===\n[Error parsing CSV: {e}]")

            # 4. Plain text / Markdown / JSON
            else:
                try:
                    text_content = file_bytes.decode("utf-8", errors="replace")
                    extracted_parts.append(f"=== ATTACHED FILE: {name} ===\n{text_content}")
                except Exception:
                    extracted_parts.append(f"=== ATTACHED FILE: {name} ({len(file_bytes)} bytes) ===")

        all_context = "\n\n".join(extracted_parts)
        user_prompt = query.strip() if query and query.strip() else "Analyze and explain the key findings, numbers, and takeaways from this uploaded file."
        files_str = ", ".join(attachment_names)

        llm_prompt = f"""You are IRIUM, an expert AI Financial Research Assistant.
The user has attached the following file(s) to this chat message: {files_str}.

### ATTACHED FILE CONTENT:
{all_context}

### USER QUESTION:
"{user_prompt}"

### INSTRUCTIONS:
1. Ground your response directly on the content, data, metrics, or tables in the attached file(s).
2. Quote exact numbers, financial metrics, dates, and findings.
3. Structure your response clearly with bold highlights and bullet points.
4. If asked to explain the file or what it contains, provide an executive breakdown.

FINANCIAL ANALYST RESPONSE:"""

        try:
            from langchain_groq import ChatGroq
            llm = ChatGroq(model=settings.MODEL_NAME, api_key=settings.GROQ_API_KEY, temperature=0.2)
            response = llm.invoke(llm_prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate attachment analysis: {e}")
            if extracted_parts:
                return f"Here is the content extracted from **{files_str}**:\n\n" + extracted_parts[0][:1000] + "..."
            return f"Processed uploaded file **{files_str}**. Please let me know what specific figures you would like me to analyze."

    def delete_user_document(self, user_id: str, doc_id: str):
        """Remove document chunks from the user's index and storage."""
        chunk_store = self._load_user_chunks(user_id)
        to_delete = [cid for cid, c in chunk_store.items() if c.get("document_id") == doc_id]
        for cid in to_delete:
            chunk_store.pop(cid, None)
        self._save_user_chunks(user_id)


_document_service = None


def get_document_service() -> DocumentService:
    """Get or create document service singleton."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service

