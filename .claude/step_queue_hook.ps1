# PreToolUse hook: inject step queue context before any edit or UI action.
# If .claude/step_queue.md is missing, block so Claude is forced to create it first.

$queueFile = ".claude/step_queue.md"

if (Test-Path $queueFile) {
    $content = Get-Content $queueFile -Raw
    $context = "STEP QUEUE - check CURRENT before acting. If your action does not serve CURRENT, stop.`n`n$content"
    $out = @{
        hookSpecificOutput = @{
            hookEventName     = "PreToolUse"
            additionalContext = $context
        }
    } | ConvertTo-Json -Compress -Depth 5
    Write-Output $out
} else {
    $out = @{
        continue   = $false
        stopReason = "BLOCKED: .claude/step_queue.md is missing. Create it at .claude/step_queue.md with three lines: PREVIOUS: <what just completed>, CURRENT: <the one thing you are doing now>, NEXT: <what comes after>. Then retry."
    } | ConvertTo-Json -Compress
    Write-Output $out
}
