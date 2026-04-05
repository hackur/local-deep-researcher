#!/usr/bin/env bash
# ============================================================
# Local Deep Researcher — Launcher
#
# QUERY MODE — run research directly, save artifacts:
#   ./run.sh lmstudio <model|alias> "<topic>" [output_dir] [options]
#   ./run.sh ollama <model> "<topic>" [output_dir] [options]
#   ./run.sh openclaw <agent> "<topic>" [output_dir] [options]
#
# OPENCLAW OPTIONS:
#   --tui                 Launch interactive TUI instead of one-shot
#   --session <key>       Explicit session key (default: auto from topic)
#   --thinking <level>    off|minimal|low|medium|high|xhigh
#   --timeout N           Agent timeout in seconds (default: 600)
#
# SERVER MODE — start LangGraph dev server + Studio UI:
#   ./run.sh serve                    # use model from .env
#   ./run.sh serve <alias|model-id>   # use specific model
#   PORT=8080 ./run.sh serve          # custom port
#
# UTILITY:
#   ./run.sh list                     # list all models + aliases
#   ./run.sh help                     # full usage
#
# Examples:
#   ./run.sh lmstudio crow "quantum computing" ./output/quantum
#   ./run.sh lmstudio crow-9b-opus-4.6-distill-heretic_qwen3.5 "AI safety" ./out
#   ./run.sh ollama qwen3:8b "rust vs go" ./output/rust
#   ./run.sh openclaw main "best local LLMs 2026" ./output/llms
#   ./run.sh openclaw main "topic" ./output --tui --thinking medium
#   ./run.sh lmstudio crow "topic" ./out --loops 5 --search tavily
#   ./run.sh serve crow
#
# Aliases (for lmstudio):
#   crow        crow-9b-opus-4.6-distill-heretic_qwen3.5
#   gpt         openai/gpt-oss-20b
#   nemotron    nvidia/nemotron-3-nano-4b
#   qwen9b      qwen/qwen3.5-9b
#   qwen35b     qwen/qwen3.5-35b-a3b
#   qwen27b     qwen3.5-27b-claude-4.6-opus-reasoning-distilled
#   glm46       zai-org/glm-4.6v-flash
#   glm47       zai-org/glm-4.7-flash
#   deepseek    deepseek/deepseek-r1-0528-qwen3-8b
#   qwen3coder  qwen3-coder-30b-a3b-instruct
#   devstral    mistralai/devstral-small-2507
#   (run ./run.sh list for all)
# ============================================================

set -e
cd "$(dirname "$0")"

export LMSTUDIO_BASE_URL="${LMSTUDIO_BASE_URL:-http://localhost:1234}"
PORT="${PORT:-2024}"
PYTHON=".venv/bin/python"
HELPER="lms_helper.py"

# ── Aliases ───────────────────────────────────────────────────
declare -A ALIASES
ALIASES[crow]="crow-9b-opus-4.6-distill-heretic_qwen3.5"
ALIASES[gpt]="openai/gpt-oss-20b"
ALIASES[qwen9b]="qwen/qwen3.5-9b"
ALIASES[qwen35b]="qwen/qwen3.5-35b-a3b"
ALIASES[qwen27b]="qwen3.5-27b-claude-4.6-opus-reasoning-distilled"
ALIASES[qwen0.8b]="qwen3.5-0.8b-mlx-custom"
ALIASES[glm46]="zai-org/glm-4.6v-flash"
ALIASES[glm47]="zai-org/glm-4.7-flash"
ALIASES[glm47mlx5]="glm-4.7-flash-mlx-5"
ALIASES[nemotron]="nvidia/nemotron-3-nano-4b"
ALIASES[nemotron8b]="nvidia/nemotron-3-nano"
ALIASES[poe]="poe-8b-glm5-opus4.6-sonnet4.5-kimi-grok-gemini-3-pro-preview-heretic"
ALIASES[poe-i1]="poe-8b-glm5-opus4.6-sonnet4.5-kimi-grok-gemini-3-pro-preview-heretic-i1"
ALIASES[rnj]="essentialai/rnj-1"
ALIASES[lfm2]="liquid/lfm2-24b-a2b"
ALIASES[devstral]="mistralai/devstral-small-2507"
ALIASES[qwen3-4b]="qwen/qwen3-4b-2507"
ALIASES[qwen3-4bt]="qwen/qwen3-4b-thinking-2507"
ALIASES[qwen3-8b]="qwen/qwen3-8b"
ALIASES[qwen3coder]="qwen3-coder-30b-a3b-instruct"
ALIASES[deepseek]="deepseek/deepseek-r1-0528-qwen3-8b"
ALIASES[gemma]="google/gemma-3n-e4b"
ALIASES[tinyllama]="tinyllama-1.1b-chat-v1.0"

