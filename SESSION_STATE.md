Written at commit: f1ceb59

# SESSION STATE -- opencode wiring, llm profiles, primer bundle awareness

Arc file missing (no session_arc.md was kept this session); reconstructed from
git log and re-verification. Tags: [V] confirmed by a command this run, [?] recalled.

Last agent: Claude Code (desktop app). Next agent may be opencode (see Next steps).

## STATE [V]

- Branch: main at f1ceb59, PUSHED to origin/main (b8dc661..f1ceb59, no force); the repo
  is public. This file's own commit follows and is pushed with it.
- Other branch: dj2-state-machines-openspec (merged into main at 7600131; local and
  origin copies can be deleted). backup-before-sanitize (local, 4bca915) is the
  pre-rewrite main; delete it once you are satisfied.
- Working tree clean except untracked memory/reference_autosaddler.md (user file).
- Regression: all ten groups pass at f1ceb59's tree (206, 203, 136, 181, 136, 112, 310,
  48, 131, 81; 93 s total, no server left behind). --slow run of
  test_intent_layer_ab.py: 28 passed in 431 s, server stopped at session end.
- Parity check: `AGENT PARITY: ok`.
- Model server for opencode (agent profile, port 8083) is running at time of writing [V].
  Stop with `.venv\Scripts\python tools\llm_server.py stop --profile agent`.

## WHAT HAPPENED (main, oldest first)

 5f849a9 llm_client: named server profiles (analysis 8081, agent 8083), port-scoped
         orphan kill, tools/llm_server.py, determined.cfg rewritten
 aff1aae context_compactor removed (only Determined used it)
 1e4ace7 analysis profile text-only (no mmproj); HISTORY pointer fixed
 2c56608 opencode wiring: .opencode/plugins/determined, opencode.json, AGENTS.md,
         docs/AGENT_PARITY.md + agent_parity.json, tools/check_agent_parity.py
 89f9efd plugin tools determined_tests / determined_git / determined_python,
         shell redirect, bash/sh/wsl block in validate_shell.py
 7600131 merge of dj2-state-machines-openspec (session 314 handoff work, 19 commits)
 306208a design_oracle test fixture gains class_name; test mapped to agent_tools
 f34791e primer aware of verified handoff bundles (determined/agent/handoff_bundles.py)
 1da59ea docs: lessons recorded (registry, AGENT_PARITY, HISTORY, TRACKER RM74-RM79)
 ead23c4 llm_client autostart seam (DETERMINED_LLM_AUTOSTART), conftest makes tests
         hermetic by default, session teardown, 15 s unreachable memory
 028c7ba docs: autostart trap, fix and follow-ups (HISTORY, TRACKER RM80)
 ba95804 SESSION_STATE for the above (rewritten hash of the former 4bca915)
 a7f5933 docs: commit references refreshed after the unpushed-history cleanup
 f1ceb59 guarded pushes: tools/pre_push_check.py, determined_git push, rule updated

 Before the push, 11 unpushed commits were rewritten to drop mentions of an unrelated
 private project (a commit message, a HISTORY line, a SESSION_STATE line, a tracker
 item). The 19 openspec commits and the signed commit are byte-identical.

## LIVE IN THE CODE NOW [V]

- Profiles: `DETERMINED_LLM_PROFILE` env > determined.cfg `[llm] profile` > analysis.
  Public llm_client API unchanged. One profile's server fits in 8 GB VRAM at a time.
- Autostart: `DETERMINED_LLM_AUTOSTART` env > `[llm] autostart` > true. Off = generate()/
  chat() never start a server (None instead). tests/regression/conftest.py turns it off
  for every test not marked slow/live_llm and not using warmup_llm, and stops a server
  the session launched. The plugin runs Determined children with it off.
- opencode (v2.0.29) in the Determined folder: plugin gives guards (the repo's own hook
  scripts, honoring exit 2 and {"decision":"block"}), a per-prompt work_session_primer
  brief, tools determined_query/tests/git/python, `/next`. Default model
  local/qwen36-35b at 127.0.0.1:8083.
