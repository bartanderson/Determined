# Item 14 - Phase 2: Full LLM test

> **HISTORICAL** — Item 14 is closed (2026-06-27). This procedure was written against Ollama/llama3.2:3b and the harrow corpus. The current backend is llama-server with Qwen3-8B (port 8081), launched on demand by the UI. Kept for reference only; do not run as-is.

## Prerequisites
- Phase 1 passed (tools return data, no errors)
- llama-server-8b running (port 8081) with Qwen3-8B loaded
- harrow DB ingested

## Step 1: Ingest harrow (if not done)

```
cd C:\Users\bartl\dev\Determined
.venv\Scripts\python.exe determined\engine\run_engine.py C:\Users\bartl\dev\harrow
```

## Step 2: Run phase 1 tool sequence test

```
.venv\Scripts\python.exe tests\item14_phase1_pattern_tools.py
```

Review output before proceeding to LLM test.

## Step 3: Run agent with verbose output captured

```
.venv\Scripts\python.exe -m determined.agent.local_agent C_Users_bartl_dev_harrow.db --verbose 2>&1 | Tee-Object -FilePath tests\item14_run.log
```

## Step 4: Type these inputs at the agent prompt

```
orient
```
Wait for full response. Then:
```
understand world_gen
```
(or whatever symbol Phase 1 identified as most connected)

Then type `quit`.

## What to look for in item14_run.log

**Pattern detection:**
- `[pattern detected] orient_to_codebase` should appear
- `[pattern-executor]` lines should show each step firing

**Per-step:**
- Did all steps execute? Or did some return `(no data)`?
- Did the model interpretation (1-2 sentences per step) make sense given the result?
- Any hallucinated tool names or tool errors?

**Final synthesis:**
- Does the final answer reflect what the tools actually found?
- Is it useful as a cold-start orientation, or generic/wrong?

**Failure modes to flag:**
1. Pattern not detected - model free-forms instead
2. Steps fire but model ignores results in interpretation
3. Final synthesis contradicts or ignores step findings
4. Model hallucinates facts not in any tool result

## After the run

Share item14_run.log content and we judge together:
- Which steps worked
- Where it drifted (if anywhere)
- Whether the output would actually help a developer orient
