# why zsh integration: observe shell lifecycle without wrapping commands.
# Source this file from ~/.zshrc, or use: eval "$(why init zsh)"

autoload -Uz add-zsh-hook

# Exporting the session ID lets child processes use it, while the PID check
# ensures a newly spawned zsh does not accidentally inherit its parent's ID.
if [[ -z "${WHY_SESSION_ID:-}" || "${WHY_SESSION_PID:-}" != "$$" ]]; then
    export WHY_SESSION_ID="$(uuidgen 2>/dev/null || date +%s)-$$-${RANDOM}"
    export WHY_SESSION_PID="$$"
fi

WHY_EVENT_ID=""

_why_preexec() {
    local command="$1"
    [[ "${WHY_INTERNAL:-}" == "1" ]] && return 0
    [[ "$command" == "WHY_INTERNAL=1 "* ]] && return 0
    [[ "$command" == "why" || "$command" == "why "* ]] && return 0

    WHY_EVENT_ID="$(WHY_INTERNAL=1 command why internal begin \
        --command "$command" \
        --cwd "$PWD" 2>/dev/null)" || WHY_EVENT_ID=""
    return 0
}

_why_precmd() {
    local exit_code=$?
    if [[ "${WHY_INTERNAL:-}" == "1" ]]; then
        return "$exit_code"
    fi

    if [[ -n "${WHY_EVENT_ID:-}" ]]; then
        WHY_INTERNAL=1 command why internal end \
            --event-id "$WHY_EVENT_ID" \
            --exit-code "$exit_code" \
            --cwd "$PWD" >/dev/null 2>&1 || true
        WHY_EVENT_ID=""
    fi

    # Do not let the recorder's own command change the status seen by the
    # prompt/theme after the user's command completed.
    return "$exit_code"
}

# Re-sourcing .zshrc should not register duplicate hooks.
add-zsh-hook -d preexec _why_preexec 2>/dev/null
add-zsh-hook -d precmd _why_precmd 2>/dev/null
add-zsh-hook preexec _why_preexec
add-zsh-hook precmd _why_precmd

# Materialize the session at shell initialization, even before the first
# command. Failure is intentionally silent so why never breaks the shell.
WHY_INTERNAL=1 command why internal session \
    --session-id "$WHY_SESSION_ID" >/dev/null 2>&1 || true
