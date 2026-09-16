from datetime import datetime, timezone
import os
import uuid
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from app.models.schemas import (
    UserCreate, UserLogin, UserResponse, Token, RegisterResponse,
    VerifyEmailRequest, ChatQueryRequest, ChatQueryResponse,
    ChatSessionSummary, ChatSessionResponse, ChatSessionSaveRequest, ChatMessage
)
from app.models.document_schemas import (
    DocumentUploadResponse, DocumentInfo, DocumentListResponse,
    DocumentDeleteResponse, DocumentQueryRequest, DocumentQueryResponse
)
from app.database.db import UserRepository, ChatRepository
from app.database.documents import DocumentRepository, UPLOAD_DIR
from app.services.documents import get_document_service
from app.core.security import create_access_token
from app.api.dependencies import get_current_user, get_optional_current_user
from app.services.email import send_otp_email

logger = logging.getLogger("IRIUM_AUTH")
router = APIRouter(tags=["IRIUM API"])



@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Register a new user with compulsory full_name. Generates 6-digit OTP code requiring verification before login."""
    if not user_data.full_name or len(user_data.full_name.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full Name is compulsory (minimum 2 characters)"
        )

    if UserRepository.get_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    if UserRepository.get_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken"
        )
    
    user = UserRepository.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name
    )

    send_otp_email(
        to_email=user["email"],
        otp_code=user["verification_code"],
        user_name=user.get("full_name", "User"),
    )
    logger.info(f"Verification OTP generated and sent for {user['email']}")

    return RegisterResponse(
        message="Registration successful! Please enter the 6-digit verification code sent to your email.",
        email=user["email"],
        needs_verification=True
    )


@router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate user credentials. If email is unverified, block session and request OTP verification."""
    user = UserRepository.authenticate(credentials.username_or_email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_verified", False):
        if not user.get("verification_code"):
            code = UserRepository.resend_verification_code(user["email"])
        else:
            code = user["verification_code"]
        send_otp_email(
            to_email=user["email"],
            otp_code=code,
            user_name=user.get("full_name", "User"),
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"EMAIL_NOT_VERIFIED:{user['email']}"
        )

    access_token = create_access_token(data={"sub": user["id"], "username": user["username"], "email": user["email"]})

    user_response = UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        is_verified=user.get("is_verified", True),
        created_at=user["created_at"]
    )

    return Token(access_token=access_token, token_type="bearer", user=user_response)


@router.post("/auth/verify-and-login", response_model=Token)
async def verify_and_login(req: VerifyEmailRequest):
    """Verify 6-digit OTP code and issue JWT access token upon successful verification."""
    success = UserRepository.verify_email(req.email, req.code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )
    
    user = UserRepository.get_by_email(req.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = create_access_token(data={"sub": user["id"], "username": user["username"], "email": user["email"]})

    user_response = UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        is_verified=True,
        created_at=user["created_at"]
    )

    return Token(access_token=access_token, token_type="bearer", user=user_response)


