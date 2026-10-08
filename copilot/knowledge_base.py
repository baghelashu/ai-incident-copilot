"""FAISS vector store over runbooks and past incident reports (markdown)."""

from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from copilot.config import Settings
from copilot.llm import get_embeddings


def load_documents(knowledge_dir: Path) -> list[Document]:
    docs = []
    for path in sorted(knowledge_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        docs.append(Document(page_content=text, metadata={"source": str(path.relative_to(knowledge_dir)), "title": title, "kind": path.parent.name}))
    return docs


class KnowledgeBase:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.embeddings = get_embeddings(settings)
        self._store: FAISS | None = None

    @property
    def store(self) -> FAISS:
        if self._store is None:
            self._store = self._load_or_build()
        return self._store

    def _index_path(self) -> Path:
        return self.settings.index_dir / self.settings.llm_provider

    def _load_or_build(self) -> FAISS:
        path = self._index_path()
        if (path / "index.faiss").exists():
            return FAISS.load_local(str(path), self.embeddings, allow_dangerous_deserialization=True)
        return self.rebuild()

    def rebuild(self) -> FAISS:
        docs = load_documents(self.settings.knowledge_dir)
        if not docs:
            raise ValueError(f"No markdown documents found in {self.settings.knowledge_dir}")
        self._store = FAISS.from_documents(docs, self.embeddings)
        self._store.save_local(str(self._index_path()))
        return self._store

    def add_incident(self, title: str, body: str) -> Path:
        """Persist a resolved incident so future analyses can retrieve it."""
        incidents = self.settings.knowledge_dir / "incidents"
        incidents.mkdir(parents=True, exist_ok=True)
        slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")[:60]
        path = incidents / f"{slug}.md"
        text = f"# {title}\n\n{body.strip()}\n"
        path.write_text(text, encoding="utf-8")
        self.store.add_documents([Document(page_content=text, metadata={"source": str(path.relative_to(self.settings.knowledge_dir)), "title": title, "kind": "incidents"})])
        self.store.save_local(str(self._index_path()))
        return path

    def search(self, query: str, k: int | None = None) -> list[tuple[Document, float]]:
        return self.store.similarity_search_with_score(query, k=k or self.settings.retrieval_k)
