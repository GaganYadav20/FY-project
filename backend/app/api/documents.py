from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import uuid
import shutil
from datetime import datetime

from app.models.document_schemas import (
    DocumentUploadResponse,
    DocumentQueryRequest,
    DocumentQueryResponse,
)
from app.services.document_processor import document_processor
from app.agents.document_analysis_agent import document_analysis_agent
import logging

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_MB = 25
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

# In-memory registry for the demo — swap for a documents table in
# Postgres if you want uploads to persist across restarts.
_document_store: dict[str, dict] = {}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max {MAX_FILE_SIZE_MB}MB.",
        )

    document_id = str(uuid.uuid4())
    saved_path = UPLOAD_DIR / f"{document_id}{ext}"
    with open(saved_path, "wb") as f:
        f.write(contents)

    try:
        pages = document_processor.process(str(saved_path))
    except Exception as e:
        logger.error("Failed to process uploaded document: %s", e)
        raise HTTPException(status_code=422, detail=f"Could not process file: {e}")

    _document_store[document_id] = {
        "file_path": str(saved_path),
        "filename": file.filename,
        "file_type": document_processor.detect_file_type(str(saved_path)),
        "pages": pages,
        "uploaded_at": datetime.utcnow(),
    }

    logger.info(
        "Document uploaded: id=%s filename=%s pages=%d",
        document_id, file.filename, len(pages),
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        file_type=_document_store[document_id]["file_type"],
        page_count=len(pages),
        uploaded_at=_document_store[document_id]["uploaded_at"],
        status="ready",
    )


@router.post("/query", response_model=DocumentQueryResponse)
async def query_document(request: DocumentQueryRequest):
    doc = _document_store.get(request.document_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found. Upload it first via /documents/upload.",
        )

    # Batch large documents so the vision call stays within context limits
    batches = document_processor.batch_pages(doc["pages"])

    if len(batches) == 1:
        return await document_analysis_agent(batches[0], request.query_text)

    # For multi-batch documents: query each batch, merge non-empty answers.
    # A production version would route only to the relevant batch based on
    # a lightweight page-index step; this keeps it simple for the prototype.
    results = []
    for batch in batches:
        result = await document_analysis_agent(batch, request.query_text)
        if not result.not_found:
            results.append(result)

    if not results:
        return DocumentQueryResponse(
            answer="I could not find this information in the uploaded document.",
            not_found=True,
        )

    return results[0]