@router.post("/auth/resend-verification")
async def resend_verification(email: str):
    """Resend a new 6-digit email verification code."""
    code = UserRepository.resend_verification_code(email)
    if not code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User email not found"
        )
    user = UserRepository.get_by_email(email)
    send_otp_email(
        to_email=email,
        otp_code=code,
        user_name=user.get("full_name", "User") if user else "User",
    )
    return {"status": "success", "message": f"A new 6-digit verification code has been sent to {email}."}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return profile details for the currently authenticated user."""
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        is_verified=current_user.get("is_verified", False),
        created_at=current_user["created_at"]
    )


# -------------------------------------------------------------
# CHAT SESSION MANAGEMENT
# -------------------------------------------------------------

@router.get("/chat/sessions", response_model=list[ChatSessionSummary])
async def get_chat_sessions(current_user: dict = Depends(get_current_user)):
    """Get list of all chat sessions for the authenticated user."""
    return ChatRepository.get_user_sessions(current_user["id"])


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific chat session with all its messages."""
    session = ChatRepository.get_session(current_user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.post("/chat/sessions", response_model=ChatSessionResponse)
async def save_chat_session(req: ChatSessionSaveRequest, current_user: dict = Depends(get_current_user)):
    """Create or update a chat session for the authenticated user."""
    session_dict = req.dict(exclude_unset=True)
    saved = ChatRepository.save_session(current_user["id"], session_dict)
    return saved


# -------------------------------------------------------------
# FINANCIAL DOCUMENTS MANAGEMENT & RAG
# -------------------------------------------------------------

@router.post("/documents/upload", response_model=DocumentListResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    current_user: dict | None = Depends(get_optional_current_user)
):
    """Upload one or multiple financial documents (PDF, DOCX, XLSX, CSV, TXT) and process/index them."""
    user_id = current_user["id"] if current_user else "guest_user"
    doc_service = get_document_service()
    results = []

    user_upload_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_upload_dir, exist_ok=True)

    for file in files:
        if not file.filename:
            continue

        safe_filename = Path(file.filename).name
        save_path = os.path.join(user_upload_dir, f"{uuid.uuid4().hex[:8]}_{safe_filename}")
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        file_size = len(content)
        ext = Path(safe_filename).suffix.lower()
        file_type = ext.replace(".", "").upper()

        try:
            processed = doc_service.process_document(
                user_id=user_id,
                file_path=save_path,
                filename=safe_filename,
                file_size=file_size
            )
            chunk_count = processed.get("chunk_count", 0)
            chunk_ids = processed.get("chunk_ids", [])

            doc_entry = DocumentRepository.create(
                user_id=user_id,
                filename=safe_filename,
                file_type=file_type,
                file_size=file_size,
                chunk_count=chunk_count,
                file_path=save_path
            )
            doc_service.link_chunks_to_document(user_id, doc_entry["id"], chunk_ids)

            results.append(DocumentInfo(
                document_id=doc_entry["id"],
                filename=safe_filename,
                file_type=file_type,
                file_size=file_size,
                upload_timestamp=doc_entry["upload_timestamp"],
                chunk_count=chunk_count,
                status="ready"
            ))
        except Exception as exc:
            logger.error(f"Error processing {safe_filename}: {exc}")
            doc_entry = DocumentRepository.create(
                user_id=user_id,
                filename=safe_filename,
                file_type=file_type,
                file_size=file_size,
                chunk_count=0,
                file_path=save_path
            )
            DocumentRepository.update_status(doc_entry["id"], "error")
            results.append(DocumentInfo(
                document_id=doc_entry["id"],
                filename=safe_filename,
                file_type=file_type,
                file_size=file_size,
                upload_timestamp=doc_entry["upload_timestamp"],
                chunk_count=0,
                status="error"
            ))

    all_docs = DocumentRepository.get_by_user(user_id)
    all_infos = [
        DocumentInfo(
            document_id=d["id"],
            filename=d["filename"],
            file_type=d["file_type"],
            file_size=d["file_size"],
            upload_timestamp=d["upload_timestamp"],
            chunk_count=d.get("chunk_count", 0),
            status=d.get("status", "ready")
        )
        for d in all_docs
    ]
    return DocumentListResponse(documents=all_infos, total=len(all_infos))


@router.get("/documents", response_model=DocumentListResponse)
async def get_documents(current_user: dict | None = Depends(get_optional_current_user)):
    """Get all uploaded financial documents for the current user."""
    user_id = current_user["id"] if current_user else "guest_user"
    docs = DocumentRepository.get_by_user(user_id)
    doc_infos = [
        DocumentInfo(
            document_id=d["id"],
            filename=d["filename"],
            file_type=d["file_type"],
            file_size=d["file_size"],
            upload_timestamp=d["upload_timestamp"],
            chunk_count=d.get("chunk_count", 0),
            status=d.get("status", "ready")
        )
        for d in docs
    ]
    return DocumentListResponse(documents=doc_infos, total=len(doc_infos))


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    current_user: dict | None = Depends(get_optional_current_user)
):
    """Delete an uploaded financial document and its indexed chunks."""
    user_id = current_user["id"] if current_user else "guest_user"
    doc = DocumentRepository.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    get_document_service().delete_user_document(user_id, document_id)

    if doc.get("file_path") and os.path.exists(doc["file_path"]):
        try:
            os.remove(doc["file_path"])
        except Exception:
            pass

    DocumentRepository.delete(document_id)
    return DocumentDeleteResponse(
        message=f"Document '{doc.get('filename')}' successfully removed",
        document_id=document_id
    )


