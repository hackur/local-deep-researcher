#!/usr/bin/env python3
"""
Test Local Deep Researcher with all configured LMStudio models.
Usage: python test_models.py [model_alias]
       python test_models.py all    # test all models
       python test_models.py crow   # test one model
"""
import sys
import time
import asyncio
import requests

# Model aliases → LMStudio IDs
MODELS = {
    "crow":     "crow-9b-opus-4.6-distill-heretic_qwen3.5",
    "gpt":      "openai/gpt-oss-20b",
    "glm46":    "zai-org/glm-4.6v-flash",
    "glm47":    "glm-4.7-flash-mlx-5",          # may fail if RAM insufficient
    "nemotron": "nvidia/nemotron-3-nano-4b",
    "qwen":     "qwen/qwen3.5-9b",
}

TOPIC = "What is LangGraph?"


def check_lmstudio():
    """Check LMStudio is running and return loaded model IDs."""
    try:
        resp = requests.get("http://localhost:1234/v1/models", timeout=5)
        if resp.status_code == 200:
            ids = [m["id"] for m in resp.json()["data"]]
            return ids
    except Exception:
        pass
    return None


async def test_model(model_id: str, alias: str) -> bool:
    from ollama_deep_researcher.graph import graph

    config = {
        "configurable": {
            "local_llm": model_id,
            "llm_provider": "lmstudio",
            "search_api": "duckduckgo",
            "max_web_research_loops": 1,
            "use_tool_calling": True,
            "fetch_full_page": False,
        }
    }

    t0 = time.time()
    result = None
    try:
        async for event in graph.astream(
            {"research_topic": TOPIC}, config=config, stream_mode="values"
        ):
            result = event
    except Exception as e:
        print(f"  ❌ [{alias}] ERROR: {e}")
        return False

    elapsed = time.time() - t0

    if result and "running_summary" in result:
        summary = result["running_summary"]
        print(f"  ✅ [{alias}] {model_id} — {elapsed:.0f}s")
        print(f"     {summary[:150].strip()}...")
        return True
    else:
        print(f"  ⚠️  [{alias}] {model_id} — no summary produced ({elapsed:.0f}s)")
        return False


async def main():
    print("\n🔍 Local Deep Researcher — Model Test")
    print("=" * 60)

    # Check LMStudio
    loaded = check_lmstudio()
    if loaded is None:
        print("❌ LMStudio not running at localhost:1234")
        sys.exit(1)
    print(f"✅ LMStudio running ({len(loaded)} models loaded)")

    # Determine which models to test
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "all":
        to_test = list(MODELS.items())
    elif arg in MODELS:
        to_test = [(arg, MODELS[arg])]
    else:
        # treat as raw model ID
        to_test = [(arg, arg)]

    print(f"\n📋 Testing {len(to_test)} model(s) on topic: '{TOPIC}'\n")

    results = {}
    for alias, model_id in to_test:
        if model_id not in loaded:
            print(f"  ⏭️  [{alias}] {model_id} — not currently loaded in LMStudio, skipping")
            results[alias] = None
            continue
        print(f"  🚀 Testing [{alias}] {model_id}...")
        ok = await test_model(model_id, alias)
        results[alias] = ok
        print()

    # Summary
    print("=" * 60)
    print("Results:")
    for alias, ok in results.items():
        status = "✅ PASS" if ok else ("⏭️  SKIP" if ok is None else "❌ FAIL")
        print(f"  {status}  {alias} ({MODELS.get(alias, alias)})")

    failures = [k for k, v in results.items() if v is False]
    if failures:
        print(f"\n⚠️  {len(failures)} model(s) failed: {', '.join(failures)}")
        sys.exit(1)
    else:
        print("\n✅ All tested models passed!")


if __name__ == "__main__":
    asyncio.run(main())
