"""FastAPI service for the incident copilot."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from copilot import __version__
from copilot.agent import IncidentCopilot
from copilot.log_parser import cluster_errors, detect_anomalies, parse_logs, summarize

app = FastAPI(title="AI Incident & Log Analysis Copilot", version=__version__)
_sessions: dict[str, str] = {}
_copilot: IncidentCopilot | None = None


def get_copilot() -> IncidentCopilot:
    global _copilot
    if _copilot is None:
        _copilot = IncidentCopilot()
    return _copilot


class AskRequest(BaseModel):
    question: str = ""
    session_id: str | None = None
    logs: str | None = None


class IncidentIn(BaseModel):
    title: str
    body: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": get_copilot().settings.llm_provider}


@app.post("/logs/upload")
async def upload_logs(file: UploadFile = File(...)) -> dict:
    text = (await file.read()).decode("utf-8", errors="replace")
    entries = parse_logs(text)
    if not entries:
        raise HTTPException(status_code=422, detail="No recognizable log lines found")
    session_id = uuid.uuid4().hex
    _sessions[session_id] = text
    settings = get_copilot().settings
    return {
        "session_id": session_id,
        "filename": file.filename,
        "summary": summarize(entries),
        "clusters": [c.to_dict() for c in cluster_errors(entries)][:20],
        "anomalies": [a.to_dict() for a in detect_anomalies(entries, settings.anomaly_z_threshold, settings.anomaly_min_errors)],
    }


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    logs = req.logs if req.logs is not None else _sessions.get(req.session_id or "")
    if logs is None:
        raise HTTPException(status_code=404, detail="Provide `logs` or a valid `session_id` from /logs/upload")
    result = get_copilot().run(logs, req.question)
    return {
        "report": result["report"],
        "anomalies": result.get("anomalies", []),
        "top_clusters": result.get("clusters", [])[:5],
        "sources": [{"title": c["title"], "source": c["source"], "score": c["score"]} for c in result.get("context", [])],
    }


@app.get("/knowledge/search")
def search_knowledge(q: str, k: int = 4) -> list[dict]:
    return [{"title": d.metadata["title"], "source": d.metadata["source"], "score": float(s)} for d, s in get_copilot().kb.search(q, k)]


@app.post("/knowledge/incidents", status_code=201)
def add_incident(incident: IncidentIn) -> dict:
    path = get_copilot().kb.add_incident(incident.title, incident.body)
    return {"saved": path.name}