@router.post("/documents/query", response_model=DocumentQueryResponse)
async def query_documents(
    req: DocumentQueryRequest,
    current_user: dict | None = Depends(get_optional_current_user)
):
    """Answer financial queries directly grounded in the user's uploaded documents."""
    user_id = current_user["id"] if current_user else "guest_user"
    doc_service = get_document_service()
    result = doc_service.query_user_documents(
        user_id=user_id,
        query=req.query,
        document_ids=req.document_ids,
        top_k=req.top_k
    )
    return DocumentQueryResponse(**result)


# -------------------------------------------------------------
# MAIN CHAT QUERY PROCESSOR
# -------------------------------------------------------------

@router.post("/chat/query", response_model=ChatQueryResponse)
async def process_chat_query(
    req: ChatQueryRequest,
    current_user: dict | None = Depends(get_optional_current_user)
):
    """Process user queries via in-chat attachments, document RAG, or multi-agent research workflow, and persist history."""
    query_str = (req.query or "").strip()
    attachments = req.attachments or []

    if not query_str and not attachments:
        raise HTTPException(status_code=400, detail="Query or attachment cannot be empty")

    session_id = req.session_id or f"session_{int(datetime.now().timestamp() * 1000)}"
    user_id = current_user["id"] if current_user else "guest_user"

    # Auto-save user message if user is authenticated
    if current_user:
        att_dicts = [a.dict() for a in attachments] if attachments else None
        ChatRepository.append_message(
            user_id=current_user["id"],
            session_id=session_id,
            message={
                "sender": "user",
                "text": query_str if query_str else f"Attached: {', '.join([a.name for a in attachments])}",
                "attachments": att_dicts
            }
        )

    # 1. Handle in-chat ChatGPT-style attachments first
    if attachments:
        doc_service = get_document_service()
        attachment_reply = doc_service.analyze_attachments(
            query=query_str,
            attachments=[a.dict() for a in attachments]
        )
        if current_user:
            ChatRepository.append_message(
                user_id=current_user["id"],
                session_id=session_id,
                message={"sender": "bot", "text": attachment_reply, "tier": "attachment"}
            )
        return ChatQueryResponse(
            query=query_str,
            reply=attachment_reply,
            tier="attachment",
            session_id=session_id
        )

    q_lower = query_str.lower()
    
    # 2. Handle greetings naturally
    greetings = ["hi", "hii", "hiii", "hello", "hey", "heyy", "good morning", "good afternoon", "good evening"]
    if q_lower in greetings or q_lower.startswith(("hi ", "hello ", "hey ")):
        greeting_reply = "Hello! How can I assist you with your financial research, market analysis, or document analysis today?"
        if current_user:
            ChatRepository.append_message(
                user_id=current_user["id"],
                session_id=session_id,
                message={"sender": "bot", "text": greeting_reply, "tier": "general"}
            )
        return ChatQueryResponse(
            query=query_str,
            reply=greeting_reply,
            tier="general",
            session_id=session_id
        )
    
    # 2.5. Handle unclear/ambiguous queries
    from app.graph.routing_logic import classify_tier
    quick_tier = classify_tier(query_str)
    
    if quick_tier == "unclear":
        unclear_reply = """I'd be happy to help! Could you please provide more details about what you'd like to know?

For example, you can ask me:
• **Stock prices:** "What is Reliance stock price?"
• **Definitions:** "What is EBITDA?" or "Explain mutual funds"
• **Comparisons:** "Difference between SEBI and RBI"
• **Rates:** "Current bank interest rates"
• **Analysis:** "Impact of RBI rate changes on economy"

What would you like to know about?"""
        
        if current_user:
            ChatRepository.append_message(
                user_id=current_user["id"],
                session_id=session_id,
                message={"sender": "bot", "text": unclear_reply, "tier": "general"}
            )
        return ChatQueryResponse(
            query=query_str,
            reply=unclear_reply,
            tier="general",
            session_id=session_id
        )

    # 3. Check for uploaded financial documents and document-related queries
    doc_service = get_document_service()
    user_docs = DocumentRepository.get_by_user(user_id)
    
    doc_triggers = [
        "document", "doc", "docs", "file", "files", "pdf", "csv", "xlsx", "sheet",
        "statement", "statements", "balance sheet", "income statement", "cash flow",
        "10-k", "10k", "10-q", "10q", "annual report", "earnings report", "uploaded",
        "according to", "in my file", "in the file", "in the doc", "portfolio"
    ]
    is_explicit_doc_query = any(trigger in q_lower for trigger in doc_triggers)
    
    if user_docs:
        chunks = doc_service.search_documents(user_id=user_id, query=query_str, top_k=5)
        if chunks and (is_explicit_doc_query or chunks[0]["score"] >= 4.0):
            logger.info(f"Routing query to financial document RAG engine (matching {len(chunks)} chunks)")
            doc_result = doc_service.query_user_documents(user_id=user_id, query=query_str, top_k=5)
            
            if current_user:
                ChatRepository.append_message(
                    user_id=current_user["id"],
                    session_id=session_id,
                    message={"sender": "bot", "text": doc_result["reply"], "tier": "document"}
                )

            return ChatQueryResponse(
                query=query_str,
                reply=doc_result["reply"],
                tier="document",
                session_id=session_id
            )


    # 3. Check API keys for multi-agent workflow
    from app.config import settings
    
    if settings.LLM_PROVIDER == "nvidia":
        if not settings.NVIDIA_API_KEY or settings.NVIDIA_API_KEY == "YOUR_NVIDIA_API_KEY_HERE":
            logger.error("NVIDIA_API_KEY not configured")
            error_reply = "System configuration error: NVIDIA_API_KEY is not configured. Please configure your API key in backend/.env file."
            if current_user:
                ChatRepository.append_message(
                    user_id=current_user["id"],
                    session_id=session_id,
                    message={"sender": "bot", "text": error_reply, "tier": "error"}
                )
            return ChatQueryResponse(
                query=query_str,
                reply=error_reply,
                tier="error",
                session_id=session_id
            )
    elif settings.LLM_PROVIDER == "gemini":
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            logger.error("GEMINI_API_KEY not configured")
            error_reply = "System configuration error: GEMINI_API_KEY is not configured. Please configure your API key in backend/.env file."
            if current_user:
                ChatRepository.append_message(
                    user_id=current_user["id"],
                    session_id=session_id,
                    message={"sender": "bot", "text": error_reply, "tier": "error"}
                )
            return ChatQueryResponse(
                query=query_str,
                reply=error_reply,
                tier="error",
                session_id=session_id
            )
    
    try:
        # Initialize tools with configuration
        from app.graph.tools import initialize_tools
        from app.graph.graph import execute_research_workflow
        
        tool_config = {
            "NVIDIA_API_KEY": settings.NVIDIA_API_KEY if settings.LLM_PROVIDER == "nvidia" else "",
            "NVIDIA_MODEL": settings.NVIDIA_MODEL if settings.LLM_PROVIDER == "nvidia" else "",
            "GEMINI_API_KEY": settings.GEMINI_API_KEY if settings.LLM_PROVIDER == "gemini" else "",
            "GEMINI_MODEL": settings.GEMINI_MODEL if settings.LLM_PROVIDER == "gemini" else "",
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "TAVILY_API_KEY": settings.TAVILY_API_KEY,
            "MARKETAUX_API_KEY": getattr(settings, "MARKETAUX_API_KEY", ""),
            "API_NINJAS_KEY": getattr(settings, "API_NINJAS_KEY", ""),
            "MODEL_NAME": settings.NVIDIA_MODEL if settings.LLM_PROVIDER == "nvidia" else settings.GEMINI_MODEL,
            "LLM_TEMPERATURE": settings.LLM_TEMPERATURE
        }
        
        tools = initialize_tools(tool_config)
        logger.info(f"Executing research workflow for query: {query_str}")
        
        # Retry logic with timeout (OPTION 2: Simple Mode)
        max_retries = 1
        timeout_seconds = 30  # Reduced timeout to 30 seconds for better UX
        
        for attempt in range(max_retries + 1):
            try:
                # Execute with timeout
                final_state = await asyncio.wait_for(
                    execute_research_workflow(
                        query=query_str,
                        domain="fintech",
                        tools=tools,
                        user_id=user_id if current_user else None,
                        session_id=session_id
                    ),
                    timeout=timeout_seconds
                )
                
                reply = final_state.get("final_answer", "Unable to process query")
                tier = final_state.get("tier", "unknown")
                
                # Check for errors in final state
                errors = final_state.get("errors", [])
                if errors and "embedding" in str(errors).lower():
                    logger.warning(f"Embedding errors detected: {errors}")
                
                # Enhance response with charts and structured data
                from app.services.visualization import get_visualization_service
                vis_service = get_visualization_service()
                
                # Get tool results from workflow state
                tool_results = []
                
                # Check if this was a simple lookup with direct tool results
                if final_state.get("tool_results"):
                    tool_results = final_state["tool_results"]
                elif final_state.get("search_results"):
                    # Complex workflow tool results
                    for result in final_state["search_results"]:
                        if result.get("tool_results"):
                            tool_results.extend(result["tool_results"])
                
                # Generate visuals
                charts, structured_data, metadata = vis_service.enhance_response_with_visuals(
                    query=query_str,
                    response_text=reply,
                    tool_results=tool_results
                )
                
                logger.info(f"Generated visuals: {len(charts)} charts, {len(structured_data)} data tables")
                
                logger.info(f"Workflow completed: tier={tier}, stage={final_state.get('current_stage')}")
                
                if current_user:
                    ChatRepository.append_message(
                        user_id=current_user["id"],
                        session_id=session_id,
                        message={"sender": "bot", "text": reply, "tier": tier}
                    )

                return ChatQueryResponse(
                    query=query_str,
                    reply=reply,
                    tier=tier,
                    session_id=session_id,
                    charts=charts,
                    structured_data=structured_data,
                    metadata=metadata
                )
                
            except asyncio.TimeoutError:
                logger.error(f"Workflow timeout on attempt {attempt + 1}/{max_retries + 1}")
                if attempt < max_retries:
                    logger.info(f"Retrying workflow (attempt {attempt + 2}/{max_retries + 1})")
                    await asyncio.sleep(1)  # Brief pause before retry
                    continue
                else:
                    # Max retries reached - use fallback
                    logger.error(f"Max retries reached after {max_retries + 1} attempts, using fallback")
                    break
                    
            except Exception as workflow_exc:
                logger.error(f"Workflow error on attempt {attempt + 1}: {workflow_exc}")
                if attempt < max_retries:
                    logger.info(f"Retrying after error (attempt {attempt + 2}/{max_retries + 1})")
                    await asyncio.sleep(1)  # Brief pause before retry
                    continue
                else:
                    # Max retries reached - use fallback
                    logger.error(f"Max retries reached after workflow errors, using fallback: {workflow_exc}")
                    break
        
        # If we get here, all retries failed - use fallback (OPTION 2: Simple Mode fallback)
        logger.warning("All workflow attempts failed, falling back to simple LLM response")
        
    except Exception as exc:
        logger.error(f"Query processing failed: {exc}", exc_info=True)
    
    # OPTION 2: Simple Mode - Direct LLM response when workflow fails
    try:
        from app.services.llm import get_llm_client
        llm = get_llm_client()
        
        # Check if query needs current data
        q_lower = query_str.lower()
        needs_current_data = any(term in q_lower for term in ["current", "latest", "2026", "rates", "price", "today", "now"])
        
        if needs_current_data:
            # Try to fetch current data for time-sensitive queries
            try:
                import httpx
                import json
                from app.config import settings
                
                # Use Tavily for current financial data
                tavily_key = settings.TAVILY_API_KEY
                if tavily_key:
                    search_query = f"{query_str} August 2026 current latest"
                    
                    logger.info(f"Attempting web search for current data: {search_query}")
                    
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "https://api.tavily.com/search",
                            json={
                                "api_key": tavily_key,
                                "query": search_query,
                                "search_depth": "basic",
                                "include_answer": True,
                                "max_results": 5
                            },
                            timeout=15
                        )
                        
                        if response.status_code == 200:
                            search_data = response.json()
                            
                            if search_data.get("answer"):
                                # Get raw web search results and format them properly
                                web_answer = search_data["answer"]
                                sources = search_data.get("results", [])
                                
                                # Use LLM to reformat the web answer in plain text
                                format_prompt = f"""Reformat this financial information into clean plain text format:

RESPONSE FORMAT RULES:
- Use ALL CAPS for section headings
- Use DASHES (-----) for separators  
- NO markdown asterisks (**)
- NO markdown tables with pipes (|)
- Use simple bullet points with dashes (-)

Raw Information:
{web_answer}

Reformat this into clean sections with current date context (August 2026)."""

                                try:
                                    format_response = await asyncio.wait_for(llm.ainvoke(format_prompt), timeout=10)
                                    formatted_content = format_response.content.strip()
                                    
                                    # Additional cleanup of any remaining markdown
                                    formatted_content = formatted_content.replace("**", "")
                                    formatted_content = formatted_content.replace("*", "")
                                    formatted_content = formatted_content.replace("|", "")
                                    formatted_content = formatted_content.replace("---", "")
                                    
                                except Exception as format_exc:
                                    logger.warning(f"Format cleanup failed: {format_exc}")
                                    formatted_content = web_answer.replace("**", "").replace("*", "").replace("|", "")
                                
                                fallback_reply = f"""CURRENT INFORMATION (August 2026)
------------------------------------------
{formatted_content}

DATA SOURCES
------------
Based on web search results from:"""
                                for i, source in enumerate(sources[:3], 1):
                                    title = source.get("title", "Unknown Source")
                                    url = source.get("url", "")
                                    fallback_reply += f"""
- {title}"""
                                
                                fallback_reply += f"""

IMPORTANT NOTE
--------------
Information retrieved from web search as of August 2026. Please verify with official sources before making financial decisions."""
                                
                                if current_user:
                                    ChatRepository.append_message(
                                        user_id=current_user["id"],
                                        session_id=session_id,
                                        message={"sender": "bot", "text": fallback_reply, "tier": "web_search"}
                                    )

                                return ChatQueryResponse(
                                    query=query_str,
                                    reply=fallback_reply,
                                    tier="web_search",
                                    session_id=session_id
                                )
                
            except Exception as web_exc:
                logger.warning(f"Web search failed: {web_exc}")
                # Continue to regular LLM fallback
        
        system_prompt = """You are IRIUM, an expert financial research AI assistant.

IMPORTANT CONTEXT:
- Current Date: August 17, 2026
- Always specify data age and when information might be outdated
- For company financials, prioritize the most recent available data (2024-2026 preferably)
- If you only have older data (before 2024), clearly state the data limitations

Your role is to provide accurate, current, and professional answers about:
- Financial concepts and definitions
- Stock market information and current trends
- Banking and financial products
- Economic indicators and recent changes
- Investment strategies and market analysis
- Company financial performance and growth metrics

DATA FRESHNESS REQUIREMENTS:
- When asked about company growth/performance, provide the most recent data available
- Always mention the time period of data being referenced
- If data is older than 2 years, acknowledge the limitation and suggest seeking current sources
- For stock prices, rates, or market data, indicate if information may not be real-time

CRITICAL - RESPONSE FORMAT - PLAIN TEXT ONLY:
- Use ALL CAPS for section headings (NO markdown asterisks)
- Use DASHES (------) for section separators
- NEVER use markdown tables with pipes (|)
- NEVER use markdown formatting like **text** or *text*
- Write in normal paragraphs without any markdown
- Use simple bullet points with dashes (-) for lists
- Do NOT create tables at all - use plain text lists instead

Example format:

EXECUTIVE OVERVIEW
------------------
Your main answer here in clear paragraphs.

CORE METRICS
------------
- Metric name: description
- Another metric: another description

INFLATION GROWTH AND MARKET OUTLOOK
-----------------------------------
- Key point one
- Key point two

DRIVERS AND POLICY RATIONALE
----------------------------
- Driver one: explanation
- Driver two: explanation

PRACTICAL IMPLICATIONS
----------------------
- Impact on borrowers: explanation
- Impact on savers: explanation
- Impact on businesses: explanation

CONCLUSION
----------
Summary paragraph."""
        
        prompt = f"{system_prompt}\n\nUser Question: {query_str}"
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=20)
        fallback_reply = response.content.strip()
        
        if current_user:
            ChatRepository.append_message(
                user_id=current_user["id"],
                session_id=session_id,
                message={"sender": "bot", "text": fallback_reply, "tier": "simple"}
            )

        return ChatQueryResponse(
            query=query_str,
            reply=fallback_reply,
            tier="simple",
            session_id=session_id
        )
        
    except asyncio.TimeoutError:
        logger.error("Simple LLM fallback also timed out (20s)")
        fallback_reply = "The system is currently experiencing delays. Please try your query again in a moment."
        
    except Exception as llm_exc:
        logger.error(f"Simple LLM fallback failed: {llm_exc}")
        
        # Ultimate fallback - predefined responses for common queries
        q_lower = query_str.lower()
        if "ebitda" in q_lower:
            fallback_reply = "EBITDA stands for Earnings Before Interest, Taxes, Depreciation, and Amortization. It measures a company's operating profitability by excluding financing costs, tax expenses, and non-cash depreciation and amortization charges."
        elif "nav" in q_lower or "net asset value" in q_lower:
            fallback_reply = "NAV (Net Asset Value) represents the per-share value of a mutual fund, calculated by dividing the total net asset value of the portfolio by the number of outstanding units."
        elif any(term in q_lower for term in ["home loan", "loan rate", "interest rate"]):
            fallback_reply = """HOME LOAN RATES COMPARISON
---------------------------

DATA LIMITATION NOTICE
----------------------
The system currently cannot access live 2026 banking data. For accurate current home loan rates as of August 2026, please:

RECOMMENDED ACTIONS
-------------------
- Visit bank websites directly (HDFC, ICICI, SBI, etc.)
- Call bank customer service for current rates
- Check RBI website for latest policy rates
- Use bank rate comparison websites

GENERAL INFORMATION (Historical Context)
----------------------------------------
Home loan rates in India typically range from 8% to 12% depending on:
- Bank policy and RBI rates
- Borrower credit score
- Loan amount and tenure
- Current economic conditions

IMPORTANT
---------
Interest rates change frequently based on RBI monetary policy. Always verify current rates before making financial decisions."""
        elif any(term in q_lower for term in ["stock", "share", "price"]):
            fallback_reply = "I'm currently experiencing technical difficulties accessing live market data. Please try again in a few moments or check your preferred financial data provider for current stock prices."
        else:
            fallback_reply = f"I'm experiencing technical difficulties processing your query. The system will try to resolve these issues. Please try again in a few moments."
    
    if current_user:
        ChatRepository.append_message(
            user_id=current_user["id"],
            session_id=session_id,
            message={"sender": "bot", "text": fallback_reply, "tier": "simple"}
        )
        
    return ChatQueryResponse(
        query=query_str,
        reply=fallback_reply,
        tier="simple",
        session_id=session_id
    )


# -------------------------------------------------------------
# FINANCIAL NEWS - FINNHUB API
# -------------------------------------------------------------

@router.get("/news/search")
async def search_news(
    q: str,
    limit: int = 50,
    current_user: dict | None = Depends(get_optional_current_user)
):
    """
    Search financial news using Finnhub API.
    
    Supports:
    - Company symbols (e.g., AAPL, TSLA, MSFT)
    - General keywords (e.g., inflation, tech stocks, merger)
    
    Args:
        q: Search query (company symbol or keywords)
        limit: Number of results (default: 50)
    """
    from app.config import settings
    from app.services.news import get_news_service
    
    if not q or not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )
    
    # Check if API key is configured
    finnhub_key = getattr(settings, "FINNHUB_API_KEY", "")
    if not finnhub_key:
        raise HTTPException(
            status_code=503,
            detail="Finnhub API key not configured. Please add FINNHUB_API_KEY to backend/.env file. Get a free key at https://finnhub.io/register"
        )
    
    try:
        news_service = get_news_service(finnhub_key)
        result = await news_service.search_news(query=q, limit=limit)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=502,
                detail=result.get("error", "Failed to search news")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error searching news: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search news: {str(exc)}"
        )
