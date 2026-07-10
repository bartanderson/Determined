---
name: feedback-test-targeting
description: Run only test files related to changed code — not full suite as a step gate
metadata:
  type: feedback
---

Run targeted test files, not the full regression suite, as the step-by-step gate.

**Why:** Full suite takes 6 minutes and tests things that cannot have been affected by the change. This wastes time regardless of how fast individual tests are.

**How to apply:** After changing code in module X, run only `pytest tests/regression/test_X.py` (plus test_agent_tools.py if TOOLS or registry changed). Run full suite only as an occasional sanity check or before a major commit that touches many files. Even then, prefer targeted runs.
