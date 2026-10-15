"""Start, stop, or inspect a llama-server profile from the command line.

Usage:
    python tools/llm_server.py status [--profile NAME]
    python tools/llm_server.py start  [--profile NAME]
    python tools/llm_server.py stop   [--profile NAME]
    python tools/llm_server.py profiles

Profiles live in determined/agent/llm_client.py (_PROFILES). Only one profile's
server fits in VRAM on the 8 GB card, so stop the running one before starting
another; `start` refuses to stack a second server and says which port is busy.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=["status", "start", "stop", "profiles"])
    ap.add_argument("--profile", help="profile name (default: env/cfg/analysis)")
    args = ap.parse_args(argv)

    if args.profile:
        os.environ["DETERMINED_LLM_PROFILE"] = args.profile

    from determined.agent import llm_client as lc

    if args.action == "profiles":
        for name, p in lc._PROFILES.items():
            mark = "*" if name == lc.LLM_PROFILE else " "
            print(f"{mark} {name:9s} port {p['port']}  {p['display_name']}")
        return 0

    print(f"profile={lc.LLM_PROFILE} port={lc.LLM_PORT} model={lc.LLM_DISPLAY_NAME}")

    if args.action == "status":
        up = lc.is_available(timeout=3)
        print("running" if up else "not running")
        for pid, cmd in lc._llama_servers():
            print(f"  llama-server pid {pid} port {lc._parse_port(cmd)}")
        return 0 if up else 1

    if args.action == "start":
        if lc.is_available(timeout=3):
            print("already running")
            return 0
        others = [(pid, lc._parse_port(cmd)) for pid, cmd in lc._llama_servers()]
        if others:
            print("another llama-server is running (VRAM is shared): "
                  + ", ".join(f"pid {pid} port {port}" for pid, port in others))
            print("stop it first (python tools/llm_server.py stop --profile <name>)")
            return 2
        ok = lc.start_server(wait_seconds=180)
        print("ready" if ok else "failed to start (see logs / model path)")
        return 0 if ok else 1

    lc.stop_server(any_owner=True)
    print("stopped" if not lc.is_available(timeout=3) else "still responding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
