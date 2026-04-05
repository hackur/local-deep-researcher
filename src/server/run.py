#!/usr/bin/env python3
"""
Entry point for the Local Deep Researcher API server.

Usage:
    python -m server.run                     # from src/
    python src/server/run.py                 # from project root
    uvicorn server.main:app --reload         # from src/   (dev mode)
"""

import os
import sys

# Ensure src/ is on the path so both `server` and `ollama_deep_researcher` resolve
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# Load .env from project root if python-dotenv is available
_project_root = os.path.dirname(_src_dir)
_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass


def main():
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
