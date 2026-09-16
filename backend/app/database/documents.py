import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DOCUMENTS_FILE = os.path.join(DATA_DIR, "documents.json")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if not os.path.exists(DOCUMENTS_FILE):
        with open(DOCUMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def load_documents() -> Dict[str, Dict[str, Any]]:
    _ensure_dirs()
    try:
        with open(DOCUMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_documents(docs: Dict[str, Dict[str, Any]]):
    _ensure_dirs()
    with open(DOCUMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2)


class DocumentRepository:
    @staticmethod
    def create(
        user_id: str,
        filename: str,
        file_type: str,
        file_size: int,
        chunk_count: int = 0,
        file_path: str = ""
    ) -> Dict[str, Any]:
        docs = load_documents()
        doc_id = str(uuid.uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": doc_id,
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "file_path": file_path,
            "chunk_count": chunk_count,
            "upload_timestamp": now_str,
            "status": "ready" if chunk_count > 0 else "processing",
        }
        docs[doc_id] = doc
        save_documents(docs)
        return doc

    @staticmethod
    def get_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
        docs = load_documents()
        return docs.get(doc_id)

    @staticmethod
    def get_by_user(user_id: str) -> List[Dict[str, Any]]:
        docs = load_documents()
        return [d for d in docs.values() if d.get("user_id") == user_id]

    @staticmethod
    def delete(doc_id: str) -> bool:
        docs = load_documents()
        if doc_id in docs:
            del docs[doc_id]
            save_documents(docs)
            return True
        return False

    @staticmethod
    def update_status(doc_id: str, status: str, chunk_count: int = None):
        docs = load_documents()
        if doc_id in docs:
            docs[doc_id]["status"] = status
            if chunk_count is not None:
                docs[doc_id]["chunk_count"] = chunk_count
            save_documents(docs)
