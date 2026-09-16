from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=100)


class UserLogin(BaseModel):
    username_or_email: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: str
    is_verified: bool = False
    created_at: str


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr
    needs_verification: bool = True


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    sub: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None


class AttachmentItem(BaseModel):
    name: str
    type: str = "application/pdf"
    data: Optional[str] = None  # base64 string or data URL
    size: Optional[int] = 0


class ChatMessage(BaseModel):
    id: Optional[str] = None
    sender: str
    text: str
    tier: Optional[str] = None
    created_at: Optional[str] = None
    attachments: Optional[list[AttachmentItem]] = None


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage] = []


class ChatSessionSaveRequest(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = "New Chat"
    created_at: Optional[str] = None
    messages: list[ChatMessage] = []


class ChatQueryRequest(BaseModel):
    query: str = Field(default="")
    session_id: Optional[str] = None
    attachments: Optional[list[AttachmentItem]] = []


class ChartData(BaseModel):
    type: str = Field(..., description="Chart type: line, bar, pie, candlestick")
    title: str = Field(..., description="Chart title")
    data: Dict[str, Any] = Field(..., description="Chart data structure")
    config: Optional[Dict[str, Any]] = Field(default={}, description="Chart configuration options")


class StructuredData(BaseModel):
    type: str = Field(..., description="Data type: stock, financial_metrics, table, etc.")
    title: str = Field(..., description="Data section title") 
    data: Dict[str, Any] = Field(..., description="Structured data")


class ChatQueryResponse(BaseModel):
    query: str
    reply: str
    tier: str = "general"
    session_id: Optional[str] = None
    attachments: Optional[list[AttachmentItem]] = None
    charts: Optional[List[ChartData]] = Field(default=[], description="Charts/visualizations to display")
    structured_data: Optional[List[StructuredData]] = Field(default=[], description="Structured data tables/metrics")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional response metadata")



