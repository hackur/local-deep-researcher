# Stack Analysis — Local Deep Researcher + DeepAgent UI Integration

> **Date:** March 23, 2026  
> **Purpose:** Understand the current LangGraph/LangSmith/Studio stack, how it works with local models, and create a path forward for your DeepAgent UI vision.

---

## 🎯 Executive Summary

**What you have:**
- A working **LangGraph-based research agent** (iterative web search → summarize → reflect loop)
- **LMStudio integration** with 30+ local models (crow, gpt-oss, qwen, glm, deepseek, etc.)
- **Auto-load script** (`run.sh` + `lms_helper.py`) that manages model loading/unloading via LMStudio REST API
- **Tool calling support** for structured output (required for most local models)
- **DuckDuckGo search** (free, no API key) + optional Tavily/Perplexity/SearXNG
- **LangGraph CLI dev server** (`langgraph dev`) that exposes a REST API + opens **LangSmith Studio** web UI in your browser

**What the stack does:**
- `langgraph dev` → starts a local Agent Server at `http://localhost:2024`
- Browser opens → `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`
- **Studio is a browser-based UI** hosted by LangChain that connects to your local server
- It visualizes your graph, lets you configure models/settings, run tasks, see step-by-step execution, and inspect state

**Where you are:**
- ✅ Phase 0 complete: working single-model deep research agent
- ✅ LMStudio model management working (list, check, load, unload)
- ✅ Tool calling enabled for all local models
- 📝 PLAN.md written: full multi-agent platform architecture (Phase 1-7)
- ❌ Not yet started: team system, preset system, model registry
- 🔄 Git staging: `.env`, `run.sh`, `utils.py`, `test_models.py` changes ready to commit

---

## 🧱 Current Stack Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   YOU (via browser or API)                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│         LangSmith Studio Web UI (smith.langchain.com)           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ • Graph visualization                                     │  │
│  │ • Configuration UI (model picker, search settings, etc.)  │  │
│  │ • Thread management (conversation history)                │  │
│  │ • Run execution (click "Run", see step-by-step results)   │  │
│  │ • State inspection (view graph state at each node)        │  │
│  │ • Traces & debugging (LangSmith observability)            │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ WebSocket / HTTP
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│           LangGraph Agent Server (localhost:2024)               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ langgraph dev (CLI command)                               │  │
│  │  • Serves the graph as REST API                           │  │
│  │  • Exposes /docs (FastAPI Swagger UI)                     │  │
│  │  • Watches for code changes, auto-reloads                 │  │
│  │  • Provides streaming, checkpoints, persistence           │  │
│  │  • Reads langgraph.json for config                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Your Graph (src/ollama_deep_researcher/graph.py)          │  │
│  │  Nodes:                                                    │  │
│  │   1. generate_query (LLM → search query)                  │  │
│  │   2. web_research (DuckDuckGo/Tavily/etc → sources)       │  │
│  │   3. summarize_sources (LLM → running summary)            │  │
│  │   4. reflect_on_summary (LLM → follow-up query)           │  │
│  │   5. [loop back to web_research N times]                  │  │
│  │   6. finalize_summary (dedupe sources, format output)     │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ OpenAI-compatible API (POST /v1/chat/completions)
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│           LMStudio (localhost:1234/v1)                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Loaded models: [crow-9b, gpt-oss-20b, ...]               │  │
│  │ REST API:                                                  │  │
│  │  • GET  /api/v1/models (list installed)                   │  │
│  │  • GET  /api/v0/models (check load state)                 │  │
│  │  • POST /api/v1/models/load                               │  │
│  │  • POST /api/v1/models/unload                             │  │
│  │  • POST /v1/chat/completions (inference)                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🌐 LangSmith Studio — What It Is & How It Works

### What Studio IS:
- **A hosted web UI** at `smith.langchain.com/studio` (runs in your browser)
- Connects to a **local or deployed Agent Server** via `?baseUrl=http://127.0.0.1:2024`
- **Visual graph builder + test runner** — you can design, configure, and run agents through a UI
- **Observability dashboard** — traces, state inspection, debugging
- **Thread/assistant management** — persistent conversations, memory stores
- Built by LangChain, maintained centrally, auto-updates

