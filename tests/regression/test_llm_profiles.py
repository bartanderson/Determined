"""llm_client server profiles: selection, request shaping, and port-scoped kill.

No server is started and nothing is killed: process listing and subprocess.run are
patched. Profile selection is exercised by reloading the module under a patched env.
"""
from __future__ import annotations

import importlib

import pytest

from determined.agent import llm_client


@pytest.fixture
def lc(monkeypatch):
    """Reload llm_client under a controlled environment; restore it afterwards."""
    def _load(profile: str | None):
        if profile is None:
            monkeypatch.delenv("DETERMINED_LLM_PROFILE", raising=False)
        else:
            monkeypatch.setenv("DETERMINED_LLM_PROFILE", profile)
        return importlib.reload(llm_client)

    yield _load
    monkeypatch.delenv("DETERMINED_LLM_PROFILE", raising=False)
    importlib.reload(llm_client)


def test_default_profile_is_analysis_on_8081(lc):
    m = lc(None)
    assert m.LLM_PROFILE in ("analysis", "agent")  # cfg may pin; env unset here
    m = lc("analysis")
    assert m.LLM_PROFILE == "analysis"
    assert m.LLM_PORT == 8081
    assert m.LLM_BASE_URL == "http://localhost:8081"
    assert "--mmproj" not in m.LLM_SERVER_ARGS  # text-only; vision is not used here
    assert "--jinja" not in m.LLM_SERVER_ARGS


def test_agent_profile_uses_own_port_and_jinja(lc):
    m = lc("agent")
    assert m.LLM_PROFILE == "agent"
    assert m.LLM_PORT == 8083
    assert m.LLM_BASE_URL == "http://localhost:8083"
    assert "--jinja" in m.LLM_SERVER_ARGS
    assert "--mmproj" not in m.LLM_SERVER_ARGS
    assert m.LLM_SERVER_ARGS[:4] == ["--port", "8083", "--host", "127.0.0.1"]


def test_unknown_profile_falls_back_to_analysis(lc):
    m = lc("no-such-profile")
    assert m.LLM_PROFILE == "analysis"
    assert m.LLM_PORT == 8081


def test_profiles_never_share_a_port(lc):
    m = lc("analysis")
    ports = [p["port"] for p in m._PROFILES.values()]
    assert len(ports) == len(set(ports))


@pytest.mark.parametrize("cmd,port", [
    (r"C:\x\llama-server.exe -m a.gguf --port 8083 --host 127.0.0.1", 8083),
    (r"llama-server.exe --port=8081", 8081),
    (r"llama-server.exe -m a.gguf", None),
    ("", None),
    (None, None),
])
def test_parse_port(cmd, port):
    assert llm_client._parse_port(cmd) == port


def _capture_chat(monkeypatch, m):
    sent = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def _post(url, json=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return _Resp()

    monkeypatch.setattr(m, "_ensure_server", lambda: None)
    monkeypatch.setattr(m.requests, "post", _post)
    assert m.chat([{"role": "user", "content": "hi"}]) == "ok"
    return sent


def test_analysis_chat_prepends_no_think(lc, monkeypatch):
    m = lc("analysis")
    sent = _capture_chat(monkeypatch, m)
    assert sent["url"] == "http://localhost:8081/v1/chat/completions"
    assert sent["json"]["messages"][0] == {"role": "system", "content": "/no_think"}
    assert "chat_template_kwargs" not in sent["json"]


def test_agent_chat_uses_template_kwarg_not_prefix(lc, monkeypatch):
    m = lc("agent")
    sent = _capture_chat(monkeypatch, m)
    assert sent["url"] == "http://localhost:8083/v1/chat/completions"
    assert sent["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert sent["json"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_kill_touches_only_matching_port(lc, monkeypatch):
    m = lc("analysis")
    killed = []
    monkeypatch.setattr(m, "_llama_servers", lambda: [
        (100, r"llama-server.exe -m a --port 8081"),   # ours port, not spared -> kill
        (200, r"llama-server.exe -m b --port 8083"),   # other profile -> keep
        (300, ""),                                     # unreadable cmdline -> keep
        (400, r"llama-server.exe -m c --port 8081"),   # ours port but spared -> keep
    ])
    monkeypatch.setattr(m.subprocess, "run",
                        lambda cmd, **kw: killed.append(cmd) or None)
    m._kill_servers_on_port(8081, spare_pid=400)
    assert killed == [["taskkill", "/F", "/PID", "100"]]


def test_kill_swallows_listing_errors(lc, monkeypatch):
    m = lc("analysis")

    def _boom():
        raise RuntimeError("powershell unavailable")

    monkeypatch.setattr(m, "_llama_servers", _boom)
    m._kill_servers_on_port(8081)  # must not raise


@pytest.mark.parametrize("raw,expected", [
    ("0", False), ("false", False), ("No", False), ("off", False), ("", False),
    ("1", True), ("true", True), ("yes", True),
])
def test_autostart_env_parsing(monkeypatch, raw, expected):
    from determined.config import get_llm_autostart
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", raw)
    assert get_llm_autostart() is expected


def test_autostart_env_beats_default(monkeypatch):
    from determined import config
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")
    assert config.get_llm_autostart(default=True) is False
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "1")
    assert config.get_llm_autostart(default=False) is True


def test_unmarked_tests_run_with_autostart_disabled():
    """conftest's autouse fixture makes every non-live test hermetic."""
    from determined.config import get_llm_autostart
    assert get_llm_autostart() is False


def test_ensure_server_starts_only_when_autostart_on(lc, monkeypatch):
    m = lc("analysis")
    started = []
    monkeypatch.setattr(m, "is_available", lambda timeout=5: False)
    monkeypatch.setattr(m, "start_server", lambda *a, **k: started.append(1) or True)

    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")
    m._ensure_server()
    assert started == []

    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "1")
    m._ensure_server()
    assert started == [1]


