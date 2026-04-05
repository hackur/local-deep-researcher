# Quick Start — See It Working in 5 Minutes

> Get your deep research agent running in the browser with LangGraph Studio + your local models.

---

## Prerequisites

✅ **LMStudio** running at `http://localhost:1234` with at least one model installed  
✅ **Python 3.11+** with the virtual environment set up  
✅ **This repo** cloned to `/Volumes/JS-DEV/local-deep-researcher`

---

## Step 1: Install Dependencies (if not already done)

```bash
cd /Volumes/JS-DEV/local-deep-researcher

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install the project
pip install -e .
pip install -U "langgraph-cli[inmem]"
```

---

## Step 2: Check Available Models

```bash
./run.sh list
```

You should see output like:
```
📦 Models installed in LMStudio:

  STATUS      SIZE    MODEL KEY
  ──────────  ──────  ──────────────────────────────────────────────────
  ✅ loaded   6.3GB  crow-9b-opus-4.6-distill-heretic_qwen3.5
    ·         12.1GB  openai/gpt-oss-20b
    ·         2.8GB  nvidia/nemotron-3-nano-4b
  ...

Shortcuts:
  crow          → crow-9b-opus-4.6-distill-heretic_qwen3.5
  gpt           → openai/gpt-oss-20b
  nemotron      → nvidia/nemotron-3-nano-4b
  ...
```

---

## Step 3: Start the Agent Server

**Option A: Use default model from `.env`** (currently `crow`)
```bash
./run.sh
```

**Option B: Use a specific model by alias**
```bash
./run.sh nemotron   # Fast, tiny model
./run.sh crow       # Balanced reasoning model
./run.sh gpt        # Larger, high-quality model
```

**What happens:**
1. Script checks if LMStudio is running
2. Checks if the model is already loaded
3. If not loaded → auto-loads it (takes ~8-15 seconds)
4. Starts `langgraph dev` server on `http://localhost:2024`
5. Opens your browser to **LangSmith Studio**

You should see:
```
🔍 Model: crow → crow-9b-opus-4.6-distill-heretic_qwen3.5
✅ Model already loaded
🌐 Search: duckduckgo
🚀 Starting LangGraph dev server → http://localhost:2024

> Ready!
> - API: http://localhost:2024
> - Docs: http://localhost:2024/docs
> - LangGraph Studio Web UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

---

## Step 4: Use the Studio UI

Your browser should automatically open to:
```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

### First Time Setup:
1. Studio will prompt to **connect to your local server**
2. Click **"Connect to a local server"**
3. Enter: `http://127.0.0.1:2024`
4. Click **"Connect"**

### The Studio Interface:

#### 1. **Graph View** (left side)
You'll see your research graph visualized:
```
START
  ↓
generate_query
  ↓
web_research
  ↓
summarize_sources
  ↓
reflect_on_summary
  ↓
[loop or finalize]
  ↓
finalize_summary
  ↓
END
```

#### 2. **Configuration Tab** (top)
- **Model:** Select or confirm your model
- **Research Depth:** Number of loops (default: 3)
- **Search API:** duckduckgo (default)
- **Fetch Full Page:** true/false

#### 3. **Input Panel** (right side)
Enter a research topic:
```
Research quantum computing error correction methods
```

#### 4. **Run** Button
Click **"Run"** to start the agent.

---

## Step 5: Watch It Work

### What You'll See:

**Node: generate_query**
- ✅ Complete
- Output: `{"search_query": "quantum computing error correction methods 2026"}`

**Node: web_research**
- ✅ Complete
- Found 3 sources from DuckDuckGo
- Fetched full page content

**Node: summarize_sources**
- ✅ Complete
- Running summary: _"Quantum error correction is essential for..."_

**Node: reflect_on_summary**
- ✅ Complete
- Knowledge gap: _"Need more details on surface codes"_
- Follow-up query: `"surface code quantum error correction implementation"`

**[Loop 2]**
- Repeats: web_research → summarize_sources → reflect_on_summary

**Node: finalize_summary**
- ✅ Complete
- Final output: Markdown report with sources

### Click Any Node:
- **State** tab — see the full graph state at that point
- **Messages** tab — see LLM input/output
- **Metadata** tab — timing, model used, tokens

---

## Step 6: View the Final Report

After the graph completes, scroll to the **finalize_summary** node.

Click **"State"** → **"running_summary"**

You'll see:
```markdown
## Summary
Quantum error correction is a critical component of quantum computing that addresses...

[3-5 paragraphs of synthesized research]

### Sources:
* Quantum Error Correction Overview : https://example.com/qec-overview
* Surface Codes Explained : https://example.com/surface-codes
* Recent Advances in QEC : https://example.com/qec-2026
...
```

---

## Troubleshooting

### "LMStudio not running"
```bash
# Start LMStudio manually
# In LMStudio: go to Local Server tab → Start Server
# Verify with:
curl http://localhost:1234/api/v1/models
```

### "Model failed to load"
```bash
# Check LMStudio has enough RAM (model size + 2GB overhead)
# Try a smaller model:
./run.sh nemotron  # Only 2.8GB
```

### "Studio won't connect" (Safari users)
Safari blocks localhost mixed content. Solutions:
1. **Use Firefox or Chrome** (recommended)
2. OR use `--tunnel` flag:
   ```bash
   langgraph dev --port 2024 --tunnel
   ```
   Then copy the tunnel URL and paste into Studio's "Connect to local server" dialog.

### "Graph runs but no output"
Check your `.env` file has:
```bash
USE_TOOL_CALLING=True  # ← REQUIRED for local models
```

If it's `False`, set it to `True` and restart.

---

## Next Steps

### Test Different Models
```bash
# Try a larger model for better quality
./run.sh gpt

# Try the fastest model
./run.sh nemotron

# Try a reasoning model
./run.sh deepseek
```

### Adjust Research Depth
In Studio's **Configuration** tab:
- Set **Research Depth** to `1` for fast tests
- Set to `5` for deeper research

### Change Search API
If you have API keys:
```bash
# In .env
SEARCH_API=tavily
TAVILY_API_KEY=tvly-xxxxx
```

Then restart the server.

### Run from API (No UI)
```bash
curl -X POST http://localhost:2024/runs/stream \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "ollama_deep_researcher",
    "input": {"research_topic": "quantum computing"},
    "stream_mode": "updates"
  }'
```

### Explore the Code
- `src/ollama_deep_researcher/graph.py` — graph definition
- `src/ollama_deep_researcher/prompts.py` — system prompts
- `src/ollama_deep_researcher/utils.py` — search functions
- `.env` — configuration

---

## What's Next?

You now have a working deep research agent! Next up:

1. **Read PLAN.md** — see the full multi-agent platform vision
2. **Read STACK_ANALYSIS.md** — understand the architecture
3. **Experiment** — try different topics, models, settings
4. **Build Phase 1** — multi-model teams with supervisor pattern

Ready to go deeper? Let me know!
