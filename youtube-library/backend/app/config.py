from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://ytlib:ytlib_secret@localhost:9072/youtube_library"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 9073
    qdrant_collection: str = "youtube_transcripts"

    # LLM API (OpenAI-compatible endpoint; defaults target the optional
    # local llama-server from docker-compose --profile llm)
    llm_api_base: str = "http://localhost:9075/v1"
    llm_api_key: str = "sk-no-key-required"
    llm_chat_model: str = "gpt-oss-20b"
    llm_utility_model: str = "gpt-oss-20b"

    # Data directories
    data_dir: str = "/data"

    # Whisper
    whisper_model: str = "medium"

    # Embedding model (served by the LLM API)
    embedding_model: str = "bge-m3"

    # Language for LLM output (summaries, refinement, chat): "de" or "en"
    language: str = "de"

    # Scheduler
    check_interval_hours: int = 1

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
