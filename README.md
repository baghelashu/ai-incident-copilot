# AI Incident & Log Analysis Copilot

A GenAI copilot for production support. Upload Spring Boot / Linux logs, and it groups the errors,
flags error spikes, looks up the matching runbooks and past incidents (RAG over FAISS), and gives you
a likely root cause and fix. You can also ask questions in plain English, like *"why did orders fail last night?"*

**Tech:** Python, LangChain, LangGraph, FAISS, FastAPI, Streamlit, Ollama / OpenAI

```
logs ──► parse & cluster ──► anomaly detection ──► retrieve runbooks/incidents (FAISS) ──► LLM analysis ──► report
          (log_parser)        (z-score per minute)      (knowledge_base)                       (agent)
```

## Features
- **Log parsing** for Spring Boot, syslog and generic `timestamp LEVEL logger: msg` formats, with multi-line stack traces.
- **Error clustering**: masks IDs, numbers, IPs and UUIDs so the same error groups under one signature.
- **Anomaly detection**: flags minutes where the error rate is far above the baseline (z-score).
- **RAG knowledge base**: runbooks and past incident reports in `data/` indexed in FAISS; resolved incidents can be added through the API.
- **LangGraph agent**: `parse → retrieve → analyze` workflow that produces Summary / Root cause / Evidence / Fix / Sources.
- **Runs offline by default.** No API key needed; switch to Ollama (local) or OpenAI with one env variable.
- **FastAPI service** + **Streamlit UI**.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# API
uvicorn copilot.api:app --reload
# UI
streamlit run ui/streamlit_app.py
```

Try it with the sample logs:
```bash
curl -F "file=@samples/order-service.log" localhost:8000/logs/upload
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
     -d '{"session_id": "<id from upload>", "question": "Why are orders failing?"}'
```

### Using a real LLM
Copy `.env.example` to `.env` and set:
- Local: `COPILOT_LLM_PROVIDER=ollama` (run `ollama pull llama3.1 && ollama pull nomic-embed-text`)
- Cloud: `COPILOT_LLM_PROVIDER=openai` and `OPENAI_API_KEY=...`

## Running on Windows
Use PowerShell with Python 3.10+ installed from python.org (tick "Add python.exe to PATH" during install).

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# API (terminal 1)
uvicorn copilot.api:app --reload
# UI (terminal 2, run .venv\Scripts\activate first)
streamlit run ui/streamlit_app.py
```
If activation is blocked with "running scripts is disabled", run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Try the API with the sample logs. Use `curl.exe`, not `curl` (in PowerShell `curl` is an alias for `Invoke-WebRequest`):
```powershell
$up = curl.exe -s -F "file=@samples/order-service.log" http://localhost:8000/logs/upload | ConvertFrom-Json
$body = @{ session_id = $up.session_id; question = "Why are orders failing?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ask -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 10
```
Or open http://localhost:8000/docs in a browser to try every endpoint.

Use a real LLM: `copy .env.example .env`, then edit `COPILOT_LLM_PROVIDER` in `.env`. For Ollama, install it from ollama.com and run `ollama pull llama3.1` and `ollama pull nomic-embed-text`.

Run the tests: `pytest`

## API
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Status and active provider |
| POST | `/logs/upload` | Upload a log file → summary, error clusters, anomalies, `session_id` |
| POST | `/ask` | `{session_id or logs, question}` → root-cause report with sources |
| GET | `/knowledge/search?q=` | Semantic search over runbooks/incidents |
| POST | `/knowledge/incidents` | Save a resolved incident to the knowledge base |

## Project layout
```
copilot/
  log_parser.py      parsing, clustering, anomaly detection
  knowledge_base.py  FAISS index over data/runbooks and data/incidents
  agent.py           LangGraph workflow + prompts
  llm.py             Ollama / OpenAI / offline model factories
  api.py             FastAPI app
ui/streamlit_app.py  Streamlit UI
data/                runbooks and past incidents (markdown)
samples/             example Spring Boot and syslog logs
tests/               pytest suite
```

## Tests
```bash
pytest
```
