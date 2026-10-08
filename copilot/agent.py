"""LangGraph workflow: parse -> detect -> retrieve -> analyze."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from copilot.config import Settings, get_settings
from copilot.knowledge_base import KnowledgeBase
from copilot.llm import get_chat_model
from copilot.log_parser import cluster_errors, detect_anomalies, parse_logs, summarize


class CopilotState(TypedDict, total=False):
    logs: str
    question: str
    summary: dict
    clusters: list[dict]
    anomalies: list[dict]
    context: list[dict]
    report: str


SYSTEM_PROMPT = """You are a senior SRE helping a production support engineer.
Use ONLY the log findings and the retrieved runbooks/past incidents provided.
Answer in markdown with these sections:
### Summary
### Likely root cause
### Evidence (quote log signatures and counts)
### Recommended fix
### Related runbooks / incidents
If the evidence is insufficient, say so and list what to check next."""


def _section(markdown: str, name: str) -> str:
    match = re.search(rf"^##+\s*{name}\s*$\n(.*?)(?=^##+\s|\Z)", markdown, re.S | re.M | re.I)
    return match.group(1).strip() if match else ""


class IncidentCopilot:
    def __init__(self, settings: Settings | None = None, knowledge_base: KnowledgeBase | None = None, llm: Any = "auto"):
        self.settings = settings or get_settings()
        self.kb = knowledge_base or KnowledgeBase(self.settings)
        self.llm = get_chat_model(self.settings) if llm == "auto" else llm
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(CopilotState)
        graph.add_node("parse", self._parse)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("analyze", self._analyze)
        graph.set_entry_point("parse")
        graph.add_edge("parse", "retrieve")
        graph.add_edge("retrieve", "analyze")
        graph.add_edge("analyze", END)
        return graph.compile()

    def _parse(self, state: CopilotState) -> CopilotState:
        entries = parse_logs(state.get("logs", ""))
        return {
            "summary": summarize(entries),
            "clusters": [c.to_dict() for c in cluster_errors(entries)],
            "anomalies": [a.to_dict() for a in detect_anomalies(entries, self.settings.anomaly_z_threshold, self.settings.anomaly_min_errors)],
        }

    def _retrieve(self, state: CopilotState) -> CopilotState:
        top = state.get("clusters", [])[:3]
        query = " ".join(filter(None, [state.get("question", "")] + [f"{c['exception'] or ''} {c['sample']}" for c in top]))
        if not query.strip():
            return {"context": []}
        hits = self.kb.search(query)
        return {"context": [{"title": d.metadata["title"], "source": d.metadata["source"], "score": float(s), "content": d.page_content} for d, s in hits]}

    def _analyze(self, state: CopilotState) -> CopilotState:
        if self.llm is None:
            return {"report": self._offline_report(state)}
        findings = self._findings_text(state)
        context = "\n\n---\n\n".join(f"[{c['source']}]\n{c['content']}" for c in state.get("context", []))
        question = state.get("question") or "What is the most likely root cause and how do I fix it?"
        response = self.llm.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=f"Question: {question}\n\nLog findings:\n{findings}\n\nKnowledge base:\n{context}")]
        )
        return {"report": response.content}

    @staticmethod
    def _findings_text(state: CopilotState) -> str:
        lines = [f"Summary: {state.get('summary')}"]
        lines += [f"- [{c['level']}] x{c['count']} {c['logger']}: {c['signature']} (exception={c['exception']}, {c['first_seen']} -> {c['last_seen']})" for c in state.get("clusters", [])[:10]]
        lines += [f"- ANOMALY {a['minute']}: {a['reason']}" for a in state.get("anomalies", [])]
        return "\n".join(lines)

    def _offline_report(self, state: CopilotState) -> str:
        clusters, anomalies, context = state.get("clusters", []), state.get("anomalies", []), state.get("context", [])
        if not clusters:
            return "### Summary\nNo WARN/ERROR entries found in the provided logs."
        top = clusters[0]
        best = context[0] if context else None
        lines = [
            "### Summary",
            f"{sum(c['count'] for c in clusters)} warning/error lines in {len(clusters)} distinct signatures. "
            f"Top issue: **{top['exception'] or top['signature']}** from `{top['logger']}` (x{top['count']}).",
            "",
            "### Likely root cause",
            (_section(best["content"], "Root cause") or "See related runbook.") if best else "No matching runbook found.",
            "",
            "### Evidence",
            *[f"- `{c['level']}` x{c['count']} `{c['logger']}`: {c['signature']}" for c in clusters[:5]],
            *[f"- Error spike at **{a['minute']}**: {a['reason']}" for a in anomalies],
            "",
            "### Recommended fix",
            (_section(best["content"], "Resolution") or "Follow the related runbook.") if best else "Escalate to the owning team.",
            "",
            "### Related runbooks / incidents",
            *[f"- {c['title']} (`{c['source']}`)" for c in context],
            "",
            "_Generated in offline mode. Set COPILOT_LLM_PROVIDER=ollama or openai for LLM-written analysis._",
        ]
        return "\n".join(lines)

    def run(self, logs: str, question: str = "") -> CopilotState:
        return self.graph.invoke({"logs": logs, "question": question})
