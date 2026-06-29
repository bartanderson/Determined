# SESSION STATE - session 37 handoff
_Overwrite completely each session. Not authoritative - see docs/TRACKER.md for truth._

## What happened this session (session 37)

- Item 25 DONE: all Ollama call sites replaced with `determined/agent/llm_client.py` shim
  - `generate()` / `chat()` / `is_available()` pointing at llama-server localhost:8080
  - 8 files migrated: semantic_summary, agent_tools, stub_projector, doc_extractor,
    local_agent, pattern_executor, query_compiler, ui_server
  - PatternExecutor constructor args removed; test files updated
  - 323 tests pass, 1 pre-existing Windows file-handle flake unchanged
- dj2 TRACKER.md created with item 1 (Ollama removal from game code)

## Open items

See docs/TRACKER.md Dashboard. Items 21-24 (assistant arc) designed, not built.
Item 26 (uninstall Ollama, reclaim ~50GB) ready to do whenever Bart wants.

### Item 26 - Uninstall Ollama (ready to execute)
- Uninstall Ollama app from Windows
- Delete `C:\Users\bartl\.ollama\` (~50GB of blobs/models)
- GGUF already copied to `C:\Users\bartl\models\gguf\llama3.2-3b.gguf`
- llama-server.exe at `C:\Users\bartl\models\llama-server\llama-server.exe`
- No code depends on Ollama anymore

### Items 21-24 (assistant arc) - designed, not built
Start with item 23 (docstring health) - most concrete and self-contained.
Full wiring details in docs/TRACKER.md items 21-24.

## Infrastructure reminder
- llama-server binary: `C:\Users\bartl\models\llama-server\llama-server.exe`
- GGUF model: `C:\Users\bartl\models\gguf\llama3.2-3b.gguf`
- Start: `llama-server.exe -m C:\Users\bartl\models\gguf\llama3.2-3b.gguf --port 8080`
- Embedding: all-MiniLM-L6-v2 via sentence-transformers (no Ollama dependency)

## Two-terminal reminder
Determined: C:\Users\bartl\dev\Determined, venv at .venv\Scripts\python.exe
UI: python -m determined.agent.local_agent --ui then http://127.0.0.1:5050
Use PowerShell tool (not Bash) for all server/Python commands.