# Helper: resolve alias → model ID
resolve_model() {
    local input="$1"
    if [[ -n "${ALIASES[$input]}" ]]; then
        echo "${ALIASES[$input]}"
    else
        echo "$input"
    fi
}

# ── list ──────────────────────────────────────────────────────
if [[ "$1" == "list" ]]; then
    echo ""
    echo "📦 LMStudio models:"
    if $PYTHON $HELPER check 2>/dev/null; then
        $PYTHON $HELPER list
    else
        echo "  (LMStudio not running)"
    fi

    echo "📦 Ollama models:"
    if command -v ollama &>/dev/null && curl -s http://localhost:11434/api/tags &>/dev/null; then
        ollama list 2>/dev/null | head -20
    else
        echo "  (Ollama not running)"
    fi

    echo ""
    echo "📦 OpenClaw agents:"
    if command -v openclaw &>/dev/null; then
        echo "  main         — Main agent (default)"
        echo "  codex-agent  — Codex GPT-5 coding agent"
    else
        echo "  (openclaw not installed)"
    fi

    echo ""
    echo "🏷️  Aliases (for lmstudio):"
    for alias in $(echo "${!ALIASES[@]}" | tr ' ' '\n' | sort); do
        printf "  %-12s → %s\n" "$alias" "${ALIASES[$alias]}"
    done
    echo ""
    exit 0
fi

# ── help ──────────────────────────────────────────────────────
if [[ "$1" == "help" || "$1" == "--help" || "$1" == "-h" || -z "$1" ]]; then
    cat <<'EOF'
Local Deep Researcher

QUERY MODE (direct research → artifacts):
  ./run.sh <provider> <model> "<topic>" [output_dir] [options]

  Providers:
    lmstudio   Local LMStudio models (localhost:1234)
    ollama     Local Ollama models (localhost:11434)
    openclaw   OpenClaw gateway agent

  Examples:
    ./run.sh lmstudio crow "quantum computing" ./output/quantum
    ./run.sh lmstudio crow-9b-opus-4.6-distill-heretic_qwen3.5 "AI" ./out
    ./run.sh ollama qwen3:8b "rust vs go" ./output/rust
    ./run.sh openclaw main "best LLMs 2026" ./output/llms

  Options (lmstudio/ollama):
    --loops N          Max research loops (default: 3)
    --search API       duckduckgo|tavily|perplexity|searxng
    --no-full-page     Skip full page content fetching

  Options (openclaw):
    --tui              Launch interactive TUI (persistent session)
    --session KEY      Explicit session key (default: auto from topic)
    --thinking LEVEL   off|minimal|low|medium|high|xhigh
    --timeout N        Agent timeout in seconds (default: 600)

SERVER MODE (LangGraph Studio UI):
  ./run.sh serve                      Start with model from .env
  ./run.sh serve <alias|model-id>     Start with specific model
  PORT=8080 ./run.sh serve            Custom port

UTILITY:
  ./run.sh list                       List all models + aliases
  ./run.sh help                       This message

Output (query mode):
  <output_dir>/summary.md             Final research report
  <output_dir>/state.json             Full graph state
  <output_dir>/metadata.json          Run metadata (timing, config, session key)
EOF
    exit 0
fi

