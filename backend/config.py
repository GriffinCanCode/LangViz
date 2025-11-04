"""Application configuration management.

Loads settings from environment with validation.
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "langviz"
    postgres_user: str = Field(default_factory=lambda: os.getenv("USER", "postgres"))
    postgres_password: str = ""
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    
    # gRPC Services
    parser_service_host: str = "localhost"
    parser_service_port: int = 50051
    
    # API
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    cors_origins: list[str] = Field(default=["http://localhost:5173"])
    
    # Models
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    
    # Development
    debug: bool = False
    log_level: str = "INFO"
    
    @property
    def database_url(self) -> str:
        """PostgreSQL connection URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