def test_generate_fails_fast_without_starting_when_autostart_off(lc, monkeypatch):
    m = lc("analysis")
    started = []
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")
    monkeypatch.setattr(m, "is_available", lambda timeout=5: False)
    monkeypatch.setattr(m, "start_server", lambda *a, **k: started.append(1) or True)

    def _refused(*a, **k):
        raise m.requests.ConnectionError("connection refused")

    monkeypatch.setattr(m.requests, "post", _refused)
    assert m.generate("hi") is None
    assert m.chat([{"role": "user", "content": "hi"}]) is None
    assert started == []


def _counting_post(m, monkeypatch):
    posts = []

    def _refused(*a, **k):
        posts.append(1)
        raise m.requests.ConnectionError("connection refused")

    monkeypatch.setattr(m.requests, "post", _refused)
    return posts


def test_unreachable_server_is_remembered_when_autostart_off(lc, monkeypatch):
    m = lc("analysis")
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")
    monkeypatch.setattr(m, "is_available", lambda timeout=5: False)
    posts = _counting_post(m, monkeypatch)
    assert m.generate("a") is None
    assert m.chat([{"role": "user", "content": "b"}]) is None
    assert m.generate("c") is None
    assert posts == [1]                    # one real attempt, then fast-fail


def test_unreachable_memory_expires(lc, monkeypatch):
    m = lc("analysis")
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")
    monkeypatch.setattr(m, "is_available", lambda timeout=5: False)
    posts = _counting_post(m, monkeypatch)
    m.generate("a")
    m._unreachable_until = 0.0             # simulate the TTL elapsing
    m.generate("b")
    assert posts == [1, 1]


def test_no_memory_when_autostart_on(lc, monkeypatch):
    m = lc("analysis")
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "1")
    monkeypatch.setattr(m, "is_available", lambda timeout=5: True)   # skip any start
    posts = _counting_post(m, monkeypatch)
    m.generate("a")
    m.generate("b")
    assert posts == [1, 1]                 # transient failures are retried, not cached


def test_warmup_is_not_fast_failed(lc, monkeypatch):
    m = lc("analysis")
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")
    monkeypatch.setattr(m, "is_available", lambda timeout=5: False)
    m._unreachable_until = m.time.monotonic() + 1000      # a stale "down" note
    calls = []

    def _gen(prompt, timeout=0, max_tokens=0):
        calls.append(prompt)
        return "pong"

    monkeypatch.setattr(m, "generate", _gen)
    assert m.warmup(wait_seconds=5) is True
    assert calls == ["ping"]
    assert m._unreachable_until == 0.0


def test_explicit_start_server_ignores_autostart_flag(lc, monkeypatch):
    m = lc("analysis")
    monkeypatch.setenv("DETERMINED_LLM_AUTOSTART", "0")
    monkeypatch.setattr(m, "is_available", lambda timeout=5: True)
    assert m.start_server() is True      # already reachable; no process involved


def test_stop_server_any_owner_only_when_asked(lc, monkeypatch):
    m = lc("agent")
    calls = []
    monkeypatch.setattr(m, "_kill_servers_on_port", lambda port, spare_pid=None: calls.append(port))
    m._server_proc = None
    m.stop_server()
    assert calls == []
    m.stop_server(any_owner=True)
    assert calls == [8083]
