// Determined plugin for opencode (v2 plugin API).
//
// Three jobs, all thin; the logic lives in Determined itself, not here:
//   1. Guards   - run this repo's existing PreToolUse hook scripts (the same files
//                 Claude Code runs) over the raw shell command and block on exit 2.
//   2. Brief    - before each user prompt, run work_session_primer against the corpus
//                 and add the result to the system context, so the model reasons over
//                 Determined's ranked next-work cards instead of exploring.
//   3. Tool     - determined_query: call any Determined tool without shell-quoting JSON
//                 through Windows PowerShell 5.1 (which strips inner double quotes).
//
// Environment:
//   DETERMINED_CORPUS_DB  corpus DB for the brief and the tool default
//                         (default: <repo>/C_Users_bartl_dev_dj2.db if present)
//   DETERMINED_BRIEF=0    disable the brief
//
// Parity with Claude Code is documented in docs/AGENT_PARITY.md and checked by
// tools/check_agent_parity.py.
import { Plugin } from "@opencode/plugin"
import { execFile, spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"
import { promisify } from "node:util"

const execFileP = promisify(execFile)

const MAX_TOOL_OUTPUT = 12000
const BRIEF_ITEMS = 3
const BRIEF_MAX_CHARS = 3500
// Written through opencode's own edit tool (which has permissions), not through here.
const DENIED_TOOLS = new Set(["edit_file"])

export default Plugin.define({
  id: "determined",
  async setup(ctx: any) {
    const dir: string = ctx.location.directory
    const venvPy = join(dir, ".venv", "Scripts", "python.exe")
    const py = existsSync(venvPy) ? venvPy : "python"
    const queryPy = join(dir, "tools", "query.py")
    const hasDetermined = existsSync(queryPy)

    const defaultDb = (() => {
      const env = process.env.DETERMINED_CORPUS_DB
      if (env) return env
      const dj2 = join(dir, "C_Users_bartl_dev_dj2.db")
      return existsSync(dj2) ? dj2 : undefined
    })()

    // ---- 1. guards -------------------------------------------------------
    const guardScripts = [
      join(dir, ".claude", "hooks", "validate_shell.py"),
      join(homedir(), ".claude", "hooks", "check_venv_python.py"),
    ].filter((p) => existsSync(p))

    const runGuards = (command: string): string | null => {
      for (const script of guardScripts) {
        try {
          const payload = JSON.stringify({
            tool_name: "PowerShell",
            tool_input: { command },
            cwd: dir,
          })
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
      const why = runGuards(String(event.input?.command ?? ""))
      if (why) throw new Error(why)
    })

    // ---- 2. brief --------------------------------------------------------
    const query = async (tool: string, args: Record<string, unknown>, db?: string, signal?: AbortSignal) => {
      const argv = [queryPy]
      if (db) argv.push("--db", db)
      argv.push(tool, JSON.stringify(args ?? {}))
      const { stdout } = await execFileP(py, argv, {
        cwd: dir,
        timeout: 120000,
        maxBuffer: 8 * 1024 * 1024,
        windowsHide: true,
        signal,
      })
      return String(stdout)
    }

    let brief = ""
    const refreshBrief = async () => {
      if (!hasDetermined || !defaultDb || process.env.DETERMINED_BRIEF === "0") return
      try {
        let out = await query("work_session_primer", { top_n: BRIEF_ITEMS }, defaultDb)
        if (out.length > BRIEF_MAX_CHARS) out = out.slice(0, BRIEF_MAX_CHARS) + "\n...[truncated]"
        brief =
          "## Determined: next work items (from work_session_primer; refreshed each user prompt)\n" +
          "Use the determined_query tool for readiness_check and completion_contract on a card " +
          "before implementing it.\n\n" +
          out.trim()
      } catch {
        // Keep the previous brief; never fail a prompt because the brief could not refresh.
      }
    }

    await ctx.session.hook("prompt", async () => {
      await refreshBrief()
    })
    await ctx.session.hook("context", (event: any) => {
      if (brief) event.system.push({ type: "text", text: brief })
    })

    // ---- 3. tool + command ----------------------------------------------
    await ctx.tool.transform((editor: any) => {
      if (!hasDetermined) return
      editor.namespace({
        name: "determined",
        description: "Determined code-analysis tools over a corpus DB",
      })
      editor.add({
        name: "query",
        description:
          "Run a Determined tool and return its output. Examples: work_session_primer, " +
          "readiness_check {symbol}, completion_contract {symbol}, implementation_order, " +
          "list_stubs, blast_radius {target}, list_callers {symbol}, describe_tool {name}. " +
          "Call with tool='describe_tool' and args {name:'<tool>'} for any tool's arguments.",
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
        options: { namespace: "determined", codemode: false },
        execute: async (input: any, context: any) => {
          const tool = String(input.tool ?? "")
          if (!/^[a-z_][a-z0-9_]*$/.test(tool)) return { content: `Invalid tool name: ${tool}` }
          if (DENIED_TOOLS.has(tool)) {
            return { content: `${tool} is not available here; use the edit tool instead.` }
          }
          try {
            let out = await query(tool, input.args ?? {}, input.db ?? defaultDb, context?.signal)
            if (out.length > MAX_TOOL_OUTPUT) {
              out = out.slice(0, MAX_TOOL_OUTPUT) + `\n...[truncated ${out.length - MAX_TOOL_OUTPUT} chars]`
            }
            return { content: out }
          } catch (err: any) {
            return { content: `determined_query failed: ${String(err?.message ?? err).slice(0, 800)}` }
          }
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
