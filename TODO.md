# TODO — Local Deep Researcher

> Status as of March 23, 2026
> Server: ✅ Running, verified end-to-end
> Model: crow-9b via LMStudio (localhost:1234)
> API: langgraph-api 0.7.85, langgraph 1.1.3
> Privacy: All LangSmith/tracing disabled

---

## ✅ DONE

- [x] Upgraded `langgraph-api` from 0.5.42 (EOL) → **0.7.85** (latest)
- [x] Upgraded `langgraph` to **1.1.3**
- [x] Disabled ALL remote telemetry in `.env`:
  - `LANGSMITH_TRACING=false`
  - `LANGCHAIN_TRACING_V2=false`
  - `LANGCHAIN_CALLBACKS_DISABLED=true`
  - `LANGCHAIN_ENDPOINT=""`
  - `LANGCHAIN_API_KEY=""`
  - `LANGSMITH_API_KEY=""`
  - `DO_NOT_TRACK=1`
- [x] Verified server `/info` reports `"langsmith": false`
- [x] Verified full end-to-end run: topic → search → summarize → reflect → 4 loops → final report
- [x] All LLM calls go to `localhost:1234` (LMStudio)
- [x] All search goes to DuckDuckGo (no API key)
- [x] Created `STACK_ANALYSIS.md`, `QUICKSTART.md`

---

## 📋 TASK LIST — Phase 1: Multi-Model Teams

### 1A. Model Registry (`config/models.yaml`)
- [ ] Create `config/` directory
- [ ] Write `models.yaml` with all 30 LMStudio models from `lms_helper.py list`
- [ ] Include provider definitions (lmstudio, ollama)
- [ ] Add size_gb, capabilities, tags for each model
- [ ] Validate YAML loads cleanly

### 1B. Model Factory (`src/agents/model_factory.py`)
- [ ] Create `src/agents/` package with `__init__.py`
- [ ] Implement `get_model(alias, config) -> BaseChatModel`
- [ ] Support providers: lmstudio (ChatLMStudio), ollama (ChatOllama)
- [ ] Load registry from `config/models.yaml`
- [ ] Handle temperature, context_length overrides
- [ ] Test: `get_model("crow")` returns working ChatLMStudio

### 1C. Team Definitions
- [ ] Create `config/teams/` directory
- [ ] Write `deep-research.yaml` — supervisor + researcher + synthesizer
- [ ] Write team loader: `src/agents/team_loader.py`
- [ ] Validate team YAML references valid model aliases

### 1D. Preset System
- [ ] Create `config/presets/` directory
- [ ] Write `nemotron-fast.yaml` (all small local models, 1 loop)
- [ ] Write `crow-balanced.yaml` (current default, 3 loops)
- [ ] Preset loader merges overrides onto team defaults

### 1E. CLI Integration
- [ ] Add `./run.sh teams` — list available teams
- [ ] Add `./run.sh presets <team>` — list presets for a team
- [ ] Add `./run.sh --team deep-research` — run a team
- [ ] Add `./run.sh --team deep-research --preset nemotron-fast` — run with preset
- [ ] Model load confirmation prompt (show what needs loading + RAM cost)

### 1F. Multi-Agent Graph (Deep Research Team)
- [ ] Install `langgraph-supervisor` package
- [ ] Create `src/agents/teams/deep_research/graph.py`
- [ ] Supervisor node: breaks topic into sub-queries, routes to workers
- [ ] Researcher node: `create_react_agent` with web_search tools
- [ ] Synthesizer node: takes all research, writes final report
- [ ] Register as new graph in `langgraph.json`
- [ ] Test: 3 different models handling 3 different roles

### 1G. Local Observability (Replace LangSmith)
- [ ] Research options: OpenTelemetry + Jaeger, LangFuse (self-hosted), plain file logging
- [ ] Pick one and integrate
- [ ] Log: model used per node, token count, latency, input/output
- [ ] View in local dashboard (Jaeger UI or similar)

---

## 📋 TASK LIST — Phase 2: Polish & Test

- [ ] Test all 30 models with `test_models.py`
- [ ] Document which models work best for which roles
- [ ] Add `--pick` interactive model selector
- [ ] Write integration tests for team system
- [ ] Update `QUICKSTART.md` with team/preset usage

---

## 📋 FUTURE — Phase 3+

- [ ] Planning/Report team (Plan-and-Execute pattern)
- [ ] Coding Agent team (Swarm pattern + OpenClaw bridge)
- [ ] Media Classifier team (GLM vision models)
- [ ] Transcript Analyzer team (pipeline pattern)
- [ ] Custom web UI (if Studio limitations become blocking)
- [ ] Progress monitoring cron (pick from PROGRESS_APPROACHES.md)

---

## 🔧 How to Run (Right Now)

```bash
cd /Volumes/JS-DEV/local-deep-researcher

# Make sure LMStudio is running at localhost:1234

# Load a model and start server
./run.sh crow

# Or start manually:
.venv/bin/python lms_helper.py load "crow-9b-opus-4.6-distill-heretic_qwen3.5"
.venv/bin/langgraph dev --port 2024

# Open Studio UI (use Firefox/Chrome, NOT Safari):
# https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024

# Or call API directly:
curl -X POST http://127.0.0.1:2024/threads -H "Content-Type: application/json" -d '{}'
# Then POST to /threads/{id}/runs with your research topic
```

## ⚠️ Important Notes

- **Studio UI** is hosted at smith.langchain.com but ONLY serves static JS/CSS
- All actual data flows between your browser ↔ localhost:2024 ↔ localhost:1234
- With `LANGSMITH_TRACING=false`, zero data is sent to LangChain servers
- The Studio UI is just a convenience — you can use the API directly or build your own UI
- Safari won't work (blocks localhost mixed content) — use Firefox or Chrome
