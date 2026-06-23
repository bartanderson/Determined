# tools/analysis/tests/observability/rule_inspector.py

import json
from pathlib import Path


def load_system_rules():
    path = Path("tools/analysis/contracts/tool_system_contract.json")

    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def print_rules():
    rules = load_system_rules()

    print("\n=== SYSTEM RULES ===\n")

    for k, v in rules.items():
        print(f"{k}: {v}")