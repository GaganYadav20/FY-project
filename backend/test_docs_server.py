#!/usr/bin/env python3

import os
import sys
import uvicorn
from pathlib import Path

# Add the current directory to Python path so we can import our modules
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Set environment variables before importing FastAPI app
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("APP_NAME", "IRIUM Document Analysis")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("HOST", "0.0.0.0")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault("ALLOWED_ORIGINS", "*")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import our document analysis modules
from app.api.documents import router as documents_router

app = FastAPI(
    title="IRIUM Document Analysis API",
    version="1.0.0",
    description="Document Analysis API with Qwen2-VL"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include document analysis router
app.include_router(documents_router, prefix="/api")

@app.get("/")
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "IRIUM Document Analysis API",
        "version": "1.0.0",
        "environment": "development"
    }

if __name__ == "__main__":
    print("Starting IRIUM Document Analysis Server...")
    print("Document Analysis API will be available at:")
    print("  - Upload: http://localhost:8000/api/documents/upload")
    print("  - Query: http://localhost:8000/api/documents/query")
    print("  - Health: http://localhost:8000/api/health")
    
    uvicorn.run(
        "test_docs_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(current_dir)],
        log_level="info"
    )