### What Studio is NOT:
- NOT a desktop app (it's browser-based, always loads from `smith.langchain.com`)
- NOT self-hostable (the UI itself is proprietary SaaS; only the Agent Server runs locally)
- NOT required (you can call the LangGraph API directly, build your own UI, or use the Swagger docs at `/docs`)

### How your local server connects:
```bash
$ langgraph dev --port 2024
> Ready!
> - API: http://localhost:2024
> - Docs: http://localhost:2024/docs
> - LangGraph Studio Web UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

When you open that URL:
1. Browser loads the Studio UI from LangChain's CDN
2. Studio connects back to `http://127.0.0.1:2024` via WebSocket/HTTP
3. All graph execution happens on YOUR machine (local server + local models)
4. Optionally: traces can be sent to LangSmith cloud for observability (set `LANGSMITH_TRACING=true`)
5. **Your data stays local** if `LANGSMITH_TRACING=false` (default in your `.env`)

---

## 🔍 How the Research Graph Works (Current Implementation)

**User Input:** `"Research quantum computing error correction"`

### Graph Execution Flow:

```
START
  ↓
┌────────────────────────────────────────────────────────────┐
│ 1. generate_query                                          │
│    • LLM: crow-9b (or configured model)                    │
│    • Prompt: query_writer_instructions + research_topic    │
│    • Tool calling: Query(query, rationale)                 │
│    • Output: "quantum computing error correction methods"  │
└────────────────────────────────────────────────────────────┘
  ↓
┌────────────────────────────────────────────────────────────┐
│ 2. web_research                                            │
│    • Search API: DuckDuckGo (or tavily/perplexity/searxng) │
│    • Max results: 3                                        │
│    • Fetch full page: true                                 │
│    • Deduplicate by URL                                    │
│    • Truncate each source to ~1000 tokens                  │
│    • State updates:                                        │
│      - sources_gathered (append formatted source list)     │
│      - web_research_results (append full content)          │
│      - research_loop_count += 1                            │
└────────────────────────────────────────────────────────────┘
  ↓
┌────────────────────────────────────────────────────────────┐
│ 3. summarize_sources                                       │
│    • LLM: crow-9b                                          │
│    • Prompt: summarizer_instructions                       │
│    • Input: existing_summary + newest web_research_results │
│    • Mode: create new OR update existing                   │
│    • Output: running_summary (cumulative)                  │
└────────────────────────────────────────────────────────────┘
  ↓
┌────────────────────────────────────────────────────────────┐
│ 4. reflect_on_summary                                      │
│    • LLM: crow-9b                                          │
│    • Prompt: reflection_instructions                       │
│    • Input: running_summary                                │
│    • Tool calling: FollowUpQuery(knowledge_gap, follow_up) │
│    • Output: new search_query for next loop                │
└────────────────────────────────────────────────────────────┘
  ↓
┌────────────────────────────────────────────────────────────┐
│ 5. route_research (conditional edge)                       │
│    • if research_loop_count <= max_loops (default: 3)      │
│      → go back to web_research                             │
│    • else                                                  │
│      → finalize_summary                                    │
└────────────────────────────────────────────────────────────┘
  ↓ (after N loops)
┌────────────────────────────────────────────────────────────┐
│ 6. finalize_summary                                        │
│    • Deduplicate all sources_gathered                      │
│    • Format as markdown:                                   │
│      ## Summary                                            │
│      {running_summary}                                     │
│                                                             │
│      ### Sources:                                          │
│      * Title : URL                                         │
│      * ...                                                 │
└────────────────────────────────────────────────────────────┘
  ↓
END
```

**State Schema (SummaryState):**
```python
@dataclass
class SummaryState:
    research_topic: str              # User's original topic
    search_query: str                # Current search query
    web_research_results: list       # Accumulated search results (full text)
    sources_gathered: list           # Accumulated source citations
    research_loop_count: int         # How many loops completed
    running_summary: str             # Cumulative summary (grows each loop)
```

---

## 📊 Configuration System (Current)

### Priority Order (highest to lowest):
1. **Environment variables** (`.env` file)
2. **Studio UI configurable fields** (set in the LangSmith Studio Configuration tab)
3. **Default values** (`Configuration` class in `configuration.py`)

### `.env` File (Current Settings):
```bash
# Search API
SEARCH_API=duckduckgo

# LLM Provider
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LOCAL_LLM=crow-9b-opus-4.6-distill-heretic_qwen3.5

# Research Settings
MAX_WEB_RESEARCH_LOOPS=3
FETCH_FULL_PAGE=True

# Structured Output Mode
USE_TOOL_CALLING=True  # ← CRITICAL: local models REQUIRE this (json_object not supported)
```

### Configuration Class Schema:
```python
class Configuration(BaseModel):
    max_web_research_loops: int = 3
    local_llm: str = "llama3.2"
    llm_provider: Literal["ollama", "lmstudio"] = "ollama"
    search_api: Literal["perplexity", "tavily", "duckduckgo", "searxng"] = "duckduckgo"
    fetch_full_page: bool = True
    ollama_base_url: str = "http://localhost:11434/"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    strip_thinking_tokens: bool = True
    use_tool_calling: bool = False  # ← should be True for LMStudio
```

**Configuration in Studio UI:**
When you open Studio, there's a **Configuration** tab where you can:
- Select model from dropdown
- Set research depth (max loops)
- Choose search API
- Toggle full page fetching
- All these override `.env` values for that run only

---

## 🛠️ Your Model Management System

### `run.sh` — The Launcher Script

**Features:**
- Model alias system (e.g. `./run.sh crow` → loads `crow-9b-opus-4.6-distill-heretic_qwen3.5`)
- Auto-load check: if model not loaded, calls LMStudio API to load it
- List installed models: `./run.sh list`
- Exports `LOCAL_LLM` env var before starting `langgraph dev`

**Aliases Defined:**
| Alias | Model ID | Size | Use Case |
|---|---|---|---|
| crow | crow-9b-opus-4.6-distill-heretic_qwen3.5 | 6.3GB | Reasoning, research |
| gpt | openai/gpt-oss-20b | 12.1GB | General quality |
| nemotron | nvidia/nemotron-3-nano-4b | 2.8GB | Fast, tiny |
| qwen9b | qwen/qwen3.5-9b | 10.4GB | Balanced |
| glm46 | zai-org/glm-4.6v-flash | 7.1GB | Vision |
| deepseek | deepseek/deepseek-r1-0528-qwen3-8b | 4.6GB | Reasoning |
| qwen3coder | qwen3-coder-30b-a3b-instruct | 18.6GB | Coding |
| ... | _(total 17 aliases)_ | ... | ... |

**Usage Examples:**
```bash
# Use default model from .env
./run.sh

# Use a specific model by alias
./run.sh crow

# Use exact model ID
./run.sh "nvidia/nemotron-3-nano-4b"

# List all installed models + load state
./run.sh list

# Start on custom port
PORT=8080 ./run.sh
```

### `lms_helper.py` — LMStudio API Wrapper

**Commands:**
```bash
# Check if LMStudio is running
python lms_helper.py check

# List all installed models with load state
python lms_helper.py list

# Check if a specific model is loaded
python lms_helper.py is-loaded "crow-9b-opus-4.6-distill-heretic_qwen3.5"

# Load a model (blocks until ready, ~8-15 seconds)
python lms_helper.py load "crow-9b-opus-4.6-distill-heretic_qwen3.5"

# Unload a model (frees RAM)
python lms_helper.py unload "crow-9b-opus-4.6-distill-heretic_qwen3.5"
```

**API Endpoints Used:**
- `GET /api/v1/models` — list installed models
- `GET /api/v0/models` — check load state (loaded vs available)
- `POST /api/v1/models/load` — load model into RAM
- `POST /api/v1/models/unload` — unload from RAM
- `POST /v1/chat/completions` — inference (OpenAI-compatible)

---

## 🔬 Tool Calling vs JSON Mode (Critical for Local Models)

### The Problem:
LangGraph needs **structured output** from LLMs for steps like:
- Generating search queries (`Query(query="...", rationale="...")`)
- Reflection (`FollowUpQuery(knowledge_gap="...", follow_up_query="...")`)

Two approaches:
1. **JSON Mode** (`format="json"`) — LLM outputs raw JSON, you parse it
2. **Tool Calling** — LLM calls a tool, framework extracts structured args

### What Your Local Models Support:
- ✅ **Tool calling** (`json_schema` response format) — **ALL your models support this**
- ❌ **JSON object mode** (`response_format={"type": "json_object"}`) — **NOT supported by LMStudio**

### Your Current Implementation:
```python
# configuration.py
use_tool_calling: bool = Field(default=False, ...)  # ← should be True

# .env
USE_TOOL_CALLING=True  # ← you've correctly set this

# graph.py
if configurable.use_tool_calling:
    llm = get_llm(configurable).bind_tools([Query])
    result = llm.invoke(messages)
    return {"search_query": result.tool_calls[0]["args"]["query"]}
else:
    llm = get_llm(configurable)  # format="json"
    result = llm.invoke(messages)
    parsed = json.loads(result.content)
    return {"search_query": parsed["query"]}
```

**Recommendation:** Set `use_tool_calling: bool = Field(default=True, ...)` in `Configuration` class so it's the default.

---

## 🧪 Test Suite (`test_models.py`)

**What it does:**
- Tests all configured models end-to-end
- Runs a short research loop with each model
- Validates structured output (tool calling)
- Reports success/failure + timing

**Usage:**
```bash
# Test all models
python test_models.py

# Test a specific model
python test_models.py crow

# Quick import check only (no inference)
python test_models.py --quick
```

---

## 🎨 Your Vision: Multi-Agent "DeepAgent UI"

From your PLAN.md, you want:

### Phase 1-7 Roadmap:
1. **Foundation** — Model registry, team loader, preset system
2. **Deep Research Team** — Supervisor → Researcher → Synthesizer (multi-model)
3. **Planning/Report Team** — Plan-and-Execute pattern
4. **Coding Agent** — Swarm pattern with OpenClaw integration
5. **Media Classifier** — Vision models, batch processing
6. **Transcript Analyzer** — Audio/video analysis pipeline
7. **Studio Integration** — All teams visible in LangGraph Studio UI

### Key Architecture Concepts:

#### Teams:
```yaml
# config/teams/deep-research.yaml
name: deep-research
pattern: supervisor
agents:
  supervisor:
    role: "supervisor"
    model: nemotron
    temperature: 0.3
    context_length: 8192
  researcher:
    role: "researcher"
    model: crow
    tools: [web_search, fetch_page]
  synthesizer:
    role: "synthesizer"
    model: gpt
```

#### Presets:
```yaml
# config/presets/nemotron-fast.yaml
name: nemotron-fast
base_team: deep-research
overrides:
  agents:
    supervisor:
      model: nemotron
    researcher:
      model: crow
    synthesizer:
      model: qwen3-4b
  search:
    max_loops: 1
```

#### Model Registry:
```yaml
# config/models.yaml
models:
  crow:
    provider: lmstudio
    id: "crow-9b-opus-4.6-distill-heretic_qwen3.5"
    size_gb: 6.3
    capabilities: [tool_use, reasoning]
    tags: [fast, reasoning, local]
  
  claude-sonnet:
    provider: anthropic
    id: "claude-sonnet-4-6"
    capabilities: [tool_use, vision, reasoning]
    tags: [api, powerful]
  
  codex-agent:
    provider: openclaw
    agent_id: "codex-agent"
    capabilities: [coding, git, file-ops]
```

---

## 📈 Modern Day Usage (March 2026)

### LangGraph Ecosystem Status:

**LangGraph Core:**
- ✅ Stable, v0.6.11 (latest as of your `uv.lock`)
- ✅ Production-ready for agent orchestration
- ✅ Used by major companies (Stripe, Shopify, etc.)
- ✅ Multi-agent patterns well-documented

**LangSmith Studio:**
- ✅ Actively maintained, constantly improving
- ✅ Best tool for visualizing/debugging LangGraph agents
- ⚠️ Safari compatibility issues (use Firefox or `--tunnel`)
- ⚠️ UI is SaaS-hosted, can't self-host
- ✅ Works fully offline if `LANGSMITH_TRACING=false`

**Multi-Agent Libraries:**
- ✅ `langgraph-supervisor` — hierarchical pattern (stable)
- ✅ `langgraph-swarm` — peer handoff pattern (stable)
- ✅ `create_react_agent` — built-in, well-tested
- 📦 Plan-and-Execute — examples available, build from template

**Local Model Support:**
- ✅ LMStudio + Ollama both mature
- ✅ Tool calling works reliably (as of 2025+)
- ⚠️ JSON mode inconsistent (stick to tool calling)
- ✅ 9B-20B models competitive with GPT-3.5 for tasks like research

### Community Best Practices (2026):

1. **Always use tool calling** for structured output with local models
2. **Hybrid approach** — local for bulk work, API for critical reasoning
3. **Supervisor pattern** most reliable for multi-agent (vs pure swarm)
4. **Preset system** (like your PLAN.md) is the right abstraction
5. **LangSmith tracing** extremely valuable for debugging (even locally)

---

## 🚀 Recommended Next Steps

### Option A: Start Building the Team System (PLAN.md Phase 1)

**Week 1 Goal:** Get `./run.sh --team deep-research --preset nemotron-fast` working

**Tasks:**
1. Create `config/models.yaml` with your 17 LMStudio models + API models
2. Create `src/agents/model_factory.py` — `get_model(alias) -> ChatModel`
3. Create `config/teams/deep-research.yaml` — team definition
4. Create `config/presets/` — 3 presets (fast, balanced, quality)
5. Update `run.sh` — add `--team`, `--preset`, `teams`, `presets` commands
6. Update `lms_helper.py` — add confirmation prompt before loading models

**Deliverable:** Multi-model research team running through Studio UI

---

### Option B: Build a Custom UI (Alternative to Studio)

If you want full control over the UI instead of using LangSmith Studio:

**Stack:**
- FastAPI backend (already there from `langgraph dev`)
- React/Next.js frontend (or HTMX for simplicity)
- WebSocket for streaming
- SQLite for thread/message persistence

**What you'd build:**
```
/ui
  /dashboard       — team selector, preset picker
  /run/{run_id}    — live execution view
  /threads         — conversation history
  /models          — LMStudio model management
  /config          — team/preset editor
```

**Pros:**
- Full customization, self-hosted
- Tailored for your multi-model workflow
- Can integrate OpenClaw directly
- Better model loading UX (confirmation, RAM tracking)

**Cons:**
- More work than using Studio
- Need to build observability features yourself
- No auto-updates from LangChain

---

### Option C: Hybrid Approach (Recommended)

**Use Studio for development, build custom UI for production:**

1. **Phase 1-5** — build teams/presets, test in Studio
2. **Phase 6** — evaluate Studio limitations
3. **Phase 7** — if needed, build custom UI that talks to same Agent Server API

**Why this works:**
- Studio is excellent for graph design + debugging
- Your multi-agent system doesn't depend on Studio
- `langgraph dev` API is standard — any UI can consume it
- Custom UI only needed if Studio doesn't fit your workflow

---

## 🔍 Where You Are Right Now

### ✅ Working:
- LangGraph deep research agent (single model, iterative loop)
- LMStudio model management (17 models, auto-load)
- Tool calling for structured output
- DuckDuckGo search (no API key needed)
- Studio UI connection (browser-based visual debugging)

### 📝 Staged (ready to commit):
- `.env` — `USE_TOOL_CALLING=True`, model config
- `run.sh` — expanded aliases, better model display
- `utils.py` — improved error handling
- `test_models.py` — end-to-end test suite

### 📋 Planned (PLAN.md):
- Model registry system (YAML-based)
- Team definitions (supervisor, swarm, pipeline patterns)
- Preset system (swap models without changing team structure)
- Multi-agent orchestration (researcher + synthesizer + coder)
- OpenClaw integration (coding team delegates to codex-agent)
- Progress tracking (cron-based monitoring)

### 🎯 Next Immediate Action:

**I recommend:**

1. **Commit your current changes** (staged files)
2. **Add PLAN.md to git** (version control your architecture)
3. **Test the current graph in Studio** to verify it works end-to-end
4. **Decide: Studio-first or custom UI?**
   - If Studio-first → start Phase 1 (model registry + team loader)
   - If custom UI → prototype a simple dashboard first

**What's your preference?** I can help you:
- Complete Phase 1 implementation (team system)
- Build a custom UI proof-of-concept
- Just commit what you have and test the existing graph in Studio

Let me know which direction you want to go!
