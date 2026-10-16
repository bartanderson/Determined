// Determined plugin for opencode (v2 plugin API).
//
// Thin by design; the logic lives in Determined and in this repo's hook scripts.
//   1. Guards   - run the repo's existing PreToolUse hook scripts (the same files Claude
//                 Code runs) over the raw shell command and block on a deny decision.
//   2. Redirect - when a shell command is one a structured tool covers, block it with a
//                 one-line pointer to that tool (Windows PowerShell 5.1 quoting makes the
//                 shell route fragile; the tools take arguments as data, no quoting).
//   3. Brief    - before each user prompt, run work_session_primer against the corpus and
//                 add it to the system context.
//   4. Tools    - determined_query, determined_tests, determined_git, determined_python.
//   0. Server   - starts the local agent model server on the first prompt (the model cannot
//                 start the server it runs on) and stops it after an idle period, if this
//                 plugin started it. Log: %TEMP%\determined-opencode.log
//
// Environment:
//   DETERMINED_CORPUS_DB  corpus DB for the brief and determined_query default
//                         (default: <repo>/C_Users_bartl_dev_dj2.db if present)
//   DETERMINED_BRIEF=0    disable the brief
//   DETERMINED_REDIRECT=0 disable the shell-to-tool redirect
//   DETERMINED_AGENT_AUTOSTART=0   do not start the model server automatically
//   DETERMINED_AGENT_IDLE_MIN=30   minutes idle before a server this plugin started is stopped
//
// Parity with Claude Code: docs/AGENT_PARITY.md, checked by tools/check_agent_parity.py.
import { Plugin } from "@opencode/plugin"
import { execFile, spawnSync } from "node:child_process"
import {
  appendFileSync,
  closeSync,
  existsSync,
  openSync,
  readdirSync,
  readFileSync,
  readSync,
  statSync,
} from "node:fs"
import { homedir, tmpdir } from "node:os"
import { basename, join, resolve, sep } from "node:path"

const MAX_OUTPUT = 12000
const BRIEF_ITEMS = 3
const BRIEF_MAX_CHARS = 3500
// Edited through opencode's own edit tool (which has permissions), not through here.
const DENIED_QUERY_TOOLS = new Set(["edit_file"])
const SAFE_NAME = /^[a-z_][a-z0-9_]*$/

