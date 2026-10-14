from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/attr"

    # Пайплайн
    extractor: str = "regex"           # regex | gliner | llm | cascade
    confidence_threshold: float = 0.75 # ниже — в review

    # Tier 2: локальная LLM (Ollama)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # Tier 3: облачная LLM
    cloud_llm_key: str | None = None
    cloud_llm_model: str = "gpt-4o-mini"

    # MCP
    mcp_server_url: str = "http://localhost:8001/mcp"

    # CORS
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()