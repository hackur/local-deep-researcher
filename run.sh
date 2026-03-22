#!/usr/bin/env bash
# ============================================================
# Local Deep Researcher - Launcher
# Usage:
#   ./run.sh                          # use default model from .env
#   ./run.sh crow                     # Crow-9B Opus 4.6 Distill
#   ./run.sh gpt                      # GPT-OSS 20B
#   ./run.sh glm46                    # GLM-4.6v Flash
#   ./run.sh glm47                    # GLM-4.7 Flash
#   ./run.sh nemotron                 # Nemotron-3 Nano
#   ./run.sh qwen                     # Qwen3.5-9B Q8_0
#   ./run.sh list                     # show available models
#   PORT=8080 ./run.sh                # custom port (default: 2024)
# ============================================================

set -e
cd "$(dirname "$0")"

# Model aliases → LMStudio model IDs
declare -A MODELS
MODELS[crow]="crow-9b-opus-4.6-distill-heretic_qwen3.5"
MODELS[gpt]="openai/gpt-oss-20b"
MODELS[glm46]="zai-org/glm-4.6v-flash"
MODELS[glm47]="zai-org/glm-4.7-flash"
MODELS[nemotron]="nvidia/nemotron-3-nano"
MODELS[qwen]="qwen/qwen3.5-9b"

PORT=${PORT:-2024}

if [[ "$1" == "list" ]]; then
    echo ""
    echo "Available model shortcuts:"
    echo "  crow      → ${MODELS[crow]}"
    echo "  gpt       → ${MODELS[gpt]}"
    echo "  glm46     → ${MODELS[glm46]}"
    echo "  glm47     → ${MODELS[glm47]}"
    echo "  nemotron  → ${MODELS[nemotron]}"
    echo "  qwen      → ${MODELS[qwen]}"
    echo ""
    echo "Currently loaded in LMStudio:"
    curl -s http://localhost:1234/v1/models 2>/dev/null | python3 -c \
        "import json,sys; [print('  ' + m['id']) for m in json.load(sys.stdin)['data']]" \
        || echo "  (LMStudio not running)"
    echo ""
    exit 0
fi

# Set model from shortcut or use as-is
if [[ -n "$1" ]]; then
    if [[ -n "${MODELS[$1]}" ]]; then
        export LOCAL_LLM="${MODELS[$1]}"
        echo "🔍 Model: $1 → ${MODELS[$1]}"
    else
        export LOCAL_LLM="$1"
        echo "🔍 Model: $1 (using as-is)"
    fi
else
    echo "🔍 Using model from .env: $(grep '^LOCAL_LLM=' .env | cut -d= -f2)"
fi

echo "🌐 Search: duckduckgo (no key required)"
echo "🚀 Starting LangGraph dev server on http://localhost:${PORT}"
echo "   Open: http://localhost:${PORT}"
echo ""

exec .venv/bin/langgraph dev --port "$PORT"
