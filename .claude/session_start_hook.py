import json, os, sys, subprocess

root = os.getcwd()
ss = os.path.join(root, 'SESSION_STATE.md')
recall = os.path.join(root, '.recall', 'history.md')
capn_script = os.path.join(root, 'scripts', 'capn.py')
lines = []

if os.path.exists(ss):
    with open(ss, encoding='utf-8') as f:
        lines.append('=== SESSION_STATE.md ===')
        lines.append(f.read().strip())
else:
    lines.append('WARNING: SESSION_STATE.md not found - no prior session handoff.')

if os.path.exists(recall):
    lines.append('=== RECALL: active and logging to .recall/history.md ===')
else:
    lines.append('WARNING: .recall/history.md not found - recall may not be running.')

if os.path.exists(capn_script):
    try:
        result = subprocess.run(
            ['python', capn_script, 'context'],
            capture_output=True, text=True, timeout=5, cwd=root
        )
        if result.stdout.strip():
            lines.append(result.stdout.strip())
    except Exception:
        pass  # capn context is best-effort; never block session start

out = {
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': '\n'.join(lines)
    }
}
print(json.dumps(out))
