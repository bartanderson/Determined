"""validate_shell.py: the PreToolUse guard shared by Claude Code and opencode."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks" / "validate_shell.py"
AMP = "&" * 2


def run(tool: str, command: str):
    payload = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
    r = subprocess.run([sys.executable, str(SCRIPT)], input=payload,
                       capture_output=True, text=True, timeout=10)
    reason = ""
    if r.stdout.strip():
        reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    return r.returncode, reason


@pytest.mark.parametrize("command", [
    "echo a " + AMP + " echo b",
    "cat x > /dev/null",
    "export FOO=bar",
    "bash -c 'ls'",
    "wsl ls /mnt/c",
    "sh script.sh",
    "git status; bash",
    "Get-Content x | sh",
    "& bash.exe -lc whoami",
])
def test_powershell_commands_that_must_block(command):
    code, reason = run("PowerShell", command)
    assert code == 2
    assert reason.startswith("[validate_shell]")


@pytest.mark.parametrize("command", [
    "echo a; echo b",
    "git status",
    "git log --oneline -3",
    r".venv\Scripts\python.exe tools\run_tests.py",
    "Get-ChildItem | Select-Object -First 3",
    "ssh-keygen -l -f key",     # starts with 'ssh', not 'sh'
    "Get-Content bash_history.txt",
    "echo 'run bash later'",
])
def test_powershell_commands_that_must_pass(command):
    code, _ = run("PowerShell", command)
    assert code == 0


def test_bash_tool_windows_path_blocks():
    code, reason = run("Bash", r"ls C:\Users\bartl")
    assert code == 2 and "Windows backslash path" in reason


def test_empty_command_passes():
    assert run("PowerShell", "")[0] == 0
