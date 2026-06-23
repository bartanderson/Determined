# pipeline_guard.py

def assert_no_failure_modes(symbols: list[str]):
    from determined.context.failure_modes import FAILURE_PATTERNS

    for s in symbols:
        if s in FAILURE_PATTERNS:
            raise RuntimeError(f"Pipeline failure mode detected: {s}")