- Pushing: `tools/pre_push_check.py` (fast-forward, secret shapes, DB/binary/large files,
  private terms from ~/.determined/private_terms.txt which is outside the repo).
  `determined_git push` runs it first and never forces; CLAUDE.md says the same for
  Claude Code. The check scans exactly the outgoing range.
- Primer: fully covered items move to "Already handed off"; partial ones show
  "changes N/M ... not changed by the bundle". Bundle state via
  `git apply --reverse --check` in project_root.
- Verified live with the real 35B through opencode (headless and background-service
  mode): brief, determined_query, both guards, redirect, tool-first on 8 prompts.

## DECISIONS PINNED

- AGENTS.md is a thin pointer to CLAUDE.md (single source). opencode v2.0.29 did not
  auto-load CLAUDE.md in testing.
- Redirects to opencode-only tools live in the plugin, not in validate_shell.py.
- Only bundles with MANIFEST verified_at are read by the primer.
- fast_ctx/quality_ctx in determined.cfg left as-is on purpose (RM76).
- Push is allowed after `tools/pre_push_check.py` is clear (public repo; never force).
  Private project names stay out of commits and docs. dj2 repo changes need Bart's
  authorization.

## FAILED APPROACHES / SURPRISES (details in docs/HISTORY.md)

- v1 opencode docs (first search hits) do not match v2.0.29.
- Permission hook sees pieces of a compound shell command; use tool.execute.before.
- A first plugin honored only exit 2 and let check_venv_python through.
- Harness reset --hard did not undo a commit and contaminated a measurement.

## NOT VERIFIED [?]

- opencode desktop GUI itself has not been clicked through (permission dialogs untested).
- 8B model against the tool-first prompt set.
- Long sessions / dj2-scale tasks on the local model; quality vs Claude on real work.

## KNOWN TRAPS

Carried forward from session 314:
- Cytoscape containers need position:relative;overflow:hidden. [V s290]
- llm_client.chat() reasoning_content fallback removed -- don't re-add it. [V s290]
- Editor sym list: exact path equality in DB query, not LIKE basename. [V s291]
- Call tree: filter callees/callers whose name contains \n. [V s291]
- pytest -m on CLI REPLACES addopts -- never pass -m by hand. [V]
- Old corpus DBs may lack http_route/is_tool/is_stub columns -- handle gracefully. [V s293]
- FSM stubs have 0 static callers (string dispatch) -- not low priority. [V s295]
- New tools in TOOLS dict: add AFTER the function def, not inside the literal. [V s299]
- git commit messages: PowerShell @'...'@ here-strings fail on em-dashes/smart quotes. [V]
- Stale corpus DB produces phantom stubs. Re-ingest before trusting stub list. [V s301]
- DB paths: query with forward slashes. [V s303]
- test_dispatch_all_tools_registered: update expected set when adding tools. [V s310]
- reingest_file only handles Python via parse_ast; call_arg_count fixed s313. [V s313]
- class_name JOIN needed for class-qualified callees; pre-s313 DBs have NULL. [V s313]
- python-statemachine 3.x: callbacks get positional args only. [V s314]
- handoff.py writes patches with newline="\n" (CRLF breaks git apply). [V s314]
- handoff.py verify: direct apply, then --3way; base_sha may be an ancestor. [V s314]
- check_fsm_consistency handles 'from' as string or list. [V s314]

New this session:
- Guard hooks scan command TEXT: a literal "&&", bare `python`, or "rm -rf *" inside a
  commit message or prompt string is blocked. Put such text in a file (git commit -F). [V]
- FIXED ead23c4: non-slow tests reaching llm_client.generate() used to lazily start the
  8B (172 s, leaked). Still true outside tests: the UI and ad-hoc scripts autostart.
  A test header saying "no LLM needed" is not evidence; check what generate()/chat()
  are reachable from. Live tests need slow/live_llm marks or warmup_llm. [V]
- A refused connection costs 2-4 s on this Windows box (localhost 4 s, 127.0.0.1 2 s);
  with autostart off the client remembers a miss for 15 s. [V]
- Windows PowerShell 5.1: Start-Process -ArgumentList joins args with spaces and drops
  inner double quotes; opencode run treats a prompt word starting with "-" as a flag. [V]
