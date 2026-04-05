"""
Application configuration loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+pymysql://root:rootpass@127.0.0.1:3307/docx_agent")

    # Legacy DashScope/Qwen settings kept for backward compatibility
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_BASE_URL: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # Unified LLM settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "qwen")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", DASHSCOPE_API_KEY)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", DASHSCOPE_BASE_URL)
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-plus")

    # Provider-specific defaults
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", DASHSCOPE_API_KEY or LLM_API_KEY)
    QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", DASHSCOPE_BASE_URL)
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-plus")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", LLM_API_KEY)
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", LLM_API_KEY)
    GEMINI_BASE_URL: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # ChromaDB
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

    # File Storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")

    # JWT Auth
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "docx-agent-super-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    def get_provider_api_key(self, provider: str) -> str:
        provider = (provider or "").strip().lower()
        if provider == "qwen":
            return self.QWEN_API_KEY or self.LLM_API_KEY
        if provider == "chatgpt":
            return self.OPENAI_API_KEY or self.LLM_API_KEY
        if provider == "gemini":
            return self.GEMINI_API_KEY or self.LLM_API_KEY
        return self.LLM_API_KEY

    def get_provider_base_url(self, provider: str) -> str | None:
        provider = (provider or "").strip().lower()
        if provider == "qwen":
            return self.QWEN_BASE_URL
        if provider == "chatgpt":
            return self.OPENAI_BASE_URL or None
        if provider == "gemini":
            return self.GEMINI_BASE_URL
        return self.LLM_BASE_URL or None

    def get_provider_model(self, provider: str) -> str:
        provider = (provider or "").strip().lower()
        if provider == "qwen":
            return self.QWEN_MODEL
        if provider == "chatgpt":
            return self.OPENAI_MODEL
        if provider == "gemini":
            return self.GEMINI_MODEL
        return self.LLM_MODEL


settings = Settings()
