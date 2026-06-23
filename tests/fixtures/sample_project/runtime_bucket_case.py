# tools/analysis/tests/fixtures/sample_project/runtime_bucket_case.py
#
# Fixture for test_runtime_bindings_wiring.py (TRACKER.md item 23).
# `ai = engine.ai_system` is a runtime attribute-chain binding; calling
# the bound name directly (`ai()`) must classify as bucket="runtime"
# once parse_ast() actually wires the bindings it computes through to
# FileAnalysis.runtime_bindings.


class Engine:
    def __init__(self):
        self.ai_system = None


def use_ai(engine):
    ai = engine.ai_system
    ai()
