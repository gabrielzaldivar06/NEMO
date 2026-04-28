$rawInput = ""
if ([Console]::IsInputRedirected) {
	$rawInput = [Console]::In.ReadToEnd()
}
$hookEvent = "Unknown"

if (-not [string]::IsNullOrWhiteSpace($rawInput)) {
	try {
		$payload = $rawInput | ConvertFrom-Json
		if ($payload.hookEventName) {
			$hookEvent = [string]$payload.hookEventName
		}
		elseif ($payload.hook_event_name) {
			$hookEvent = [string]$payload.hook_event_name
		}
	}
	catch {
		$hookEvent = "Unknown"
	}
}

$msg = @"
NEMO HOOK ACTIVE ($hookEvent).

Mandatory startup actions for every primary agent and subagent:
1. Call mcp_nemo_prime_context(topic='memory persistence') before answering or reading broadly.
2. Call mcp_nemo_get_current_time() immediately after prime_context.

Proactive Context Economy policy:
- For any non-trivial coding, debugging, research, review, planning, or resume task, call mcp_nemo_build_context_portfolio early with task=<current user task>, topic='memory persistence', and a tight token_budget before broad file reads/searches or launching subagents.
- Prefer the portfolio output over raw memory dumps. Expand only needed evidence with mcp_nemo_expand_context_evidence.
- When a large tool result, transcript, log, or artifact is needed later, compact it with mcp_nemo_compress_context_artifact and keep the evidence handle recoverable.
- When continuing from an existing portfolio or after relevant changes, call mcp_nemo_refresh_context_portfolio instead of rebuilding context manually.
- If portfolio entries or evidence were useful/not useful, call mcp_nemo_record_context_feedback so future agents rank context better.
- Do not use Context Economy for trivial greetings or one-line answers where no repository or memory context is needed.
"@

@{ systemMessage = $msg } | ConvertTo-Json -Compress

