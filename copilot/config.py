from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="COPILOT_", extra="ignore")

    llm_provider: str = "offline"  # offline | ollama | openai
    ollama_model: str = "llama3.1"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    knowledge_dir: Path = ROOT_DIR / "data"
    index_dir: Path = ROOT_DIR / ".faiss_index"
    retrieval_k: int = 4
    anomaly_z_threshold: float = 3.0
    anomaly_min_errors: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
