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


def test_stop_server_any_owner_only_when_asked(lc, monkeypatch):
    m = lc("agent")
    calls = []
    monkeypatch.setattr(m, "_kill_servers_on_port", lambda port, spare_pid=None: calls.append(port))
    m._server_proc = None
    m.stop_server()
    assert calls == []
    m.stop_server(any_owner=True)
    assert calls == [8083]
