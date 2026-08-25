from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lenny Growth Assistant"
    environment: str = "development"

    database_url: str = (
        "postgresql+asyncpg://lenny:lenny_dev@localhost:5433/lenny_growth"
    )

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

    agent_provider: str = "ollama"
    agent_model: str = "llama3.2:3b"
    agent_executable: str = "pi"
    agent_timeout_seconds: float = 120.0

    artifact_model: str = "qwen3:4b-instruct"
    artifact_timeout_seconds: float = 300.0

    cloud_provider: str = "openai"
    cloud_model: str = "gpt-5.4-mini"
    cloud_fallback_enabled: bool = False

    openai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