# ══════════════════════════════════════════════════════════════
# SERVER MODE — ./run.sh serve [model]
# ══════════════════════════════════════════════════════════════
if [[ "$1" == "serve" ]]; then
    shift

    if [[ -n "$1" ]]; then
        MODEL_ID="$(resolve_model "$1")"
        if [[ "$1" != "$MODEL_ID" ]]; then
            echo "🔍 Model: $1 → $MODEL_ID"
        else
            echo "🔍 Model: $MODEL_ID"
        fi
        export LOCAL_LLM="$MODEL_ID"
    else
        MODEL_ID="$(grep '^LOCAL_LLM=' .env | sed 's/LOCAL_LLM=//' | tr -d '"')"
        echo "🔍 Model from .env: $MODEL_ID"
    fi

    if ! $PYTHON $HELPER check; then
        echo "❌ LMStudio not running at ${LMSTUDIO_BASE_URL}"
        exit 1
    fi

    if $PYTHON $HELPER is-loaded "$MODEL_ID"; then
        echo "✅ Model already loaded"
    else
        echo "📥 Loading model..."
        $PYTHON $HELPER load "$MODEL_ID"
    fi

    SEARCH_API="$(grep '^SEARCH_API=' .env | sed 's/SEARCH_API=//' | tr -d '"')"
    echo "🌐 Search: ${SEARCH_API:-duckduckgo}"
    echo "🚀 Starting LangGraph dev server → http://localhost:${PORT}"
    echo ""
    exec .venv/bin/langgraph dev --port "$PORT"
fi

# ══════════════════════════════════════════════════════════════
# QUERY MODE — ./run.sh <provider> <model> "<topic>" [output_dir]
# ══════════════════════════════════════════════════════════════

PROVIDER="$1"; shift

# Validate provider
if [[ "$PROVIDER" != "lmstudio" && "$PROVIDER" != "ollama" && "$PROVIDER" != "openclaw" ]]; then
    echo "❌ Unknown command or provider: $PROVIDER"
    echo ""
    echo "Usage:"
    echo "  ./run.sh <lmstudio|ollama|openclaw> <model> \"<topic>\" [output_dir]"
    echo "  ./run.sh serve [model]"
    echo "  ./run.sh list"
    echo "  ./run.sh help"
    exit 1
fi

if [[ $# -lt 2 ]]; then
    echo "❌ Usage: ./run.sh $PROVIDER <model> \"<topic>\" [output_dir] [options]"
    exit 1
fi

RAW_MODEL="$1"; shift
TOPIC="$1"; shift

# Resolve alias (works for all providers, but mainly useful for lmstudio)
MODEL_ID="$(resolve_model "$RAW_MODEL")"
if [[ "$RAW_MODEL" != "$MODEL_ID" ]]; then
    echo "🔍 Alias: $RAW_MODEL → $MODEL_ID"
fi

# Parse remaining args: output_dir + flags
OUTPUT_DIR=""
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --*)
            EXTRA_ARGS+=("$1"); shift
            # Grab value for flags that take one (unless next arg is also a flag)
            if [[ $# -gt 0 && ! "$1" == --* ]]; then
                EXTRA_ARGS+=("$1"); shift
            fi
            ;;
        *)
            if [[ -z "$OUTPUT_DIR" ]]; then
                OUTPUT_DIR="$1"; shift
            else
                EXTRA_ARGS+=("$1"); shift
            fi
            ;;
    esac
done

# ── Provider checks + model loading ──────────────────────────
if [[ "$PROVIDER" == "lmstudio" ]]; then
    if ! $PYTHON $HELPER check 2>/dev/null; then
        echo "❌ LMStudio not running at ${LMSTUDIO_BASE_URL}"
        echo "   Start LMStudio and enable the local server."
        exit 1
    fi
    if $PYTHON $HELPER is-loaded "$MODEL_ID" 2>/dev/null; then
        echo "✅ Model loaded: $MODEL_ID"
    else
        echo "📥 Loading model: $MODEL_ID"
        $PYTHON $HELPER load "$MODEL_ID"
    fi

elif [[ "$PROVIDER" == "ollama" ]]; then
    if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
        echo "❌ Ollama not running at http://localhost:11434"
        echo "   Start Ollama: ollama serve"
        exit 1
    fi
    echo "✅ Ollama running, model: $MODEL_ID"

elif [[ "$PROVIDER" == "openclaw" ]]; then
    if ! command -v openclaw &>/dev/null; then
        echo "❌ 'openclaw' CLI not found"
        exit 1
    fi
    echo "✅ OpenClaw gateway, agent: $MODEL_ID"
fi

# ── Execute ───────────────────────────────────────────────────
CMD=("$PYTHON" -m ollama_deep_researcher.cli_runner "$PROVIDER" "$MODEL_ID" "$TOPIC")
if [[ -n "$OUTPUT_DIR" ]]; then
    CMD+=("$OUTPUT_DIR")
fi
CMD+=("${EXTRA_ARGS[@]}")

exec "${CMD[@]}"
