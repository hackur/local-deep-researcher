#!/usr/bin/env python3
"""
LMStudio helper — called by run.sh to manage models via the v1 REST API.

Usage:
    python lms_helper.py check                    # exit 0 if LMStudio is up
    python lms_helper.py list                     # print installed models + load state
    python lms_helper.py is-loaded <model-id>     # exit 0 if model is loaded
    python lms_helper.py load <model-id>          # load a model, wait for completion
    python lms_helper.py unload <model-id>        # unload a model
"""
import sys
import json
import os

import requests

BASE = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234").rstrip("/")


def check():
    try:
        r = requests.get(f"{BASE}/api/v1/models", timeout=5)
        sys.exit(0 if r.status_code == 200 else 1)
    except Exception:
        sys.exit(1)


def list_models():
    # Loaded state from v0 API
    loaded_ids = set()
    try:
        r0 = requests.get(f"{BASE}/api/v0/models", timeout=5)
        if r0.status_code == 200:
            for m in r0.json().get("data", []):
                if m.get("state") == "loaded":
                    loaded_ids.add(m["id"])
    except Exception:
        pass

    # Full list from v1 API
    r1 = requests.get(f"{BASE}/api/v1/models", timeout=5)
    if r1.status_code != 200:
        print("Error fetching models", file=sys.stderr)
        sys.exit(1)

    models = r1.json().get("models", [])
    print(f"\n  {'STATUS':10}  {'SIZE':6}  MODEL KEY")
    print(f"  {'─'*10}  {'─'*6}  {'─'*62}")
    for m in models:
        key = m.get("key", "?")
        size_gb = m.get("size_bytes", 0) / 1e9
        state = "✅ loaded " if key in loaded_ids else "  ·       "
        print(f"  {state}  {size_gb:5.1f}GB  {key}")
    print()


def is_loaded(model_id: str):
    try:
        r = requests.get(f"{BASE}/api/v0/models", timeout=5)
        if r.status_code == 200:
            loaded = [m["id"] for m in r.json().get("data", []) if m.get("state") == "loaded"]
            sys.exit(0 if model_id in loaded else 1)
    except Exception:
        pass
    sys.exit(1)


def load_model(model_id: str):
    print(f"   ⏳ Loading: {model_id}")
    try:
        r = requests.post(
            f"{BASE}/api/v1/models/load",
            json={"model": model_id, "context_length": 8192},
            timeout=180,
        )
        if r.status_code in (200, 201):
            data = r.json()
            load_time = data.get("load_time_seconds", "?")
            print(f"   ✅ Loaded in {load_time}s")
            sys.exit(0)
        else:
            err = r.json().get("error", {})
            msg = err.get("message", r.text[:300]) if isinstance(err, dict) else str(err)[:300]
            print(f"   ❌ Load failed: {msg}")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        sys.exit(1)


def unload_model(model_id: str):
    print(f"   ⏳ Unloading: {model_id}")
    try:
        r = requests.post(
            f"{BASE}/api/v1/models/unload",
            json={"model": model_id},
            timeout=30,
        )
        if r.status_code in (200, 201):
            print(f"   ✅ Unloaded")
            sys.exit(0)
        else:
            err = r.json().get("error", {})
            msg = err.get("message", r.text[:200]) if isinstance(err, dict) else str(err)[:200]
            print(f"   ❌ Unload failed: {msg}")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd == "check":
        check()
    elif cmd == "list":
        list_models()
    elif cmd == "is-loaded":
        is_loaded(sys.argv[2])
    elif cmd == "load":
        load_model(sys.argv[2])
    elif cmd == "unload":
        unload_model(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
