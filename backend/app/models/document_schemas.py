from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str              # 'pdf' | 'image'
    page_count: Optional[int] = None
    uploaded_at: datetime
    status: Literal["processing", "ready", "failed"]


class DocumentQueryRequest(BaseModel):
    document_id: str
    query_text: str = Field(..., min_length=1, max_length=1000)


class SourceCitation(BaseModel):
    page: Optional[int] = None
    section: Optional[str] = None
    table: Optional[str] = None
    figure: Optional[str] = None


class DocumentQueryResponse(BaseModel):
    answer: str
    evidence: Optional[str] = None
    analysis: Optional[str] = None
    source: Optional[SourceCitation] = None
    calculation: Optional[str] = None
    not_found: bool = False       # true if info wasn't in the document


# Additional models for the main backend
class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    upload_timestamp: datetime
    chunk_count: int = 0
    status: str = "ready"


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int


class DocumentDeleteResponse(BaseModel):
    message: str
    document_id: str


# Chat-related document schemas for compatibility
class ChatDocumentQueryRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    top_k: int = 5


class ChatDocumentQueryResponse(BaseModel):
    reply: str
    sources: Optional[List[str]] = None