// Shell commands a structured tool covers -> pointer. Matched on the raw command.
const REDIRECTS: { re: RegExp; msg: string }[] = [
  {
    re: /tools[\\/]run_tests\.py/i,
    msg:
      "Use the determined_tests tool instead of running run_tests.py in the shell. " +
      "Arguments: files (string[] of changed source files), full_files, slow, list (booleans).",
  },
  {
    re: /tools[\\/]query\.py/i,
    msg:
      "Use the determined_query tool instead of running query.py in the shell. " +
      "Arguments: tool (name), args (object), db (optional corpus DB path).",
  },
  {
    re: /(?:^|[;|&(]\s*)(?:&\s*)?git(?:\.exe)?\s+(?:-C\s+\S+\s+)?(?:commit|add|push|switch|checkout)\b/i,
    msg:
      "Use the determined_git tool for add, commit and push. Arguments: action ('add' with " +
      "paths string[], 'commit' with message, or 'push'). Messages are passed as data, so no " +
      "quoting; push runs the pre-push check first.",
  },
]

const cap = (s: string, n = MAX_OUTPUT) =>
  s.length > n ? s.slice(0, n) + `\n...[truncated ${s.length - n} chars]` : s

const isStringArray = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every((x) => typeof x === "string")

export default Plugin.define({
  id: "determined",
  async setup(ctx: any) {
    const dir: string = ctx.location.directory
    const venvPy = join(dir, ".venv", "Scripts", "python.exe")
    const py = existsSync(venvPy) ? venvPy : "python"
    const queryPy = join(dir, "tools", "query.py")
    const testsPy = join(dir, "tools", "run_tests.py")
    const prePushPy = join(dir, "tools", "pre_push_check.py")
    const handoffPy = join(dir, "tools", "handoff.py")
    const hasDetermined = existsSync(queryPy)

    const defaultDb = (() => {
      const env = process.env.DETERMINED_CORPUS_DB
      if (env) return env
      const dj2 = join(dir, "C_Users_bartl_dev_dj2.db")
      return existsSync(dj2) ? dj2 : undefined
    })()

    // Run a process with an argument array (never a shell string): nothing to quote.
    // Determined child processes never start a model server on their own
    // (DETERMINED_LLM_AUTOSTART=0): a tool call must not stall for minutes or take VRAM
    // from the agent's own server. Start one explicitly with tools/llm_server.py; the
    // slow-test option opts back in because those tests call a real model.
    const runProc = (
      file: string,
      argv: string[],
      signal?: AbortSignal,
      timeout = 120000,
      autostart = false,
    ) =>
      new Promise<{ code: number; out: string }>((done) => {
        const env = autostart ? process.env : { ...process.env, DETERMINED_LLM_AUTOSTART: "0" }
        execFile(
          file,
          argv,
          { cwd: dir, timeout, maxBuffer: 16 * 1024 * 1024, windowsHide: true, signal, env },
          (err, stdout, stderr) => {
            const code = err ? (typeof (err as any).code === "number" ? (err as any).code : 1) : 0
            let out = String(stdout ?? "")
            if (stderr) out += `\n[stderr]\n${stderr}`
            if (err && (err as any).killed) out += "\n[timed out or cancelled]"
            done({ code, out })
          },
        )
      })

    // ---- 0. the agent model server: start on demand, stop when idle -------
    // The model cannot start the server it runs on, so the plugin does it, before the
    // model call (the prompt hook below). Health is read from the provider URL in
    // opencode.json, which tools/check_agent_parity.py ties to the llm_client profile.
    // A server this plugin started is stopped after DETERMINED_AGENT_IDLE_MIN minutes
    // without activity (it holds ~17 GB of RAM); one you started yourself is never
    // stopped here. DETERMINED_AGENT_AUTOSTART=0 turns all of this off.
    const llmServerPy = join(dir, "tools", "llm_server.py")
    const logFile = join(tmpdir(), "determined-opencode.log")
    const log = (m: string) => {
      try {
        appendFileSync(logFile, `${new Date().toISOString()} ${m}\n`)
      } catch {
        // logging is best effort
      }
    }
    const agentHealthUrl = (() => {
      try {
        const cfg = JSON.parse(readFileSync(join(dir, "opencode.json"), "utf8"))
        const base: string = cfg?.providers?.local?.settings?.baseURL ?? "http://127.0.0.1:8083/v1"
        return base.replace(/\/v1\/?$/, "") + "/health"
      } catch {
        return "http://127.0.0.1:8083/health"
      }
    })()
    const autoAgent = process.env.DETERMINED_AGENT_AUTOSTART !== "0" && existsSync(llmServerPy)
    const idleMs = (Number(process.env.DETERMINED_AGENT_IDLE_MIN) || 30) * 60_000
    let startedByUs = false
    let lastActivity = Date.now()
    let starting: Promise<void> | null = null

    const healthy = async () => {
      try {
        const r = await fetch(agentHealthUrl, { signal: AbortSignal.timeout(2000) })
        return r.ok
      } catch {
        return false
      }
    }
    const ensureAgentServer = async () => {
      lastActivity = Date.now()
      if (!autoAgent || (await healthy())) return
      if (!starting) {
        starting = (async () => {
          log(`agent server not reachable at ${agentHealthUrl}; starting`)
          // --coexist: the analysis server may be running; both fit in 8 GB VRAM.
          const r = await runProc(
            py,
            [llmServerPy, "start", "--profile", "agent", "--coexist"],
            undefined,
            240000,
          )
          log(`start exit ${r.code}: ${r.out.trim().slice(-300)}`)
          if (r.code === 0) startedByUs = true
        })().finally(() => {
          starting = null
        })
      }
      await starting
    }
    const idleTimer = setInterval(async () => {
      if (!startedByUs || starting || Date.now() - lastActivity < idleMs) return
      startedByUs = false
      log(`idle for ${Math.round((Date.now() - lastActivity) / 60000)} min; stopping agent server`)
      const r = await runProc(py, [llmServerPy, "stop", "--profile", "agent"], undefined, 60000)
      log(`stop exit ${r.code}: ${r.out.trim().slice(-200)}`)
    }, 60_000)
    ;(idleTimer as any).unref?.()

    // ---- 1 + 2. guards and redirect -------------------------------------
    const guardScripts = [
      join(dir, ".claude", "hooks", "validate_shell.py"),
      join(homedir(), ".claude", "hooks", "check_venv_python.py"),
    ].filter((p) => existsSync(p))

    const runGuards = (command: string): string | null => {
      for (const script of guardScripts) {
        try {
          const payload = JSON.stringify({ tool_name: "PowerShell", tool_input: { command }, cwd: dir })
          const r = spawnSync(py, [script], {
            input: payload,
            encoding: "utf8",
            cwd: dir,
            timeout: 10000,
            windowsHide: true,
          })
          // Claude hooks block in two shapes: exit 2 with hookSpecificOutput.permissionDecision
          // "deny" (validate_shell.py), or exit 0 with {"decision": "block", "reason"}
          // (check_venv_python.py). Honor both.
          let parsed: any = null
          try {
            parsed = JSON.parse(r.stdout)
          } catch {
            // not JSON; exit code alone decides
          }
          const hso = parsed?.hookSpecificOutput
          const blocked =
            r.status === 2 ||
            parsed?.decision === "block" ||
            parsed?.decision === "deny" ||
            hso?.permissionDecision === "deny"
          if (blocked) {
            return (hso?.permissionDecisionReason ?? parsed?.reason ?? `Blocked by ${script}`) as string
          }
        } catch {
          // A guard that cannot run does not block (same contract as Claude hooks).
        }
      }
      return null
    }

    // ---- 2b. bounded reads -----------------------------------------------
    // The local model has a 32k-token context; a few unbounded reads of the large docs
    // (HISTORY.md alone is ~18k tokens) overflow it and force compaction. A read of a big
    // file with no explicit small limit is cut to about READ_CAP_BYTES, and the result says
    // how to get the rest. Structure over vigilance: this does not depend on the model
    // remembering an instruction.
    const READ_BIG_FILE = 20000
    const READ_CAP_BYTES = 8000
    const readNotes = new Map<string, string>()
    const capRead = (event: any) => {
      try {
        const p = String(event.input?.path ?? "")
        if (!p) return
        const full = resolve(dir, p)
        if (!existsSync(full)) return
        const st = statSync(full)
        if (!st.isFile() || st.size <= READ_BIG_FILE) return
        const lim = Number(event.input?.limit ?? 0)
        if (lim > 0 && lim <= 400) return // an explicit, small, ranged read: leave it
        const fd = openSync(full, "r")
        const buf = Buffer.alloc(Math.min(65536, st.size))
        const n = readSync(fd, buf, 0, buf.length, 0)
        closeSync(fd)
        const head = buf.subarray(0, n).toString("utf8")
        const headLines = Math.max(1, head.split("\n").length - 1)
        const avg = Math.max(20, n / headLines)
        const lines = Math.max(40, Math.floor(READ_CAP_BYTES / avg))
        event.input.limit = lines
        const start = Number(event.input?.offset ?? 1) || 1
        readNotes.set(
          String(event.id),
          `\n[determined plugin: ${p} is ${Math.round(st.size / 1024)} KB, about ` +
            `${Math.round(st.size / 4 / 1000)}k tokens; this read was cut to ${lines} lines from ` +
            `line ${start}. Read the next part with offset=${start + lines} and limit=${lines}, ` +
            `or use grep to find the part you need.]`,
        )
      } catch {
        // never block a read because the cap could not be computed
      }
    }

    await ctx.tool.hook("execute.after", (event: any) => {
      if (event.tool !== "read") return
      const note = readNotes.get(String(event.id))
      if (!note) return
      readNotes.delete(String(event.id))
      try {
        const parts = event.result?.content
        const part = Array.isArray(parts) ? parts.find((x: any) => typeof x?.text === "string") : null
        if (part) part.text += note
      } catch {
        // the note is a courtesy; the cap already did its job
      }
    })

    // ---- 2c. where edits may land -------------------------------------------
    // This repository, plus the work repositories listed in determined.cfg [agent]
    // work_repos (or env DETERMINED_WORK_REPOS, ';'-separated). The permission layer
    // only ASKS about paths outside the project and a click on allow is easy, so the
    // boundary is enforced here. In a work repo other than this one, writes are allowed
    // only on a feature branch, never main/master (the documented dj2 practice: a
    // person merges the branch).
    const repoRoot = resolve(dir)
    const workRepos: string[] = (() => {
      let raw = process.env.DETERMINED_WORK_REPOS
      if (raw === undefined) {
        try {
          const cfg = readFileSync(join(dir, "determined.cfg"), "utf8")
          const sec = cfg.split(/^\[/m).find((s) => s.startsWith("agent]"))
          raw = sec?.match(/^\s*work_repos\s*=\s*(.+)$/m)?.[1]?.trim() ?? ""
        } catch {
          raw = ""
        }
      }
      return String(raw)
        .split(/[;,]/)
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => resolve(s))
    })()
    const allowedRoots = [repoRoot, ...workRepos]
    // Serialize operations per repository (see the git tool).
    const repoLocks = new Map<string, Promise<unknown>>()
    const withRepoLock = <T,>(repo: string, fn: () => Promise<T>): Promise<T> => {
      const key = resolve(repo).toLowerCase()
      const prev = repoLocks.get(key) ?? Promise.resolve()
      const next = prev.catch(() => undefined).then(fn)
      repoLocks.set(key, next.catch(() => undefined))
      return next
    }
    const rootFor = (p: string): string | null => {
      const full = (resolve(repoRoot, p) + sep).toLowerCase()
      for (const r of allowedRoots) if (full.startsWith((r + sep).toLowerCase())) return r
      return null
    }
    const currentBranch = (root: string) =>
      String(
        spawnSync("git", ["-C", root, "branch", "--show-current"], {
          encoding: "utf8",
          windowsHide: true,
        }).stdout ?? "",
      ).trim()
    const protectedBranch = (b: string) => b === "" || b === "main" || b === "master"

    // The edit/write fence does not cover the shell, which can write anywhere (verified).
    // Best effort: a shell command that names a work repo while that repo is on a
    // protected branch must be read-only, judged by an allowlist of verbs. Anything not
    // on the list is refused, which errs toward asking the model to use edit/write or
    // determined_git (those carry the real rules). Writes via a feature branch pass.
    const SHELL_READONLY = new Set([
      "get-content", "gc", "cat", "type", "get-childitem", "gci", "ls", "dir", "select-string",
      "sls", "test-path", "get-item", "gi", "measure-object", "select-object", "where-object",
      "sort-object", "format-table", "format-list", "write-output", "echo", "get-location",
      "resolve-path", "split-path", "join-path", "get-filehash", "findstr", "head", "tail",
    ])
    const GIT_READONLY = new Set([
      "status", "diff", "log", "show", "branch", "rev-parse", "ls-files", "grep", "blame",
      "remote", "describe", "shortlog", "rev-list", "cat-file", "ls-tree", "stash",
    ])
    const shellIsReadOnly = (command: string): boolean => {
      // redirection writes; ignore the harmless forms
      const stripped = command.replace(/2>&1|\d?>\s*\$null/gi, "")
      if (/>/.test(stripped)) return false
      for (const seg of command.split(/;|\||&&|\r?\n/)) {
        const t = seg.trim().replace(/^[&(]\s*/, "")
        if (!t) continue
        const parts = t.split(/\s+/)
        const first = parts[0].replace(/^['"]|['"]$/g, "").toLowerCase()
        if (first === "git" || first === "git.exe") {
          let i = 1
          while (parts[i] === "-C" || parts[i]?.startsWith("--")) i += parts[i] === "-C" ? 2 : 1
          const sub = String(parts[i] ?? "").toLowerCase()
          if (sub === "stash" && !/\b(list|show)\b/i.test(t)) return false
          if (sub === "branch" && /\s(-d|-D|-m|-M|-c|-C|--delete|--move)\b/.test(t)) return false
          if (!GIT_READONLY.has(sub)) return false
        } else if (!SHELL_READONLY.has(first)) {
          return false
        }
      }
      return true
    }
    const namesRepo = (command: string, root: string): boolean => {
      const c = command.replace(/\\/g, "/").toLowerCase()
      const r = root.replace(/\\/g, "/").toLowerCase()
      if (c.includes(r)) return true
      const base = r.split("/").pop() ?? ""
      return base !== "" && new RegExp(`(^|[/'"\\s(])${base.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([/'"\\s)]|$)`).test(c)
    }

    await ctx.tool.hook("execute.before", (event: any) => {
      lastActivity = Date.now()
      if (event.tool === "edit" || event.tool === "write") {
        const p = String(event.input?.path ?? "")
        if (p) {
          const root = rootFor(p)
          if (!root) {
            throw new Error(
              `Refused: ${p} is outside the repositories this agent may edit ` +
                `(${allowedRoots.join(", ")}). Change determined.cfg [agent] work_repos to add one.`,
            )
          }
          if (root !== repoRoot) {
            const b = currentBranch(root)
            if (protectedBranch(b)) {
              throw new Error(
                `Refused: ${root} is on ${b || "a detached HEAD"}. Create a feature branch first ` +
                  `with determined_git (action 'switch', repo '${root}', branch 'feat/<name>'); ` +
                  "a person merges it.",
              )
            }
          }
        }
      }
      if (event.tool === "read") capRead(event)
      if (event.tool !== "shell") return
      const command = String(event.input?.command ?? "")
      for (const root of workRepos) {
        if (namesRepo(command, root) && protectedBranch(currentBranch(root)) && !shellIsReadOnly(command)) {
          throw new Error(
            `Refused: this shell command names ${root}, which is on ` +
              `${currentBranch(root) || "a detached HEAD"}, and is not a read-only command. ` +
              "Create a feature branch first (determined_git action 'switch', repo, branch " +
              "'feat/<name>'), then use the edit/write tools or determined_git. Reading is allowed.",
          )
        }
      }
      if (hasDetermined && process.env.DETERMINED_REDIRECT !== "0") {
        for (const r of REDIRECTS) if (r.re.test(command)) throw new Error(r.msg)
      }
      const why = runGuards(command)
      if (why) throw new Error(why)
    })

    // ---- 3. brief --------------------------------------------------------
    const query = (tool: string, args: Record<string, unknown>, db?: string, signal?: AbortSignal) => {
      const argv = [queryPy]
      if (db) argv.push("--db", db)
      argv.push(tool, JSON.stringify(args ?? {}))
      return runProc(py, argv, signal)
    }

    let brief = ""
    const refreshBrief = async () => {
      if (!hasDetermined || !defaultDb || process.env.DETERMINED_BRIEF === "0") return
      const r = await query("work_session_primer", { top_n: BRIEF_ITEMS }, defaultDb)
      if (r.code !== 0 || !r.out.trim()) return // keep the previous brief
      brief =
        "## Determined: next work items (from work_session_primer; refreshed each user prompt)\n" +
        "Use determined_query for readiness_check and completion_contract on a card " +
        "before implementing it.\n\n" +
        cap(r.out.trim(), BRIEF_MAX_CHARS)
    }

    await ctx.session.hook("prompt", async () => {
      // Runs before the model call: the model server must be up by the time it returns.
      try {
        await ensureAgentServer()
      } catch (err) {
        log(`ensureAgentServer failed: ${String(err)}`)
      }
      try {
        await refreshBrief()
      } catch {
        // never fail a prompt because the brief could not refresh
      }
    })
    await ctx.session.hook("context", (event: any) => {
      lastActivity = Date.now()
      if (brief) event.system.push({ type: "text", text: brief })
    })

    // ---- 4. tools --------------------------------------------------------
    const text = (content: string) => ({ content })

    await ctx.tool.transform((editor: any) => {
      if (!hasDetermined) return
      editor.namespace({
        name: "determined",
        description: "Determined analysis, tests and git, with arguments passed as data",
      })
      const base = { options: { namespace: "determined", codemode: false } }

      editor.add({
        ...base,
        name: "query",
        description:
          "Run a Determined tool and return its output. Examples: work_session_primer, " +
          "readiness_check {symbol}, completion_contract {symbol}, implementation_order, " +
          "list_stubs, blast_radius {target}, list_callers {symbol}. " +
          "tool='describe_tool' with args {name:'<tool>'} lists any tool's arguments.",
        input: {
          type: "object",
          properties: {
            tool: { type: "string", description: "Determined tool name" },
            args: { type: "object", description: "Tool arguments (JSON object); may be omitted" },
            db: { type: "string", description: "Corpus DB path; defaults to DETERMINED_CORPUS_DB" },
          },
          required: ["tool"],
          additionalProperties: false,
        },
        execute: async (input: any, c: any) => {
          const tool = String(input.tool ?? "")
          if (!SAFE_NAME.test(tool)) return text(`Invalid tool name: ${tool}`)
          if (DENIED_QUERY_TOOLS.has(tool)) {
            return text(`${tool} is not available here; use the edit tool instead.`)
          }
          const r = await query(tool, input.args ?? {}, input.db ?? defaultDb, c?.signal)
          return text(cap(r.out))
        },
      })

      editor.add({
        ...base,
        name: "tests",
        description:
          "Run the targeted test runner (tools/run_tests.py): it picks the minimum tests for " +
          "the changed files. Pass files to name source files explicitly (e.g. " +
          "['determined/agent/llm_client.py']). Never runs the whole suite. Returns exit code and output.",
        input: {
          type: "object",
          properties: {
            files: { type: "array", items: { type: "string" }, description: "Source files to look up" },
            full_files: { type: "boolean", description: "Run whole matching test files" },
            slow: { type: "boolean", description: "Include slow (live LLM) tests" },
            list: { type: "boolean", description: "Only list the selected tests" },
          },
          additionalProperties: false,
        },
        execute: async (input: any, c: any) => {
          const argv = [testsPy]
          if (input.files !== undefined) {
            if (!isStringArray(input.files) || input.files.some((f: string) => f.startsWith("-"))) {
              return text("files must be an array of paths not starting with '-'.")
            }
            if (input.files.length) argv.push("--files", ...input.files)
          }
          if (input.full_files) argv.push("--full-files")
          if (input.slow) argv.push("--slow")
          if (input.list) argv.push("--list")
          const r = await runProc(py, argv, c?.signal, 180000, Boolean(input.slow))
          return text(cap(`exit ${r.code}\n${r.out}`))
        },
      })

      editor.add({
        ...base,
        name: "git",
        description:
          "Git operations with arguments as data (no shell quoting). action: status | diff | log | " +
          "branch | switch | add | commit | push | apply_bundle. add needs paths; commit needs " +
          "message (multi-line fine); switch needs branch (creates it if it does not exist); " +
          "apply_bundle needs repo (a work repo) and bundle (3-digit id such as '004'): it " +
          "applies that verified handoff bundle on the current feature branch, in order, runs " +
          "its tests and commits, or changes nothing. Bundles are cumulative: apply them in " +
          "ascending id order, one call per bundle, and read each result before the next. " +
          "repo (optional otherwise) selects a " +
          "configured work repository such as dj2; default is this one. " +
          "In a work repo, edits need a feature branch, and push never sends main/master. " +
          "push runs tools/pre_push_check.py first (secrets, DB/binary/large files, private " +
          "terms, fast-forward) and never forces. No reset, clean or amend.",
        input: {
          type: "object",
          properties: {
            action: {
              type: "string",
              enum: ["status", "diff", "log", "branch", "switch", "add", "commit", "push", "apply_bundle"],
            },
            repo: { type: "string", description: "Work repository path; default this repository" },
            bundle: { type: "string", description: "apply_bundle: 3-digit bundle id, e.g. 004" },
            branch: { type: "string", description: "Branch name for switch (e.g. feat/trade-fsm)" },
            base: { type: "string", description: "switch: start point for a NEW branch (default main, else master)" },
            paths: { type: "array", items: { type: "string" } },
            message: { type: "string", description: "Commit message (for commit)" },
            staged: { type: "boolean", description: "diff: show staged changes" },
            stat: { type: "boolean", description: "diff: summary only" },
            n: { type: "number", description: "log: number of commits (default 10, max 50)" },
          },
          required: ["action"],
          additionalProperties: false,
        },
        // One git operation at a time per repository: a model may issue several tool calls
        // in one batch, and two writers on one working tree and index corrupt each other.
        execute: (input: any) => withRepoLock(String(input?.repo ?? repoRoot), async () => {
          const paths: string[] = input.paths ?? []
          if (!isStringArray(paths) || paths.some((p) => p.startsWith("-"))) {
            return text("paths must be an array of paths not starting with '-'.")
          }
          // Accept a bare work-repo name (dj2) as well as a full path.
          const wanted = input.repo ? String(input.repo) : ""
          const byName = allowedRoots.find((r) => basename(r).toLowerCase() === wanted.toLowerCase())
          const root = wanted ? (byName ?? resolve(wanted)) : repoRoot
          if (!allowedRoots.some((r) => r.toLowerCase() === root.toLowerCase())) {
            return text(
              `repo must be one of: ${allowedRoots.join(", ")} (determined.cfg [agent] work_repos).`,
            )
          }
          if (
            root !== repoRoot &&
            (input.action === "add" || input.action === "commit") &&
            protectedBranch(currentBranch(root))
          ) {
            return text(
              `${root} is on a protected branch. Create a feature branch first: ` +
                "determined_git action 'switch' with repo and branch 'feat/<name>'.",
            )
          }
          if (input.action === "apply_bundle") {
            if (root === repoRoot) {
              return text("apply_bundle targets a work repository: pass repo (for example dj2).")
            }
            const id = String(input.bundle ?? "").trim()
            if (!/^\d{3}$/.test(id)) return text("apply_bundle needs bundle: a 3-digit id such as '004'.")
            const projDir = join(repoRoot, "handoffs", basename(root))
            const match = existsSync(projDir)
              ? readdirSync(projDir).find((n) => n.startsWith(`${id}-`))
              : undefined
            if (!match) return text(`No bundle ${id} under handoffs/${basename(root)}.`)
            // The CLI enforces: verified, feature branch, clean tree, earlier bundles in,
            // tests pass, commit; any failure restores the repository.
            const r = await runProc(
              py,
              [handoffPy, "apply", "--bundle-dir", join(projDir, match), "--repo", root],
              undefined,
              900000,
            )
            return text(cap(`exit ${r.code}\n${r.out}`))
          }
          if (input.action === "push") {
            const branch = currentBranch(root)
            if (!branch) return text("push needs a checked-out branch (detached HEAD).")
            if (root !== repoRoot && protectedBranch(branch)) {
              return text(`NOT PUSHED. ${branch} in ${root} is not pushed from here; push a feature branch.`)
            }
            // Same check a person runs by hand; no flags can bypass it from here.
            const chk = await runProc(py, [prePushPy, "--repo", root, "--branch", branch])
            if (chk.code !== 0) {
              return text(cap(`NOT PUSHED. pre-push check exit ${chk.code}\n${chk.out}`))
            }
            const pushed = spawnSync("git", ["push", "origin", branch], {
              cwd: root,
              encoding: "utf8",
              timeout: 120000,
              windowsHide: true,
            })
            return text(
              cap(
                `${chk.out.trim()}\npush exit ${pushed.status}\n${pushed.stdout ?? ""}` +
                  `${pushed.stderr ? "\n[stderr]\n" + pushed.stderr : ""}`,
              ),
            )
          }
          let argv: string[]
          let stdin: string | undefined
          switch (input.action) {
            case "status":
              argv = ["status", "--short", "--branch"]
              break
            case "branch":
              argv = ["branch", "--show-current"]
              break
            case "switch": {
              const b = String(input.branch ?? "").trim()
              if (!/^[A-Za-z0-9._][A-Za-z0-9._/-]*$/.test(b) || b.includes("..")) {
                return text("switch needs a plain branch name such as feat/trade-fsm.")
              }
              const exists = spawnSync(
                "git",
                ["-C", root, "rev-parse", "--verify", "-q", `refs/heads/${b}`],
                { windowsHide: true },
              ).status === 0
              if (exists) {
                argv = ["switch", b]
                break
              }
              // A new branch starts from the repo's main line, not from whatever is checked out:
              // otherwise a leftover branch's commits ride along unnoticed.
              const refExists = (r: string) =>
                spawnSync("git", ["-C", root, "rev-parse", "--verify", "-q", `refs/heads/${r}`], {
                  windowsHide: true,
                }).status === 0
              const base = String(input.base ?? "").trim() || (refExists("main") ? "main" : refExists("master") ? "master" : "")
              if (base && (!/^[A-Za-z0-9._][A-Za-z0-9._/-]*$/.test(base) || base.includes("..") || !refExists(base))) {
                return text(`base '${base}' is not an existing local branch.`)
              }
              argv = base ? ["switch", "-c", b, base] : ["switch", "-c", b]
              break
            }
            case "diff":
              argv = ["diff", ...(input.staged ? ["--cached"] : []), ...(input.stat ? ["--stat"] : [])]
              if (paths.length) argv.push("--", ...paths)
              break
            case "log": {
              const n = Math.min(Math.max(Number(input.n ?? 10) || 10, 1), 50)
              argv = ["log", `-n${n}`, "--oneline"]
              if (paths.length) argv.push("--", ...paths)
              break
            }
            case "add":
              if (!paths.length) return text("add needs paths (an array of specific files).")
              argv = ["add", "--", ...paths]
              break
            case "commit": {
              const message = String(input.message ?? "").trim()
              if (!message) return text("commit needs a non-empty message.")
              argv = ["commit", "-F", "-"]
              stdin = message + "\n"
              break
            }
            default:
              return text(`Unknown action: ${input.action}`)
          }
          const r = spawnSync("git", argv, {
            cwd: root,
            input: stdin,
            encoding: "utf8",
            timeout: 60000,
            windowsHide: true,
          })
          return text(cap(`exit ${r.status}\n${r.stdout ?? ""}${r.stderr ? "\n[stderr]\n" + r.stderr : ""}`))
        }),
      })

      editor.add({
        ...base,
        name: "python",
        description:
          "Run a Python script with the repo's venv interpreter; args are passed as data, " +
          "not through a shell. script must be a file inside the repo or the temp directory.",
        input: {
          type: "object",
          properties: {
            script: { type: "string", description: "Path to a .py file" },
            args: { type: "array", items: { type: "string" } },
          },
          required: ["script"],
          additionalProperties: false,
        },
        execute: async (input: any, c: any) => {
          const script = resolve(dir, String(input.script ?? ""))
          const roots = [resolve(dir) + sep, resolve(tmpdir()) + sep]
          if (!script.toLowerCase().endsWith(".py") || !roots.some((r) => script.startsWith(r))) {
            return text("script must be a .py file inside the repo or the temp directory.")
          }
          if (!existsSync(script)) return text(`No such file: ${script}`)
          if (input.args !== undefined && !isStringArray(input.args)) {
            return text("args must be an array of strings.")
          }
          // 200 s: tools/llm_server.py start waits up to 180 s for the model to load.
          const r = await runProc(py, [script, ...(input.args ?? [])], c?.signal, 200000)
          return text(cap(`exit ${r.code}\n${r.out}`))
        },
      })
    })

    await ctx.command.transform((editor: any) => {
      editor.add({
        name: "next",
        description: "Pick the top Determined work item and start it per the checklist",
        execute: async ({ sessionID, prompt, delivery }: any) => {
          await ctx.session.prompt({
            ...prompt,
            sessionID,
            text:
              "Your context is 32k tokens, so follow the 'Context budget' section of AGENTS.md: " +
              "read CLAUDE.md and SESSION_STATE.md only; do not read TRACKER.md, HISTORY.md or " +
              "UI_REDESIGN.md whole (grep or ranged reads for a specific item). Then take the " +
              "first work item in the Determined brief: run readiness_check and " +
              "completion_contract on it with determined_query, state a short plan with a " +
              "verify step, and begin.\n\n" +
              (prompt?.text ?? ""),
            delivery,
          })
        },
      })
    })

    // Stop the idle timer if the plugin is unloaded. A server started here is left
    // running on unload on purpose: it may belong to another open session.
    return () => clearInterval(idleTimer)
  },
})
