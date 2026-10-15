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
//
// Environment:
//   DETERMINED_CORPUS_DB  corpus DB for the brief and determined_query default
//                         (default: <repo>/C_Users_bartl_dev_dj2.db if present)
//   DETERMINED_BRIEF=0    disable the brief
//   DETERMINED_REDIRECT=0 disable the shell-to-tool redirect
//
// Parity with Claude Code: docs/AGENT_PARITY.md, checked by tools/check_agent_parity.py.
import { Plugin } from "@opencode/plugin"
import { execFile, spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import { homedir, tmpdir } from "node:os"
import { join, resolve, sep } from "node:path"

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
    re: /(?:^|[;|&(]\s*)(?:&\s*)?git(?:\.exe)?\s+(?:commit|add|push)\b/i,
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

    await ctx.tool.hook("execute.before", (event: any) => {
      if (event.tool !== "shell") return
      const command = String(event.input?.command ?? "")
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
      try {
        await refreshBrief()
      } catch {
        // never fail a prompt because the brief could not refresh
      }
    })
    await ctx.session.hook("context", (event: any) => {
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
          "branch | add | commit | push. add needs paths; commit needs message (multi-line fine). " +
          "push runs tools/pre_push_check.py first (this repo is public: secrets, DB/binary/large " +
          "files, private terms, fast-forward) and pushes the current branch to origin only if it " +
          "is clear; it never forces. No reset, checkout, clean or amend: those stay with the user.",
        input: {
          type: "object",
          properties: {
            action: {
              type: "string",
              enum: ["status", "diff", "log", "branch", "add", "commit", "push"],
            },
            paths: { type: "array", items: { type: "string" } },
            message: { type: "string", description: "Commit message (for commit)" },
            staged: { type: "boolean", description: "diff: show staged changes" },
            stat: { type: "boolean", description: "diff: summary only" },
            n: { type: "number", description: "log: number of commits (default 10, max 50)" },
          },
          required: ["action"],
          additionalProperties: false,
        },
        execute: async (input: any) => {
          const paths: string[] = input.paths ?? []
          if (!isStringArray(paths) || paths.some((p) => p.startsWith("-"))) {
            return text("paths must be an array of paths not starting with '-'.")
          }
          if (input.action === "push") {
            const cur = spawnSync("git", ["branch", "--show-current"], {
              cwd: dir,
              encoding: "utf8",
              windowsHide: true,
            })
            const branch = String(cur.stdout ?? "").trim()
            if (!branch) return text("push needs a checked-out branch (detached HEAD).")
            // Same check a person runs by hand; no flags can bypass it from here.
            const chk = await runProc(py, [prePushPy, "--branch", branch])
            if (chk.code !== 0) {
              return text(cap(`NOT PUSHED. pre-push check exit ${chk.code}\n${chk.out}`))
            }
            const pushed = spawnSync("git", ["push", "origin", branch], {
              cwd: dir,
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
            cwd: dir,
            input: stdin,
            encoding: "utf8",
            timeout: 60000,
            windowsHide: true,
          })
          return text(cap(`exit ${r.status}\n${r.stdout ?? ""}${r.stderr ? "\n[stderr]\n" + r.stderr : ""}`))
        },
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
              "Follow the SESSION START CHECKLIST in CLAUDE.md, then take the first work item in " +
              "the Determined brief: run readiness_check and completion_contract on it with " +
              "determined_query, state a short plan with a verify step, and begin.\n\n" +
              (prompt?.text ?? ""),
            delivery,
          })
        },
      })
    })
  },
})