- opencode shell tool is PS 5.1; `bash` is the WSL launcher, not Git Bash. [V]
- design_oracle's context lookup raises on pre-s313 DBs (RM75). [V]
- The repo is PUBLIC (github.com/bartanderson/Determined). Do not name private projects
  in commits, docs or code; a later cleanup commit does not remove text from history.
  The pre-push check enforces this from ~/.determined/private_terms.txt. [V]
- `git filter-branch` re-creates every commit it processes WITHOUT its signature, which
  changes the hash of that commit and all descendants (this nearly rewrote 19 commits that
  were already on the remote). To rewrite only what must change use a --commit-filter that
  echoes $GIT_COMMIT for unchanged commits whose parents are unchanged, and keep a backup
  branch first. Rewrite only commits that are not yet pushed. [V]
- A secret scanner scans its own tests: build secret-shaped fixtures at runtime
  (string concatenation), do not add allowlists. [V]
- Windows PowerShell 5.1 wraps git's stderr progress in a red NativeCommandError even
  when the exit code is 0; check $LASTEXITCODE. [V]

## RESOURCE / PROCESS RULES

- Test runner: tools/run_tests.py only; never pytest directly, never the full suite.
- Tool access: tools/query.py, or determined_query under opencode.
- High-blast-radius files (>= 500 edges) need full regression: agent_tools.py,
  ui_server.py, language_walker.py, graph_explorer.py, local_agent.py, parse_ast.py.
  agent_tools.py changed this session; groups run (see STATE).

---

## CARRIED FROM THE SESSION 314 HANDOFF

Full old text: `git show 8707451:SESSION_STATE.md`. Still live elsewhere:

- dj2 tests not run: Postgres-dependent files (30, classified in
  handoffs/dj2/BASELINE.md). dj2's tests/test_trade_fsm.py imports
  world.fsm.trade_machine, which does not exist at base_sha; left broken and flagged in
  handoffs/dj2/004-trade-fsm/rationale.md.
- Deferred finding: buy.json [BuyFSM] and sell.json [SellFSM] declare guards: {} and
  actions: {} yet reference price_too_low, store_offer, execute_purchase, execute_sell
  (ten unresolved references). A follow-up change, outside bundles 001-005 (TRACKER RM79).
- Bundle status and apply order: handoffs/dj2/STATE.md is the live record; the primer
  shows "pending apply" per covered item.
- The pre-existing G3 failure from that handoff is fixed (306208a).

## NEXT STEPS

First commands (any agent):

    git log --oneline -5
    .venv\Scripts\python tools\check_agent_parity.py

To try opencode on real work:

1. Nothing to start: the plugin starts the agent server on the first prompt (1-2 min cold)
   and stops it after 30 idle minutes if it started it. Manual:
   `.venv\Scripts\python tools\llm_server.py start --profile agent`.
2. Open C:\Users\bartl\dev\Determined in opencode desktop on branch main, model
   local/qwen36-35b, run `/next`. The brief will list the dj2 cards with bundle coverage.
3. Report friction (permission dialogs, tool choice) -- it feeds RM78.

Before any push: `.venv\Scripts\python tools\pre_push_check.py` (or `determined_git`
action `push`). Create/keep `~/.determined/private_terms.txt` with the private names.

Open items are in docs/TRACKER.md RM74-RM80 (RM80 = LLM lifecycle follow-ups: flip lazy
start per entry point, in-process mock server fixture, route Determined's calls to the
agent server under opencode). Suggested order:

- RM79 dj2 close-out: apply bundles 001-005 on a dj2 branch (Bart authorizes), record
  the SHA in handoffs/dj2/STATE.md, `reingest_changed`, confirm primer cards close.
- RM74 primer: do not count FSM handlers that already exist as functions.
- RM75 guard design_oracle against pre-s313 DBs.
- buy.json / sell.json follow-up change (ten unresolved references) via
  handoffs/dj2/WORKFLOW.md -- first real task for the local model.
- Pre-existing: docs/UI_REDESIGN.md Phase B/C is the main work driver per CLAUDE.md;
  untouched this session.
