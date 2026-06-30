"""
Session-scoped warmup fixture for tests that call the LLM.
GPU inference is fast (~2-5s); this just ensures the service is up before tests run.
Tests that don't touch the LLM should NOT list this fixture.
"""

import pytest
from determined.agent.llm_client import warmup as _warmup, is_available


@pytest.fixture(scope="session")
def warmup_llm():
    if not is_available(timeout=5):
        pytest.skip("llama-server not reachable")
    ready = _warmup(wait_seconds=30)
    if not ready:
        pytest.skip("llama-server reachable but model did not respond within 30s")
