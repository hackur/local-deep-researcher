#!/usr/bin/env python3
"""
CLI runner — execute the deep research graph directly from the command line.

Supports three providers:
  - lmstudio: Local models via LMStudio OpenAI-compat API (localhost:1234)
  - ollama:   Local models via Ollama API (localhost:11434)
  - openclaw: Route through OpenClaw gateway agent turn

Usage:
  python -m ollama_deep_researcher.cli_runner <provider> <model> "<topic>" [output_dir]
  python -m ollama_deep_researcher.cli_runner lmstudio crow-9b-opus-4.6-distill-heretic_qwen3.5 "quantum computing" ./output
  python -m ollama_deep_researcher.cli_runner ollama qwen3:8b "rust vs go for web servers" ./output
  python -m ollama_deep_researcher.cli_runner openclaw main "best local LLMs 2026" ./output

Output directory structure:
  <output_dir>/
    summary.md          — final research report with sources
    state.json          — full graph state (all sources, queries, loop data)
    metadata.json       — run metadata (provider, model, timing, config)
"""

import argparse
import json
import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path


def run_langgraph(provider: str, model: str, topic: str, output_dir: str, **kwargs):
    """Run the deep research graph directly (no server needed)."""

    # Set environment for this run
    os.environ["LLM_PROVIDER"] = provider if provider != "openclaw" else "lmstudio"
    os.environ["LOCAL_LLM"] = model
    os.environ["USE_TOOL_CALLING"] = "True"
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_CALLBACKS_DISABLED"] = "true"
    os.environ["DO_NOT_TRACK"] = "1"

    if provider == "lmstudio":
        os.environ["LMSTUDIO_BASE_URL"] = kwargs.get(
            "base_url", "http://localhost:1234/v1"
        )
    elif provider == "ollama":
        os.environ["OLLAMA_BASE_URL"] = kwargs.get(
            "base_url", "http://localhost:11434/"
        )

    max_loops = int(kwargs.get("max_loops", os.environ.get("MAX_WEB_RESEARCH_LOOPS", "3")))
    os.environ["MAX_WEB_RESEARCH_LOOPS"] = str(max_loops)

    search_api = kwargs.get("search_api", os.environ.get("SEARCH_API", "duckduckgo"))
    os.environ["SEARCH_API"] = search_api

    fetch_full = kwargs.get("fetch_full_page", os.environ.get("FETCH_FULL_PAGE", "True"))
    os.environ["FETCH_FULL_PAGE"] = str(fetch_full)

    # Import graph (after env is set)
    from ollama_deep_researcher.graph import graph
    from ollama_deep_researcher.configuration import Configuration

    # Prepare output directory
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Build config
    config = {
        "configurable": {
            "llm_provider": provider if provider != "openclaw" else "lmstudio",
            "local_llm": model,
            "use_tool_calling": True,
            "max_web_research_loops": max_loops,
            "search_api": search_api,
            "fetch_full_page": str(fetch_full).lower() == "true",
        }
    }

    if provider == "lmstudio":
        config["configurable"]["lmstudio_base_url"] = os.environ.get(
            "LMSTUDIO_BASE_URL", "http://localhost:1234/v1"
        )
    elif provider == "ollama":
        config["configurable"]["ollama_base_url"] = os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434/"
        )

    print(f"\n{'='*60}")
    print(f"🔬 Deep Research — CLI Runner")
    print(f"{'='*60}")
    print(f"  Provider:  {provider}")
    print(f"  Model:     {model}")
    print(f"  Topic:     {topic}")
    print(f"  Output:    {out.resolve()}")
    print(f"  Search:    {search_api}")
    print(f"  Loops:     {max_loops}")
    print(f"{'='*60}\n")

    start_time = time.time()

    # Use invoke to get the complete final state in one pass
    # We wrap it with progress callbacks via stream
    accumulated = {
        "research_topic": topic,
        "running_summary": "",
        "search_query": "",
        "research_loop_count": 0,
        "sources_gathered": [],
        "web_research_results": [],
    }

    for event in graph.stream(
        {"research_topic": topic},
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in event.items():
            # Merge updates into accumulated state
            for k, v in node_output.items():
                if k in ("sources_gathered", "web_research_results") and isinstance(v, list):
                    accumulated.setdefault(k, []).extend(v)
                else:
                    accumulated[k] = v

            if node_name == "generate_query":
                query = node_output.get("search_query", "?")
                print(f"  🔍 [{node_name}] Query: {query}")

            elif node_name == "web_research":
                loop_count = node_output.get("research_loop_count", 0)
                sources = node_output.get("sources_gathered", [""])
                n_sources = len([
                    l for l in sources[-1].split("\n") if l.strip().startswith("*")
                ]) if sources else 0
                print(f"  🌐 [{node_name}] Loop {loop_count}/{max_loops} — {n_sources} sources found")

            elif node_name == "summarize_sources":
                summary = node_output.get("running_summary", "")
                words = len(summary.split())
                print(f"  📝 [{node_name}] Summary updated ({words} words)")

            elif node_name == "reflect_on_summary":
                query = node_output.get("search_query", "?")
                print(f"  🤔 [{node_name}] Follow-up: {query}")

            elif node_name == "finalize_summary":
                print(f"  ✅ [{node_name}] Report finalized")

    elapsed = time.time() - start_time
    print(f"\n  ⏱️  Completed in {elapsed:.1f}s")

    result = accumulated
    summary = result.get("running_summary", "No summary produced")

    # Write outputs
    # 1. summary.md
    summary_path = out / "summary.md"
    with open(summary_path, "w") as f:
        f.write(f"# Deep Research: {topic}\n\n")
        f.write(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        f.write(f"*Provider: {provider} | Model: {model}*\n\n")
        f.write("---\n\n")
        f.write(summary)
    print(f"  📄 Saved: {summary_path}")

    # 2. state.json
    state_path = out / "state.json"
    # Serialize what we can
    state_data = {
        "research_topic": topic,
        "running_summary": result.get("running_summary"),
        "search_query": result.get("search_query"),
        "research_loop_count": result.get("research_loop_count"),
        "sources_gathered": result.get("sources_gathered", []),
        "web_research_results": result.get("web_research_results", []),
    }
    with open(state_path, "w") as f:
        json.dump(state_data, f, indent=2, default=str)
    print(f"  📄 Saved: {state_path}")

    # 3. metadata.json
    meta_path = out / "metadata.json"
    metadata = {
        "provider": provider,
        "model": model,
        "topic": topic,
        "search_api": search_api,
        "max_loops": max_loops,
        "actual_loops": result.get("research_loop_count", 0),
        "fetch_full_page": str(fetch_full).lower() == "true",
        "elapsed_seconds": round(elapsed, 2),
        "timestamp": datetime.now().isoformat(),
        "output_dir": str(out.resolve()),
        "summary_words": len(result.get("running_summary", "").split()),
        "total_sources": len(result.get("sources_gathered", [])),
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  📄 Saved: {meta_path}")

    print(f"\n{'='*60}")
    print(f"  ✅ Done! Report: {summary_path}")
    print(f"{'='*60}\n")

    return result


def make_session_key(topic: str) -> str:
    """Generate a stable, readable session key from a topic string."""
    slug = topic.lower()[:60].replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-")
    return f"deep-research-{slug}"


def run_openclaw(topic: str, output_dir: str, **kwargs):
    """Run research via OpenClaw gateway agent turn.

    Uses `openclaw agent` with a stable --session-id derived from the topic,
    so the conversation persists and you can follow up later via:
      openclaw tui --session "deep-research-<topic-slug>"

    The agent_id param selects which openclaw agent handles it (default: main).
    """
    agent_id = kwargs.get("agent_id", "main")
    timeout = kwargs.get("timeout", 600)
    session_key = kwargs.get("session_key") or make_session_key(topic)
    tui_mode = kwargs.get("tui", False)
    thinking = kwargs.get("thinking", None)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"🔬 Deep Research — OpenClaw Gateway")
    print(f"{'='*60}")
    print(f"  Agent:     {agent_id}")
    print(f"  Session:   {session_key}")
    print(f"  Topic:     {topic}")
    print(f"  Output:    {out.resolve()}")
    print(f"  Timeout:   {timeout}s")
    if thinking:
        print(f"  Thinking:  {thinking}")
    print(f"{'='*60}\n")

    # If --tui flag, launch interactive TUI with the session and initial message
    if tui_mode:
        message = (
            f"Perform deep web research on this topic. Search the web iteratively, "
            f"reflect on gaps, search again, and produce a comprehensive markdown "
            f"report with all sources cited.\n\nTopic: {topic}"
        )
        cmd = [
            "openclaw", "tui",
            "--session", session_key,
            "--message", message,
        ]
        if thinking:
            cmd += ["--thinking", thinking]
        print(f"  🖥️  Launching TUI session: {session_key}")
        print(f"  💡 You can reconnect later with:")
        print(f"     openclaw tui --session \"{session_key}\"")
        print()

        # Save session info before launching TUI
        meta_path = out / "metadata.json"
        metadata = {
            "provider": "openclaw",
            "agent_id": agent_id,
            "session_key": session_key,
            "topic": topic,
            "mode": "tui",
            "timestamp": datetime.now().isoformat(),
            "output_dir": str(out.resolve()),
            "reconnect_cmd": f'openclaw tui --session "{session_key}"',
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"  📄 Saved: {meta_path}")
        print()

        os.execvp("openclaw", cmd)
        # Does not return — replaces this process with TUI

    # One-shot mode: send message, wait for reply, save artifacts
    message = (
        f"Perform deep web research on the following topic and produce a comprehensive "
        f"markdown report with sources. Search the web iteratively — generate queries, "
        f"gather results, summarize, reflect on knowledge gaps, search again. "
        f"Do at least 3 research loops. Return the full report with all sources.\n\n"
        f"Topic: {topic}"
    )

    start_time = time.time()

    cmd = [
        "openclaw", "agent",
        "--session-id", session_key,
        "--message", message,
        "--timeout", str(timeout),
        "--json",
    ]
    if agent_id != "main":
        cmd += ["--agent", agent_id]
    if thinking:
        cmd += ["--thinking", thinking]

    print(f"  🚀 Sending to OpenClaw agent '{agent_id}' (session: {session_key})...")
    print(f"  💡 Follow up interactively:")
    print(f"     openclaw tui --session \"{session_key}\"")
    print()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )

        elapsed = time.time() - start_time

        if result.returncode != 0:
            print(f"  ❌ OpenClaw error (exit {result.returncode}):")
            stderr = result.stderr[:500] if result.stderr else "(no stderr)"
            print(f"     {stderr}")
            sys.exit(1)

        # Parse JSON output
        try:
            response = json.loads(result.stdout)
            reply = response.get("reply", response.get("message", result.stdout))
        except json.JSONDecodeError:
            reply = result.stdout

        print(f"  ⏱️  Completed in {elapsed:.1f}s")

        # Write outputs
        summary_path = out / "summary.md"
        with open(summary_path, "w") as f:
            f.write(f"# Deep Research: {topic}\n\n")
            f.write(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
            f.write(f"*Provider: openclaw | Agent: {agent_id} | Session: {session_key}*\n\n")
            f.write("---\n\n")
            f.write(str(reply))
        print(f"  📄 Saved: {summary_path}")

        meta_path = out / "metadata.json"
        metadata = {
            "provider": "openclaw",
            "agent_id": agent_id,
            "session_key": session_key,
            "topic": topic,
            "mode": "agent",
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.now().isoformat(),
            "output_dir": str(out.resolve()),
            "reconnect_cmd": f'openclaw tui --session "{session_key}"',
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"  📄 Saved: {meta_path}")

        print(f"\n{'='*60}")
        print(f"  ✅ Done! Report: {summary_path}")
        print(f"  💡 Continue this session:")
        print(f"     openclaw tui --session \"{session_key}\"")
        print(f"{'='*60}\n")

        return reply

    except subprocess.TimeoutExpired:
        print(f"  ❌ Timed out after {timeout}s")
        print(f"  💡 The session may still be running. Check with:")
        print(f"     openclaw tui --session \"{session_key}\"")
        sys.exit(1)
    except FileNotFoundError:
        print(f"  ❌ 'openclaw' CLI not found. Install: npm i -g openclaw")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run deep research directly from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s lmstudio crow "quantum computing advances" ./output/quantum
  %(prog)s ollama qwen3:8b "rust vs go performance" ./output/rust-go
  %(prog)s openclaw main "best local LLMs 2026" ./output/llms

Aliases (for lmstudio provider):
  crow, gpt, nemotron, qwen9b, glm46, deepseek, qwen3coder, etc.
  Use './run.sh list' to see all available models and aliases.
        """,
    )

    parser.add_argument(
        "provider",
        choices=["lmstudio", "ollama", "openclaw"],
        help="LLM provider to use",
    )
    parser.add_argument(
        "model",
        help="Model name/ID (or 'main'/'codex-agent' for openclaw)",
    )
    parser.add_argument(
        "topic",
        help="Research topic (quoted string)",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help="Output directory (default: ./output/<topic-slug>/<timestamp>)",
    )

    parser.add_argument("--loops", type=int, default=3, help="Max research loops (default: 3)")
    parser.add_argument("--search", default="duckduckgo", help="Search API (default: duckduckgo)")
    parser.add_argument("--no-full-page", action="store_true", help="Skip full page fetching")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds for openclaw (default: 600)")
    parser.add_argument("--tui", action="store_true", help="Launch openclaw TUI for interactive session")
    parser.add_argument("--session", default=None, help="Explicit session key for openclaw (default: auto from topic)")
    parser.add_argument("--thinking", default=None,
                        choices=["off", "minimal", "low", "medium", "high", "xhigh"],
                        help="Thinking level for openclaw agent")

    args = parser.parse_args()

    # Generate default output dir if not specified
    if args.output_dir is None:
        slug = args.topic.lower()[:50].replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output_dir = f"./output/{slug}/{timestamp}"

    if args.provider == "openclaw":
        run_openclaw(
            topic=args.topic,
            output_dir=args.output_dir,
            agent_id=args.model,
            timeout=args.timeout,
            tui=args.tui,
            session_key=args.session,
            thinking=args.thinking,
        )
    else:
        run_langgraph(
            provider=args.provider,
            model=args.model,
            topic=args.topic,
            output_dir=args.output_dir,
            max_loops=args.loops,
            search_api=args.search,
            fetch_full_page=not args.no_full_page,
        )


if __name__ == "__main__":
    main()
