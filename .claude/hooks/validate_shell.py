"""
PreToolUse hook: catch Bash-isms in PowerShell commands and Windows paths in Bash commands.
Exits 2 (blocks the tool call) when a violation is found.
"""
import json
import re
import sys

raw = sys.stdin.buffer.read().decode("utf-8-sig")
data = json.loads(raw)
tool_name = data.get("tool_name", "")
command = data.get("tool_input", {}).get("command", "")

if not command:
    sys.exit(0)

if tool_name == "PowerShell":
    checks = [
        (r"<<\s*['\"]?\w*",      "Bash heredoc (<<) — use PowerShell @'...'@ here-string instead"),
        (r"/dev/null",            "/dev/null is Unix-only — use $null in PowerShell (e.g. 2>$null)"),
        (r"\bexport\s+\w+=",     "export VAR= is Bash syntax — use $env:VAR = 'value' in PowerShell"),
        (r"\s&&\s",               "&& chaining is Bash syntax — use '; if ($?) { cmd2 }' in PowerShell"),
    ]
    for pattern, message in checks:
        if re.search(pattern, command):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"[validate_shell] Bash-ism in PowerShell command: {message}"
                }
            }))
            sys.exit(2)

elif tool_name == "Bash":
    if re.search(r"[A-Za-z]:\\", command):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "[validate_shell] Windows backslash path in Bash command — use forward-slash Unix paths or the PowerShell tool instead"
            }
        }))
        sys.exit(2)

sys.exit(0)
