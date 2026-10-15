"""tools/check_agent_parity.py: the live repo is in parity, and drift is detected.

Drift cases run against a throwaway copy of the handful of files the check reads.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

import determined.agent.llm_client  # noqa: F401  (cached so the check never imports a tmp copy)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_agent_parity as cap  # noqa: E402

_FILES = [
    "docs/agent_parity.json",
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/settings.json",
    ".claude/hooks/validate_shell.py",
    ".opencode/plugins/determined/index.ts",
    "opencode.json",
]


@pytest.fixture
def tree(tmp_path):
    for rel in _FILES:
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)
    return tmp_path


def test_live_repo_is_in_parity():
    assert cap.check(ROOT) == []


def test_copy_of_live_files_is_in_parity(tree):
    assert cap.check(tree) == []


def test_missing_agents_md_is_drift(tree):
    (tree / "AGENTS.md").unlink()
    assert any("AGENTS.md" in p for p in cap.check(tree))


def test_agents_md_must_point_at_claude_md(tree):
    (tree / "AGENTS.md").write_text("# nothing useful\n", encoding="utf-8")
    assert any("does not point at CLAUDE.md" in p for p in cap.check(tree))


def test_unlisted_hook_script_is_drift(tree):
    p = tree / ".claude" / "settings.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    s["hooks"]["PreToolUse"].append({
        "matcher": "Write",
        "hooks": [{"type": "command", "command": "python3 scripts/new_guard.py"}],
    })
    p.write_text(json.dumps(s), encoding="utf-8")
    problems = cap.check(tree)
    assert any("scripts/new_guard.py" in x and "not in" in x for x in problems)


def test_manifest_entry_without_wiring_is_drift(tree):
    p = tree / "docs" / "agent_parity.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m["claude_only"].append({"script": "scripts/ghost.py", "why": "x"})
    p.write_text(json.dumps(m), encoding="utf-8")
    assert any("ghost.py" in x and "not wired" in x for x in cap.check(tree))


def test_provider_port_mismatch_is_drift(tree):
    p = tree / "opencode.json"
    oc = json.loads(p.read_text(encoding="utf-8"))
    oc["providers"]["local"]["settings"]["baseURL"] = "http://127.0.0.1:9999/v1"
    p.write_text(json.dumps(oc), encoding="utf-8")
    assert any("9999" in x or "port" in x for x in cap.check(tree))


def test_plugin_must_reference_shared_guard(tree):
    p = tree / ".opencode" / "plugins" / "determined" / "index.ts"
    p.write_text("export default {}\n", encoding="utf-8")
    assert any("validate_shell.py" in x for x in cap.check(tree))
