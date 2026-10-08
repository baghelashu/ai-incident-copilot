"""Model factories. `offline` mode needs no API key or local model."""

import hashlib
import math
import re

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from copilot.config import Settings

_TOKEN = re.compile(r"[a-z][a-z0-9_]+")


class HashingEmbeddings(Embeddings):
    """Bag-of-words feature hashing: deterministic, dependency-free embeddings for offline use."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN.findall(text.lower()):
            digest = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[digest % self.dim] += 1.0 if (digest >> 8) & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def get_embeddings(settings: Settings) -> Embeddings:
    if settings.llm_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=settings.openai_embed_model)
    if settings.llm_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=settings.ollama_embed_model, base_url=settings.ollama_base_url)
    return HashingEmbeddings()


def get_chat_model(settings: Settings) -> BaseChatModel | None:
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.openai_model, temperature=0)
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url, temperature=0)
    return None
