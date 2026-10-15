"""Check that the Claude Code and opencode setups for this repo have not drifted.

Reads docs/agent_parity.json (the manifest) and compares it with what is actually
wired: .claude/settings.json hooks, opencode.json, AGENTS.md, the opencode plugin,
and the llm_client "agent" server profile.

Usage:
    python tools/check_agent_parity.py          # exit 0 = in parity
    python tools/check_agent_parity.py --json   # machine-readable result

A problem line names the file to fix and what is missing. Add a hook script to the
manifest (shared_guards / claude_only / session_start) when you wire a new one.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "docs/agent_parity.json"
PLUGIN = ".opencode/plugins/determined/index.ts"
_SCRIPT_RE = re.compile(r"[\w./\\:~-]+\.py")


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _hook_scripts(settings: dict) -> set[str]:
    """Every .py path named in a hook command in .claude/settings.json."""
    found: set[str] = set()
    for entries in (settings.get("hooks") or {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                for m in _SCRIPT_RE.findall(hook.get("command", "")):
                    found.add(_norm(m))
    return found


def check(root: Path = ROOT) -> list[str]:
    """Return a list of problems; empty means in parity."""
    problems: list[str] = []

    mpath = root / MANIFEST
    if not mpath.exists():
        return [f"{MANIFEST}: manifest missing"]
    manifest = json.loads(mpath.read_text(encoding="utf-8"))

    # 1. Instructions: canonical file and the opencode entry that points at it.
    canonical = manifest["instructions"]["canonical"]
    entry = manifest["instructions"]["opencode_entry"]
    if not (root / canonical).exists():
        problems.append(f"{canonical}: canonical instructions file missing")
    entry_path = root / entry
    if not entry_path.exists():
        problems.append(f"{entry}: opencode entry file missing")
    elif canonical not in entry_path.read_text(encoding="utf-8"):
        problems.append(f"{entry}: does not point at {canonical}")

    # 2. Every wired Claude hook script is accounted for in the manifest.
    settings_path = root / ".claude" / "settings.json"
    if settings_path.exists():
        wired = _hook_scripts(json.loads(settings_path.read_text(encoding="utf-8")))
        known = set()
        for key in ("shared_guards", "claude_only", "session_start"):
            for item in manifest.get(key, []):
                known.add(_norm(item["script"]))
        for script in sorted(wired - known):
            problems.append(
                f".claude/settings.json: hook script {script} is wired but not in {MANIFEST}"
            )
        for script in sorted(known - wired):
            problems.append(
                f"{MANIFEST}: {script} is listed but not wired in .claude/settings.json"
            )

    # 3. Shared guards exist and the plugin actually runs them.
    plugin_path = root / PLUGIN
    plugin_src = plugin_path.read_text(encoding="utf-8") if plugin_path.exists() else ""
    if not plugin_src:
        problems.append(f"{PLUGIN}: opencode plugin missing")
    for guard in manifest.get("shared_guards", []) + manifest.get("user_level_guards", []):
        script = guard["script"]
        if not script.startswith("~") and not (root / script).exists():
            problems.append(f"{script}: shared guard script missing")
        if plugin_src and Path(script).name not in plugin_src:
            problems.append(f"{PLUGIN}: does not reference guard {Path(script).name}")

    # 4. opencode provider matches the llm_client agent profile (one source of truth).
    ms = manifest.get("model_server", {})
    oc_path = root / "opencode.json"
    if not oc_path.exists():
        problems.append("opencode.json: missing")
    else:
        oc = json.loads(oc_path.read_text(encoding="utf-8"))
        provider = (oc.get("providers") or {}).get(ms.get("opencode_provider", ""))
        if provider is None:
            problems.append(f"opencode.json: provider {ms.get('opencode_provider')!r} missing")
        else:
            sys.path.insert(0, str(root))
            try:
                from determined.agent import llm_client
                prof = llm_client._PROFILES[ms["profile"]]
                url = provider.get("settings", {}).get("baseURL", "")
                if f":{prof['port']}/" not in url + "/":
                    problems.append(
                        f"opencode.json: baseURL {url!r} does not use the "
                        f"{ms['profile']} profile port {prof['port']}"
                    )
                alias = ""
                args = prof["server_args"]
                if "--alias" in args:
                    alias = args[args.index("--alias") + 1]
                want = ms.get("opencode_model", "")
                if alias and not want.endswith("/" + alias):
                    problems.append(
                        f"{MANIFEST}: opencode_model {want!r} does not match "
                        f"server alias {alias!r}"
                    )
                if oc.get("model") and oc["model"] != want:
                    problems.append(f"opencode.json: model {oc['model']!r} != manifest {want!r}")
            except Exception as exc:  # import or lookup failure is itself drift
                problems.append(f"llm_client agent profile unreadable: {exc}")

    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    problems = check()
    if "--json" in args:
        print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
    elif problems:
        print("AGENT PARITY: DRIFT")
        for p in problems:
            print("  - " + p)
    else:
        print("AGENT PARITY: ok")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
