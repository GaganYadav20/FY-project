from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "IRIUM"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "super-secret-jwt-key-change-this-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    GROQ_API_KEY: str = ""
    MODEL_NAME: str = "llama3-8b-8192"
    LLM_TEMPERATURE: float = 0.2
    
    # LLM Provider Configuration
    LLM_PROVIDER: str = "nvidia"  # "groq", "gemini", or "nvidia"
    
    # NVIDIA NIM Configuration
    NVIDIA_API_KEY: str = ""
    NVIDIA_MODEL: str = "meta/llama-3.1-8b-instruct"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    
    # Gemini Configuration (Backup)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "models/gemini-3.6-flash"

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    VECTOR_STORE: str = "faiss"
    FAISS_INDEX_PATH: str = "./data/faiss_indexes"

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "fintech_research"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    DATABASE_URL: str = "sqlite:///./data/app.db"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"

    TAVILY_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""
    HUGGINGFACE_API_KEY: str = ""
    
    MARKETAUX_API_KEY: str = ""
    API_NINJAS_KEY: str = ""

    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "fintech_research"

    # Resend Email Configuration
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "IRIUM <onboarding@resend.dev>"

    LOG_LEVEL: str = "INFO"

    TOP_K: int = 5
    RERANK_TOP_K: int = 3
    SIMILARITY_THRESHOLD: float = 0.7

    MAX_SUB_QUESTIONS: int = 3
    MAX_REPORT_WORDS: int = 2000
    MAX_REVISIONS: int = 2

    CACHE_EXPIRY_SECONDS: int = 3600
    REQUEST_TIMEOUT: int = 30

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    UPLOAD_DIRECTORY: str = "./data/uploads"
    REPORT_DIRECTORY: str = "./data/reports"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()