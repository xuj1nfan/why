# why zsh integration: observe shell lifecycle without wrapping commands.
# Source this file from ~/.zshrc, or use: eval "$(why init zsh)"

autoload -Uz add-zsh-hook
zmodload zsh/datetime 2>/dev/null || true

# Exporting the session ID lets child processes use it, while the PID check
# ensures a newly spawned zsh does not accidentally inherit its parent's ID.
if [[ -z "${WHY_SESSION_ID:-}" || "${WHY_SESSION_PID:-}" != "$$" ]]; then
    export WHY_SESSION_ID="$(uuidgen 2>/dev/null || date +%s)-$$-${RANDOM}"
    export WHY_SESSION_PID="$$"
fi

WHY_EVENT_COMMAND=""
WHY_EVENT_CWD=""
WHY_EVENT_STARTED_AT=""
_WHY_RECORDER_PID=""

_why_wait_recorder() {
    if [[ -n "${_WHY_RECORDER_PID:-}" ]]; then
        wait "$_WHY_RECORDER_PID" 2>/dev/null || true
        _WHY_RECORDER_PID=""
    fi
}

_why_preexec() {
    local command="$1"
    [[ "${WHY_INTERNAL:-}" == "1" ]] && return 0
    [[ "$command" == "WHY_INTERNAL=1 "* ]] && return 0
    _why_wait_recorder
    [[ "$command" == "why" || "$command" == "why "* ]] && return 0

    WHY_EVENT_COMMAND="$command"
    WHY_EVENT_CWD="$PWD"
    WHY_EVENT_STARTED_AT="${EPOCHREALTIME:-$(date +%s)}"
    return 0
}

_why_precmd() {
    local exit_code=$?
    if [[ "${WHY_INTERNAL:-}" == "1" ]]; then
        return "$exit_code"
    fi

    if [[ -n "${WHY_EVENT_COMMAND:-}" ]]; then
        WHY_INTERNAL=1 command why internal record \
            --command "$WHY_EVENT_COMMAND" \
            --cwd-before "$WHY_EVENT_CWD" \
            --cwd-after "$PWD" \
            --started-at "$WHY_EVENT_STARTED_AT" \
            --exit-code "$exit_code" \
            >/dev/null 2>&1 &
        _WHY_RECORDER_PID=$!
        WHY_EVENT_COMMAND=""
        WHY_EVENT_CWD=""
        WHY_EVENT_STARTED_AT=""
    fi

    # Do not let the recorder's own command change the status seen by the
    # prompt/theme after the user's command completed.
    return "$exit_code"
}

_why_zshexit() {
    _why_wait_recorder
}

# Re-sourcing .zshrc should not register duplicate hooks.
add-zsh-hook -d preexec _why_preexec 2>/dev/null
add-zsh-hook -d precmd _why_precmd 2>/dev/null
add-zsh-hook -d zshexit _why_zshexit 2>/dev/null
add-zsh-hook preexec _why_preexec
add-zsh-hook precmd _why_precmd
add-zsh-hook zshexit _why_zshexit

# Materialize the session at shell initialization, even before the first
# command. Failure is intentionally silent so why never breaks the shell.
WHY_INTERNAL=1 command why internal session \
    --session-id "$WHY_SESSION_ID" >/dev/null 2>&1 || true
