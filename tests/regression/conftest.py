"""
Shared fixtures for the regression suite.

LLM policy: tests are hermetic by default. llm_client.generate()/chat() would
otherwise start a llama-server on demand (a ~4.7 GB GPU process, 1-3 minutes, left
running afterwards). The autouse fixture below turns that autostart off for every test
that is not explicitly live. A test is live when it is marked slow / live_llm, or asks
for warmup_llm. Live tests start the server themselves; the session teardown stops any
server this process started.
"""

import pytest
from determined.agent.llm_client import warmup as _warmup, start_server


def _is_live(request) -> bool:
    node = request.node
    return (
        node.get_closest_marker("slow") is not None
        or node.get_closest_marker("live_llm") is not None
        or "warmup_llm" in request.fixturenames
    )


@pytest.fixture(autouse=True)
def _no_llm_autostart(request, monkeypatch):
    if not _is_live(request):
        monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")


@pytest.fixture(scope="session")
def warmup_llm():
    """For tests that call the LLM. Starts the server (or reuses a running one)."""
    if not start_server():
        pytest.skip("llama-server could not be started")
    ready = _warmup(wait_seconds=30)
    if not ready:
        pytest.skip("llama-server did not respond within 30s")


def pytest_sessionfinish(session, exitstatus):
    """Stop a server this process launched (no-op if it did not launch one)."""
    from determined.agent import llm_client
    llm_client.stop_server()
