#!/bin/sh
# Entry point of the guard hook. hooks.json blocks the tool call when this hook fails, and Claude Code
# cannot tell an agent session from any other, so a failure must be sorted out here: python3 missing,
# crashing or hanging may only block a session that is using the agent. Exit 2 denies, 0 allows.
input=$(cat)
script="$(dirname "$0")/ofa_guard_hook.py"

if [ -f "$script" ]; then
    if command -v timeout >/dev/null 2>&1; then
        printf '%s' "$input" | timeout 8 python3 "$script"
    else
        printf '%s' "$input" | python3 "$script"
    fi
    status=$?
    if [ "$status" -eq 0 ] || [ "$status" -eq 2 ]; then
        exit "$status"
    fi
fi

deny() {
    echo "ofa guard: the guard could not run, denying" >&2
    exit 2
}

session_id=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([A-Za-z0-9_-]*\)".*/\1/p' | head -n 1)
if [ -n "$session_id" ] && [ -e "$CLAUDE_PLUGIN_DATA/active_sessions/$session_id" ]; then
    deny
fi
if printf '%s' "$input" | grep -Eq 'odoo-functional-agent:|(^|[^[:alnum:]_.-])ofa([^[:alnum:]_.-]|$)'; then
    deny
fi
if printf '%s' "$input" | grep -q '"hook_event_name"[[:space:]]*:[[:space:]]*"UserPromptSubmit"' \
    && printf '%s' "$input" | grep -Eiq 'target[[:space:]]*:[[:space:]]*[^[:space:]]'; then
    deny
fi
exit 0
