from __future__ import annotations
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "it_knowledge_base"
    mock_llm: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

settings = Settings()
