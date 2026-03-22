# Multi-Agent Teams Platform — Architecture & Implementation Plan

> **Project:** Extend local-deep-researcher into a full multi-agent platform with preset team configurations, heterogeneous model support, and pluggable pipelines for research, coding, media, and more.
> **Author:** Donna (OpenClaw main agent) — March 22, 2026
> **Codebase:** `/Volumes/JS-DEV/local-deep-researcher`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State & What We Have](#2-current-state--what-we-have)
3. [Core Architecture: Agent Teams](#3-core-architecture-agent-teams)
4. [Model Registry & Provider Abstraction](#4-model-registry--provider-abstraction)
5. [Preset System Design](#5-preset-system-design)
6. [Team Patterns (Agentic Architecture Reference)](#6-team-patterns-agentic-architecture-reference)
7. [Team Blueprints for Your Use Cases](#7-team-blueprints-for-your-use-cases)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [File & Folder Structure](#9-file--folder-structure)
10. [Technology Stack & Dependencies](#10-technology-stack--dependencies)
11. [Open Questions & Design Decisions](#11-open-questions--design-decisions)

---

## 1. Executive Summary

The goal is to turn this codebase into a **team-based multi-agent platform** where:

- **Presets** define named configurations: which models fill which roles, system prompts, context lengths, search settings, temperature, etc.
- **Teams** are groups of agents with specific roles (supervisor, researcher, coder, classifier, reporter…) wired together into a LangGraph graph.
- **Any model source** works: LMStudio local models, Ollama, OpenAI/Anthropic API, Claude via OpenClaw ACP sessions, or even sub-processes (codex, claude CLI).
- **Named pipelines** map to specific tasks: deep research, media classification, coding agent orchestration, planning/reporting, etc.
- You choose a preset at launch (`./run.sh --team deep-research --preset nemotron-fast`) and the system handles model loading, context setup, and graph wiring automatically.

**No auto-loading of large models.** The preset system will always show what will be loaded and ask for confirmation (or skip if already loaded), so you stay in control of RAM.

---

## 2. Current State & What We Have

### Already built:
- **`local-deep-researcher`** — a LangGraph graph with nodes: `generate_query → web_research → summarize_sources → reflect_on_summary → finalize_summary`
- **LMStudio integration** (`ChatLMStudio`) — OpenAI-compatible API wrapper
- **`lms_helper.py`** — Python CLI for LMStudio v1 REST API (list, check, load, unload)
- **`run.sh`** — launcher with model aliases, auto-load support, LangGraph dev server
- **`test_models.py`** — end-to-end test runner for all configured models
- **`.env` config** — standard env-based configuration picked up by `Configuration.from_runnable_config()`

### What the current graph does:
```
User topic
  → generate_query (LLM, tool calling)
  → web_research (DuckDuckGo / Tavily / Perplexity / SearXNG)
  → summarize_sources (LLM)
  → reflect_on_summary (LLM, tool calling) 
  → [loop or finalize]
  → finalize_summary
  → Final markdown report with sources
```

### Key constraint confirmed:
LMStudio models support tool calling and `json_schema` but NOT `json_object` mode. `USE_TOOL_CALLING=True` is the correct setting for all local models.

---

## 3. Core Architecture: Agent Teams

### 3.1 The Team Concept

A **Team** is a named configuration that specifies:

```yaml
# teams/deep-research.yaml
name: deep-research
description: "Multi-model deep research with planner, researcher, and synthesizer roles"
pattern: supervisor          # supervisor | swarm | pipeline | solo
agents:
  supervisor:
    role: "supervisor"
    model: nemotron           # model alias from models.yaml
    system_prompt: |
      You are a research director. Break down the user's question into
      sub-tasks and delegate to your researcher and synthesizer agents.
    temperature: 0.3
    context_length: 8192
  researcher:
    role: "researcher"  
    model: crow
    system_prompt: |
      You are a meticulous web researcher. Search for accurate, current information.
      Always cite your sources. Focus on facts, not speculation.
    temperature: 0.1
    context_length: 16384
    tools: [web_search, fetch_page]
  synthesizer:
    role: "synthesizer"
    model: gpt
    system_prompt: |
      You are a senior analyst. You receive research and produce clear,
      structured reports. Organize findings logically with citations.
    temperature: 0.4
    context_length: 8192
search:
  api: duckduckgo
  max_loops: 3
  fetch_full_page: true
output:
  format: markdown
  include_sources: true
  filename_template: "research_{topic}_{date}.md"
```

### 3.2 Model Resolution

Models are resolved at team-load time through a **Model Registry**:

```
alias → provider → model_id → loader → ChatLMStudio / ChatOpenAI / ChatAnthropic / OpenClaw
```

### 3.3 Pattern Types

| Pattern | Description | When to use |
|---|---|---|
| **Solo** | Single agent, no orchestration | Simple single-model tasks |
| **Pipeline** | Linear chain: A → B → C → output | Fixed ordered workflows (research → write → review) |
| **Supervisor** | Central LLM routes to specialized workers | Complex tasks needing dynamic routing |
| **Swarm** | Agents hand off to each other peer-to-peer | Open-ended collaboration, each agent specializes |
| **Parallel** | Multiple agents run concurrently, results merged | Batch classification, parallel research threads |

---

## 4. Model Registry & Provider Abstraction

### 4.1 `models.yaml` — Central Model Registry

```yaml
# config/models.yaml
providers:
  lmstudio:
    base_url: "http://localhost:1234/v1"
    api_key: "not-needed"
    type: openai-compat
    
  ollama:
    base_url: "http://localhost:11434"
    type: ollama
    
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    type: anthropic
    
  openai:
    api_key: "${OPENAI_API_KEY}"
    type: openai

  openclaw:
    type: openclaw-acp           # Routes via OpenClaw ACP session
    gateway_url: "http://localhost:8765"

models:
  # ── LMStudio local models (your installed set) ──────────────
  crow:
    provider: lmstudio
    id: "crow-9b-opus-4.6-distill-heretic_qwen3.5"
    display: "Crow 9B Opus Distill"
    size_gb: 6.3
    capabilities: [tool_use, reasoning]
    tool_calling: true
    recommended_context: 16384
    tags: [fast, reasoning, local]

  gpt-oss:
    provider: lmstudio
    id: "openai/gpt-oss-20b"
    display: "GPT-OSS 20B"
    size_gb: 12.1
    capabilities: [tool_use]
    tool_calling: true
    recommended_context: 8192
    tags: [capable, local]

  nemotron:
    provider: lmstudio
    id: "nvidia/nemotron-3-nano-4b"
    display: "Nemotron 3 Nano 4B"
    size_gb: 2.8
    capabilities: [tool_use]
    tool_calling: true
    recommended_context: 4096
    tags: [fast, tiny, local]

  qwen9b:
    provider: lmstudio
    id: "qwen/qwen3.5-9b"
    display: "Qwen3.5 9B Q8"
    size_gb: 10.4
    capabilities: [tool_use]
    tool_calling: true
    recommended_context: 16384
    tags: [capable, local]

  glm46:
    provider: lmstudio
    id: "zai-org/glm-4.6v-flash"
    display: "GLM-4.6v Flash"
    size_gb: 7.1
    capabilities: [tool_use, vision]
    tool_calling: true
    recommended_context: 4096
    tags: [vision, local]

  qwen3-4b:
    provider: lmstudio
    id: "qwen/qwen3-4b-2507"
    display: "Qwen3 4B"
    size_gb: 2.3
    capabilities: [tool_use]
    tool_calling: true
    recommended_context: 8192
    tags: [fast, tiny, local]

  deepseek:
    provider: lmstudio
    id: "deepseek/deepseek-r1-0528-qwen3-8b"
    display: "DeepSeek R1 Qwen3 8B"
    size_gb: 4.6
    capabilities: [tool_use, reasoning]
    tool_calling: true
    recommended_context: 8192
    tags: [reasoning, local]

  qwen3-coder:
    provider: lmstudio
    id: "qwen3-coder-30b-a3b-instruct"
    display: "Qwen3 Coder 30B"
    size_gb: 18.6
    capabilities: [tool_use, coding]
    tool_calling: true
    recommended_context: 16384
    tags: [coding, large, local]

  # ── API models ──────────────────────────────────────────────
  claude-sonnet:
    provider: anthropic
    id: "claude-sonnet-4-6"
    display: "Claude Sonnet 4.6"
    capabilities: [tool_use, vision, reasoning, coding]
    tool_calling: true
    tags: [api, powerful, coding]

  claude-opus:
    provider: anthropic
    id: "claude-opus-4-6"
    display: "Claude Opus 4.6"
    capabilities: [tool_use, vision, reasoning, coding]
    tool_calling: true
    tags: [api, most-capable, coding]

  # ── OpenClaw / ACP ──────────────────────────────────────────
  donna:
    provider: openclaw
    agent_id: "main"
    display: "Donna (Main OpenClaw Agent)"
    capabilities: [orchestration, memory, tools]
    tags: [orchestrator, openclaw]

  codex-agent:
    provider: openclaw
    agent_id: "codex-agent"
    display: "Codex GPT-5 Agent"
    capabilities: [coding, git, file-ops]
    tags: [coding, openclaw]
```

### 4.2 Model Loader Factory

```python
# src/agents/model_factory.py

def get_model(model_alias: str, config: dict = None) -> BaseChatModel:
    """
    Resolve a model alias to a LangChain-compatible chat model.
    Handles: lmstudio, ollama, openai, anthropic, openclaw-acp
    """
    registry = load_model_registry()
    model_def = registry["models"][model_alias]
    provider = registry["providers"][model_def["provider"]]
    
    overrides = config or {}
    temperature = overrides.get("temperature", 0)
    context_length = overrides.get("context_length", model_def.get("recommended_context", 4096))
    
    match provider["type"]:
        case "openai-compat":
            return ChatLMStudio(
                base_url=provider["base_url"],
                model=model_def["id"],
                temperature=temperature,
                api_key=provider.get("api_key", "not-needed"),
            )
        case "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(model=model_def["id"], temperature=temperature)
        case "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=model_def["id"], temperature=temperature)
        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model_def["id"], temperature=temperature)
        case "openclaw-acp":
            # Thin wrapper that routes calls through OpenClaw ACP sessions
            return OpenClawACPModel(agent_id=model_def["agent_id"])
```

---

## 5. Preset System Design

### 5.1 Preset vs Team vs Run

| Concept | What it is |
|---|---|
| **Model** | A single LLM (crow, gpt-oss, claude-sonnet…) |
| **Role** | What a model does in a team (supervisor, researcher, coder…) |
| **Team** | A named group of roles + their models + graph pattern |
| **Preset** | A named override: swap models/settings within a team without changing structure |
| **Run** | A single invocation of a team with a specific task |

### 5.2 Example Preset File

```yaml
# presets/nemotron-fast.yaml
name: nemotron-fast
description: "All-local fast preset using small models for quick iterations"
base_team: deep-research        # inherits team structure
overrides:
  agents:
    supervisor:
      model: nemotron           # override the supervisor model
      context_length: 4096
    researcher:
      model: crow
      context_length: 8192
    synthesizer:
      model: qwen3-4b
      context_length: 4096
  search:
    max_loops: 1                # faster = fewer loops
    fetch_full_page: false

# presets/claude-quality.yaml  
name: claude-quality
description: "API-backed high-quality research with Claude Sonnet"
base_team: deep-research
overrides:
  agents:
    supervisor:
      model: claude-sonnet
    researcher:
      model: crow              # still local for web search
    synthesizer:
      model: claude-sonnet
  search:
    max_loops: 5
    fetch_full_page: true
```

### 5.3 CLI Interface

```bash
# List teams
./run.sh teams

# List presets for a team
./run.sh presets deep-research

# Run a team with default preset
./run.sh --team deep-research

# Run a team with a specific preset
./run.sh --team deep-research --preset nemotron-fast

# Run solo (current behavior, backward compat)
./run.sh crow

# Interactive model selector (picks from loaded LMStudio models)
./run.sh --pick
```

### 5.4 Confirmation Flow (No Auto-Load)

```
$ ./run.sh --team deep-research --preset nemotron-fast

Team:   deep-research (Supervisor → Researcher → Synthesizer)
Preset: nemotron-fast

Models required:
  supervisor   → nemotron  (nvidia/nemotron-3-nano-4b, 2.8GB) ✅ loaded
  researcher   → crow      (crow-9b-opus-4.6-distill-heretic, 6.3GB) ✅ loaded
  synthesizer  → qwen3-4b  (qwen/qwen3-4b-2507, 2.3GB)        ❌ not loaded

Total new RAM: ~2.3GB

Load missing models? [y/N/skip]: y
  ⏳ Loading qwen/qwen3-4b-2507 ...
  ✅ Loaded in 8.2s

🚀 Starting server on http://localhost:2024
```

---

## 6. Team Patterns (Agentic Architecture Reference)

These are the proven patterns from LangGraph's official libraries and research:

### 6.1 Supervisor Pattern (`langgraph-supervisor`)
```
User → Supervisor LLM
         ├── calls agent_A as a tool
         ├── calls agent_B as a tool
         └── synthesizes final answer
```
- Supervisor has tool-calling enabled; each worker is a `create_react_agent`
- Best for: research + synthesis, planning + execution
- Library: `langgraph-supervisor` (pip installable)
- **Use for:** Deep Research, Planning/Reporting teams

### 6.2 Swarm Pattern (`langgraph-swarm`)
```
User → Agent_A
         └── handoff_to(Agent_B) 
               └── handoff_to(Agent_C)
                     └── handoff_to(Agent_A)  [loop until done]
```
- Peer-to-peer handoffs via tool calls; system remembers last active agent
- Best for: open-ended collaboration, each agent has a narrow specialty
- Library: `langgraph-swarm` (pip installable)
- **Use for:** Multi-step coding review + planning + commit loops

### 6.3 Pipeline Pattern (custom LangGraph)
```
Node_A → Node_B → Node_C → Node_D → Output
  (strict linear, no routing decisions)
```
- Deterministic, no LLM-based routing
- Best for: media processing (ingest → transcribe → classify → store)
- Already implemented: our existing research graph IS a pipeline

### 6.4 Parallel Map-Reduce Pattern
```
Input → [Agent_1, Agent_2, Agent_3] (parallel) → Aggregator → Output
```
- Fan-out to N agents, collect results, reduce
- Best for: batch classification, parallel research threads, image tagging
- LangGraph supports `Send()` API for dynamic fan-out

### 6.5 Plan-and-Execute Pattern
```
User → Planner (makes step list)
         → Executor (runs each step sequentially)
           → each step may call tools/agents
         → Replanner (revises if needed)
         → Final Answer
```
- Planner creates a structured plan; executor follows it step by step
- Best for: complex multi-step tasks (coding projects, research reports)
- LangGraph example: `examples/plan-and-execute/`

---

## 7. Team Blueprints for Your Use Cases

### 7.1 Team: `deep-research`
**Pattern:** Supervisor → [Researcher, Synthesizer]
**Purpose:** Deep web research on any topic, producing structured reports

```
Supervisor (nemotron / claude-sonnet)
  - Breaks question into sub-queries
  - Routes to Researcher, asks Synthesizer to write final report

Researcher (crow / qwen9b)
  - Web search via DuckDuckGo/Tavily
  - Fetches full page content
  - Returns structured source data

Synthesizer (gpt-oss / claude-sonnet)
  - Takes all research, writes markdown report
  - Includes citations, key findings, gaps
```

**Presets:**
- `nemotron-fast` — all local, tiny models, 1 search loop
- `crow-balanced` — local models, 3 search loops (current default)
- `claude-quality` — Anthropic API for supervisor + synthesizer, crow for research

---

### 7.2 Team: `planning-report`
**Pattern:** Plan-and-Execute
**Purpose:** Turn a vague goal into an actionable plan with a structured report

```
Planner (claude-sonnet / gpt-oss)
  - Receives goal: "Plan a product launch for CrispDisplay"
  - Produces structured JSON plan: [step1, step2, ..., stepN]

Executor (per-step, uses tools)
  - Runs each step: web research, note-taking, calculations
  - Can spawn Researcher sub-agent for web lookups

Report Writer (crow / claude-sonnet)
  - Takes all step results
  - Writes a final structured report / document
```

**Output:** Markdown document saved to `~/Desktop/plan_{topic}_{date}.md`

---

### 7.3 Team: `media-classifier`
**Pattern:** Pipeline + Parallel Map-Reduce
**Purpose:** Ingest images, video frames, audio transcripts → classify, tag, organize

```
Ingestor (no LLM)
  - Scans input directory
  - Routes files by type: image → ImageQueue, video → VideoQueue, audio → AudioQueue

Image Classifier (glm46 / vision model)
  - Receives batches of images
  - Returns tags: [content, scene, people, objects, mood, quality]

Video Processor (ffmpeg + frame sampler)
  - Extracts keyframes from video
  - Each keyframe → Image Classifier

Transcriber (whisper / local audio)
  - Audio files → text transcript
  
Text Classifier (crow / nemotron)
  - Transcripts → topic tags, sentiment, key entities

Organizer (no LLM)
  - Reads all classification results
  - Moves/renames/symlinks files into organized folder structure
  - Writes SQLite index: filename, tags, date, source

Reporter (crow)
  - Summarizes what was processed
  - Lists notable items, suggested albums/groups
```

**Presets:**
- `fast-tags` — glm46 for vision, nemotron for text, no full-page fetch
- `quality-classify` — glm46 vision + claude-sonnet for text
- `local-only` — all local models, offline safe

---

### 7.4 Team: `coding-agent`
**Pattern:** Swarm (Planner ↔ Coder ↔ Reviewer) + OpenClaw Integration
**Purpose:** Multi-model coding loop with progress tracking

```
Planner (claude-sonnet / gpt-oss)
  - Receives: task description + codebase context
  - Creates: implementation plan, file list, acceptance criteria
  - Hands off to: Coder

Coder (qwen3-coder / claude via OpenClaw ACP)
  - Receives plan from Planner
  - Executes: creates/edits files, runs tests
  - Reports back: what was done, what failed
  - Can hand off to Reviewer

Reviewer (crow / claude-sonnet)
  - Reviews code diff
  - Returns: approved | needs-changes + feedback
  - If needs-changes → hands back to Coder

Progress Tracker (no LLM, file-based)
  - Reads/writes: progress.json in project root
  - Tracks: plan steps, completion status, errors, session IDs
  - Can resume interrupted runs
```

**OpenClaw Integration:**
- Coder node can dispatch to `codex-agent` via `sessions_spawn` (ACP)
- Results are returned via `sessions_yield`
- Progress tracked in `memory/coding-sessions/` in OpenClaw workspace

**Presets:**
- `local-plan-codex-exec` — local Planner/Reviewer, Codex via OpenClaw for execution
- `all-claude` — Claude Sonnet throughout (API, high quality)
- `local-qwen-coder` — all local, qwen3-coder for coding

---

### 7.5 Team: `transcript-analyzer`
**Pattern:** Pipeline
**Purpose:** Process audio/video transcripts → extract insights, topics, action items

```
Loader
  - Reads: .txt, .vtt, .srt, .json transcript files

Chunker
  - Splits into 2000-token segments with overlap

Analyzer (per chunk, crow / nemotron)
  - Extracts: key topics, speaker intent, action items, decisions made

Aggregator (crow / gpt-oss)
  - Merges all chunk analyses
  - Deduplicates topics
  - Ranks importance

Report Writer (gpt-oss / claude-sonnet)
  - Final structured output:
    - Executive summary
    - Key topics & themes
    - Action items & owners
    - Decisions made
    - Open questions
```

---

### 7.6 Team: `image-collection` (Future — VLM-Powered)
**Pattern:** Parallel Map-Reduce
**Purpose:** Classify and organize large image collections

```
Scanner → [glm46-flash × N] → SQLite index → Organizer
```

GLM-4.6v Flash is already loaded and supports vision + tool_use — it's the right model for this.

---

## 8. Implementation Roadmap

### Phase 1 — Foundation (Week 1)
**Goal:** Preset system + model registry, no new agents yet

- [ ] `config/models.yaml` — full model registry with all your LMStudio models + API models
- [ ] `config/teams/` directory with YAML team definitions
- [ ] `config/presets/` directory with named presets
- [ ] `src/agents/model_factory.py` — resolve aliases to LangChain models
- [ ] `src/agents/team_loader.py` — load team + preset YAML, validate models available
- [ ] Update `run.sh` — add `--team`, `--preset`, `teams`, `presets` commands
- [ ] Update `lms_helper.py` — add `confirm-load` with y/N prompt instead of auto-loading
- [ ] Add `langgraph-supervisor` and `langgraph-swarm` to `pyproject.toml`

**Deliverable:** `./run.sh --team deep-research --preset crow-balanced` works, shows confirmation prompt, launches LangGraph Studio with correct models.

---

### Phase 2 — Deep Research Team (Week 1-2)
**Goal:** First real multi-model team working end-to-end

- [ ] `src/teams/deep_research/graph.py` — Supervisor → [Researcher, Synthesizer] using `langgraph-supervisor`
- [ ] `src/teams/deep_research/agents.py` — define each agent with its tools and prompts
- [ ] `config/teams/deep-research.yaml` — team definition
- [ ] `config/presets/nemotron-fast.yaml`, `crow-balanced.yaml`, `claude-quality.yaml`
- [ ] Test: run deep-research team with 3 different presets
- [ ] Output: save final report to file, not just terminal

**Deliverable:** Research report on any topic, 3+ presets working, output saved.

---

### Phase 3 — Planning/Report Team (Week 2)
**Goal:** Plan-and-Execute pattern for structured planning

- [ ] `src/teams/planning_report/graph.py` — Planner → Executor → Report Writer
- [ ] `config/teams/planning-report.yaml`
- [ ] `config/presets/planning-*.yaml`
- [ ] Test: "Plan a CrispDisplay waitlist email campaign" → structured report

**Deliverable:** Planning team producing actionable plans as Markdown documents.

---

### Phase 4 — Coding Agent Team (Week 2-3)
**Goal:** OpenClaw-integrated coding loop with progress tracking

- [ ] `src/teams/coding_agent/graph.py` — Swarm: Planner ↔ Coder ↔ Reviewer
- [ ] `src/teams/coding_agent/openclaw_bridge.py` — route Coder node to `codex-agent` via OpenClaw ACP
- [ ] `src/teams/coding_agent/progress.py` — read/write `progress.json`, resume support
- [ ] `config/teams/coding-agent.yaml`
- [ ] `config/presets/coding-*.yaml`
- [ ] Test: "Add dark mode to CrispDisplay landing page" → plan → code → review loop

**Deliverable:** Coding team that delegates to Codex, tracks progress, can resume.

---

### Phase 5 — Media Pipeline (Week 3)
**Goal:** File ingest, classify, organize for images/video/audio

- [ ] `src/teams/media_classifier/graph.py` — Pipeline + parallel map for classification
- [ ] `src/teams/media_classifier/ingestor.py` — scan directories, route by type
- [ ] `src/teams/media_classifier/vision.py` — glm46 image classification node
- [ ] `src/teams/media_classifier/index.py` — SQLite-based media index
- [ ] `config/teams/media-classifier.yaml`
- [ ] Test: classify 20 mixed images → check tags + organized output

**Deliverable:** Drop a folder of images/videos → get organized structure + JSON index.

---

### Phase 6 — Transcript Analyzer (Week 3-4)
**Goal:** Process any transcript → structured insights

- [ ] `src/teams/transcript_analyzer/graph.py`
- [ ] `config/teams/transcript-analyzer.yaml`
- [ ] Test: process a meeting transcript → executive summary + action items

---

### Phase 7 — LangGraph Studio Integration + UI (Week 4)
**Goal:** Teams visible and configurable in the LangGraph Studio UI

- [ ] Each team registered as a separate graph in `langgraph.json`
- [ ] Studio shows all teams with their nodes and config
- [ ] Preset picker in Studio UI (via `config_schema`)
- [ ] Human-in-the-loop checkpoints for sensitive steps (approving code, confirming model loads)

---

## 9. File & Folder Structure

```
/Volumes/JS-DEV/local-deep-researcher/
│
├── config/
│   ├── models.yaml              ← Central model registry (all providers)
│   ├── teams/
│   │   ├── deep-research.yaml
│   │   ├── planning-report.yaml
│   │   ├── coding-agent.yaml
│   │   ├── media-classifier.yaml
│   │   └── transcript-analyzer.yaml
│   └── presets/
│       ├── nemotron-fast.yaml
│       ├── crow-balanced.yaml
│       ├── claude-quality.yaml
│       ├── local-plan-codex-exec.yaml
│       └── ...
│
├── src/
│   ├── ollama_deep_researcher/  ← existing code (keep for backward compat)
│   │   ├── graph.py
│   │   ├── configuration.py
│   │   └── ...
│   │
│   └── agents/                  ← NEW
│       ├── __init__.py
│       ├── model_factory.py     ← alias → ChatModel resolver
│       ├── team_loader.py       ← YAML → team config loader
│       ├── registry.py          ← model registry access
│       ├── lms_manager.py       ← wraps lms_helper.py for team use
│       │
│       └── teams/
│           ├── deep_research/
│           │   ├── __init__.py
│           │   ├── graph.py     ← the LangGraph graph
│           │   ├── agents.py    ← agent definitions
│           │   └── prompts.py   ← system prompts
│           ├── planning_report/
│           ├── coding_agent/
│           │   ├── graph.py
│           │   ├── openclaw_bridge.py
│           │   └── progress.py
│           ├── media_classifier/
│           └── transcript_analyzer/
│
├── outputs/                     ← Run outputs (gitignored)
│   ├── research/
│   ├── plans/
│   ├── media-index/
│   └── transcripts/
│
├── lms_helper.py                ← existing, enhance with confirm-load
├── run.sh                       ← existing, extend with --team/--preset
├── test_models.py               ← existing
├── langgraph.json               ← extend: register all team graphs
├── pyproject.toml
└── .env
```

---

## 10. Technology Stack & Dependencies

### Already installed:
- `langgraph` — graph runtime
- `langchain-openai` — OpenAI + LMStudio compat
- `langchain-community` — utilities, search wrappers
- `langchain-ollama` — Ollama provider
- `duckduckgo-search` / `ddgs` — web search

### Add in Phase 1:
```toml
# pyproject.toml additions
"langgraph-supervisor>=0.0.1"    # Supervisor pattern
"langgraph-swarm>=0.0.1"         # Swarm pattern
"langchain-anthropic>=0.3"       # Claude API
"pyyaml>=6.0"                    # YAML config files
"rich>=13.0"                     # Better terminal output
"sqlite-utils>=3.35"             # Media index
```

### For media/transcription (Phase 4-5):
```toml
"ffmpeg-python>=0.2"             # Video frame extraction
"openai-whisper>=20231117"       # Local transcription (or use LMStudio)
"pillow>=10.0"                   # Image handling
```

### OpenClaw ACP Bridge:
- No new package needed — use `openclaw system event` CLI + OpenClaw's `sessions_spawn` / `sessions_send` tools
- The bridge is a thin async wrapper that POSTs to OpenClaw gateway

### Provider comparison (for your reference):

| Provider | Models | Cost | Privacy | Speed | Best for |
|---|---|---|---|---|---|
| LMStudio (local) | Your 30 models | Free | 100% local | Varies | Experimentation, privacy |
| Anthropic API | Claude Sonnet/Opus | ~$3-15/M tok | Cloud | Fast | High quality output |
| OpenAI API | GPT-4o, o3 | ~$2-60/M tok | Cloud | Fast | General capability |
| Ollama (local) | Community models | Free | 100% local | Varies | Alternative to LMStudio |
| OpenClaw ACP | Codex, Donna | Subscription | Local+API | Fast | Orchestration, coding |

---

## 11. Open Questions & Design Decisions

### Q1: Should presets define full model configs or just overrides?
**Recommendation:** Overrides on top of team defaults. Keeps team YAML as the canonical definition; presets only specify what changes.

### Q2: How to handle model conflicts? (Two teams want different models loaded simultaneously)
**Options:**
- A) Each team run is exclusive — unload previous team's models first
- B) Let LMStudio manage memory, just load what's needed
- C) Let user decide (show what's loaded, what's needed, ask)

**Recommendation:** Option C — always show the delta and ask. You already indicated you don't want auto-loading of large models.

### Q3: LangGraph Studio vs custom web UI?
LangGraph Studio (the `langgraph dev` UI) is great for debugging graphs. For production use, a simple custom FastAPI+HTMX UI would be more user-friendly. 

**Recommendation:** Use Studio for now (Phase 1-5). Build a custom UI as Phase 8 if needed.

### Q4: How does the Coding Agent team integrate with OpenClaw?
Options:
- A) Fire-and-forget: send a message to codex-agent session, poll for completion
- B) Two-way: coding agent writes results back to a shared file, progress.json
- C) Webhook: codex-agent notifies when done via `openclaw system event`

**Recommendation:** Option C — use `openclaw system event` callback pattern (already in coding-agent skill). Progress tracked in `progress.json` in the project directory.

### Q5: What's the right model for supervisor roles?
For local: `crow` or `gpt-oss-20b` — they have the best instruction following and tool-calling reliability in your set.
For quality: Claude Sonnet — best for planning, routing, synthesis.

### Q6: How should team YAML reference system prompts — inline or file?
**Recommendation:** Both. Short prompts inline; longer ones as `prompt_file: prompts/researcher.md` (relative to team dir).

---

## Appendix A: LangGraph Multi-Agent Libraries Available

| Library | Pattern | pip install | Status |
|---|---|---|---|
| `langgraph-supervisor` | Hierarchical supervisor | `langgraph-supervisor` | Stable, recommended |
| `langgraph-swarm` | Peer handoffs | `langgraph-swarm` | Stable |
| `langgraph` prebuilt | `create_react_agent` | built-in | Stable |
| `langgraph` `Send()` | Parallel fan-out | built-in | Stable |
| Plan-and-Execute | Custom graph | examples/ | Build from template |

## Appendix B: Relevant LangGraph Patterns (Code Sketches)

### Supervisor (using `langgraph-supervisor`):
```python
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

researcher = create_react_agent(crow_model, tools=[web_search], name="researcher",
    prompt="You are a web researcher. Search thoroughly.")
    
synthesizer = create_react_agent(gpt_model, tools=[], name="synthesizer",
    prompt="You are a report writer. Synthesize research into a structured report.")

supervisor_graph = create_supervisor(
    [researcher, synthesizer],
    model=supervisor_model,
    prompt="You manage a research team. Delegate to researcher for facts, synthesizer for writing."
)

app = supervisor_graph.compile()
result = app.invoke({"messages": [{"role": "user", "content": "Research quantum computing"}]})
```

### Swarm (using `langgraph-swarm`):
```python
from langgraph_swarm import create_swarm, create_handoff_tool
from langchain.agents import create_agent

planner = create_agent(model, name="planner", tools=[
    create_handoff_tool(agent_name="coder", description="Hand off to coder when plan is ready")
], system_prompt="You are a software architect. Create implementation plans.")

coder = create_agent(model, name="coder", tools=[
    write_file, run_tests,
    create_handoff_tool(agent_name="reviewer", description="Hand off to reviewer when code is done")
], system_prompt="You are a senior developer. Implement the plan.")

reviewer = create_agent(model, name="reviewer", tools=[
    create_handoff_tool(agent_name="coder", description="Send back to coder with feedback")
], system_prompt="You are a code reviewer. Check for bugs, style, completeness.")

swarm = create_swarm([planner, coder, reviewer], default_active_agent="planner")
app = swarm.compile()
```

### Parallel Fan-Out (LangGraph `Send()`):
```python
from langgraph.types import Send

def classify_batch(state):
    # Fan out: send each image to a separate classifier invocation
    return [Send("classify_image", {"image_path": img}) for img in state["images"]]

builder.add_conditional_edges("route", classify_batch)
```

---

## Appendix C: Your Current LMStudio Model Roster

| Alias | Model ID | Size | Tool Call | Best Role |
|---|---|---|---|---|
| crow | crow-9b-opus-4.6-distill-heretic_qwen3.5 | 6.3GB | ✅ | Researcher, Reviewer |
| gpt-oss | openai/gpt-oss-20b | 12.1GB | ✅ | Supervisor, Synthesizer |
| nemotron | nvidia/nemotron-3-nano-4b | 2.8GB | ✅ | Fast tasks, routing |
| qwen9b | qwen/qwen3.5-9b | 10.4GB | ✅ | General researcher |
| glm46 | zai-org/glm-4.6v-flash | 7.1GB | ✅ | Vision/image classifier |
| deepseek | deepseek/deepseek-r1-0528-qwen3-8b | 4.6GB | ✅ | Reasoning, analysis |
| qwen3-4b | qwen/qwen3-4b-2507 | 2.3GB | ✅ | Fast synthesis |
| qwen3-4bt | qwen/qwen3-4b-thinking-2507 | 2.3GB | ✅ | Reasoning |
| qwen3-coder | qwen3-coder-30b-a3b-instruct | 18.6GB | ✅ | Coding (heavy) |
| rnj | essentialai/rnj-1 | 5.1GB | ✅ | General |
| devstral | mistralai/devstral-small-2507 | 13.3GB | ✅ | Coding (medium) |
| lfm2 | liquid/lfm2-24b-a2b | 13.4GB | ✅ | General (large) |
| qwen3-8b | qwen/qwen3-8b | 8.7GB | ✅ | Balanced |
| gemma | google/gemma-3n-e4b | 5.9GB | ❌ | Text gen only |

**Recommended baseline team (all fits in ~17GB RAM loaded):**
- Supervisor: `nemotron` (2.8GB, fast routing)
- Researcher: `crow` (6.3GB, good reasoning)
- Synthesizer: `qwen3-4b` (2.3GB, quick writer)
- Coder: `qwen3-coder` via MLX or Codex via OpenClaw

---

*Plan written March 22, 2026. Ready for Phase 1 implementation.*
*Next step: scaffold `config/models.yaml`, `src/agents/model_factory.py`, and extend `run.sh` with `--team` support.*
