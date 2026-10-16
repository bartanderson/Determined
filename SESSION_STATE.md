Written at commit: 5807d24

# SESSION STATE -- opencode desktop is the daily driver; Claude helps on request

Arc file missing (none kept); built from git log, TRACKER RM81 and checks run at write
time. Tags: [V] confirmed by a command this run, [?] recalled, not rechecked.

Last agent: Claude Code (desktop app). Day-to-day work now runs in opencode desktop
(local Qwen3.6-35B-A3B). Bart asks Claude for help only when needed.

## HOW TO START A CLAUDE SESSION HERE

Read this file and docs/TRACKER.md RM81, then do what Bart asks. Standing rule
(memory: feedback_use_the_tools_dont_bypass): when Bart is running the opencode flow,
do not do the real work from the Claude side and do not touch dj2 unasked. Observe,
fix the TOOL when it fails, say what changed, ask Bart to rerun.
Observation sources: plugin log `%TEMP%\determined-opencode.log`, opencode log
`%USERPROFILE%\.local\share\opencode\log\opencode.log`, `git -C <dj2>`.

## STATE [V]

- Determined main at 5807d24, pushed to origin (public repo). Working tree clean except
  untracked memory/reference_autosaddler.md (Bart's file). Parity check: AGENT PARITY: ok.
- dj2 (C:\Users\bartl\dev\dj2): main still 598ed55 (untouched). Branches
  feat/bundles-agent (agent-made, bundles 001-005 = 41c02db..0d4dc8f, currently checked
  out) and feat/handoff-bundles (earlier, d5a9b29); trees identical. Local only, nothing
  pushed. Awaits Bart's review/merge (RM79). Local backup-before-sanitize still exists.
- Regression groups were last run at f1ceb59 (all ten passed); not rerun after
  5807d24, which only touches the TypeScript plugin [?].

## FIRST REAL DESKTOP RUN (2026-10-16) [V]

The agent created feat/bundles-agent in dj2 and applied bundles 001-005 through
`determined_git apply_bundle`; Claude verified the commits against git afterwards.
- Tool defect found and fixed (5807d24): `switch` cut new branches from the checked-out
  branch, not main. Now main (else master), `base` optional; `repo` accepts "dj2".
- Desktop trap: the app reopens on the last project. If dj2 is the loaded project the
  server never reads Determined's opencode.json or the plugin: only catalog providers
  show, no local model, no guards. Open Determined as the project (opencode.log shows
  "location services booted ... Determined"), then start a new session.
- The Custom provider form is unavailable on this server; opencode.json is the source.
- New sessions did not default to the local model; select it once in the picker.

## NEXT STEPS (RM81, in the order they block unattended work)

1. dj2 test runner for the agent (determined_tests is Determined-only).
2. FSM re-ingest after changes (reingest_changed says "up to date"; ingested_at NULL).
3. One measured real task on a card that is not a bundle (steps, time, refusals).
4. Check whether the primer lists pending bundles on a clean dj2 main [?]; show dj2's
   own CLAUDE.md to the agent; /next assumes the dj2 corpus.
5. Desktop-only unknowns: idle auto-stop, compaction recovery, long first prompt.
First command for a fresh Claude session: `git log --oneline -5` then read RM81.

## LIVE IN THE CODE NOW [V at f1ceb59; plugin changes since in git log]

- Profiles: `DETERMINED_LLM_PROFILE` env > determined.cfg `[llm] profile` > analysis.
  One profile's server fits in 8 GB VRAM at a time (analysis 8081 VL-8B, agent 8083 35B).
- Autostart: `DETERMINED_LLM_AUTOSTART` env > `[llm] autostart` > true; conftest turns it
  off for tests not marked slow/live_llm.
- Plugin (.opencode/plugins/determined): guards, per-prompt primer brief, bounded reads,
  work-repo edit boundary (feature branch only), shell-write guard, tools
  determined_query/tests/git/python, `/next`, per-repo lock, model auto-start/idle stop.
- Pushing: tools/pre_push_check.py, `determined_git push`, never force.
- Bundles: tools/handoff.py apply (verified, feature branch, ordered, tests, parse check,
  commit, rollback); primer reads handoffs/<project>/ via project_meta.project_root.

## DECISIONS PINNED

- AGENTS.md is the opencode entry (CLAUDE.md is not auto-loaded by v2.0.29).
- dj2 is a work repo (determined.cfg [agent] work_repos): feature branch only, git via
  determined_git repo=, a person merges. Private project names stay out of the repo.
- fast_ctx/quality_ctx in determined.cfg left stale on purpose (RM76).

## FAILED APPROACHES / SURPRISES (details in docs/HISTORY.md)

- v1 opencode docs do not match v2.0.29; permission hook sees pieces of compound shell
  commands (block in tool.execute.before); a bundle can be "verified" yet unparseable
  (parse guard added); I applied bundles myself once and cost Bart the real run.

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
- opencode's local model has a 32k window; the CLAUDE.md checklist reads ~33k tokens
  (HISTORY.md alone ~18k). The first /next overflowed and compaction itself failed (a
  session in that state cannot recover; start a new one). Plugin now caps unbounded reads
  of files over 20 KB to ~8 KB with a "next part" note; AGENTS.md has a Context budget
  section. If a session still compacts, check what it read. [V]
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

## ALSO STILL OPEN

- Before any push: tools/pre_push_check.py (or determined_git push); keep ~/.determined/private_terms.txt.
- RM75 guard design_oracle against pre-s313 DBs; RM80 LLM lifecycle follow-ups; buy.json/sell.json
  follow-up change via handoffs/dj2/WORKFLOW.md (a good first non-bundle task for the local model).
- docs/UI_REDESIGN.md Phase B/C is the main work driver per CLAUDE.md; untouched in these sessions.
