# why bash integration: observe shell lifecycle without wrapping commands.
# Source this file from ~/.bashrc, or use: eval "$(why init bash)"

# Bash has one DEBUG trap and one PROMPT_COMMAND hook. We chain any existing
# DEBUG trap and prepend our prompt hook so existing shell customizations keep
# receiving the user's original exit status.
if [[ "${_WHY_BASH_HOOK_INSTALLED:-0}" != "1" ]]; then
    _WHY_BASH_HOOK_BUSY=1

    _WHY_BASH_PREVIOUS_DEBUG_TRAP="$(trap -p DEBUG)"
    _WHY_BASH_PREVIOUS_DEBUG_COMMAND=""
    if [[ -n "$_WHY_BASH_PREVIOUS_DEBUG_TRAP" ]]; then
        _WHY_BASH_PREVIOUS_DEBUG_ASSIGNMENT="${_WHY_BASH_PREVIOUS_DEBUG_TRAP#trap -- }"
        _WHY_BASH_PREVIOUS_DEBUG_ASSIGNMENT="${_WHY_BASH_PREVIOUS_DEBUG_ASSIGNMENT% DEBUG}"
        eval "_WHY_BASH_PREVIOUS_DEBUG_COMMAND=$_WHY_BASH_PREVIOUS_DEBUG_ASSIGNMENT"
    fi

    if [[ -z "${WHY_SESSION_ID:-}" || "${WHY_SESSION_PID:-}" != "$$" ]]; then
        export WHY_SESSION_ID="$(uuidgen 2>/dev/null || date +%s)-$$-${RANDOM}"
        export WHY_SESSION_PID="$$"
    fi

    _WHY_BASH_PENDING_EVENT_ID=""
    _WHY_BASH_PENDING_COMMAND=""

    _why_bash_history_command() {
        local history_line history_number history_command
        history_line="$(builtin history 1)"
        read -r history_number history_command <<< "$history_line"
        printf '%s' "$history_command"
    }

    _why_bash_debug() {
        local command="${1:-}"
        local previous_status="${2:-0}"
        [[ "${_WHY_BASH_HOOK_BUSY:-0}" == "1" ]] && return 0

        case "$command" in
            why|why\ *|_why_bash_*) return 0 ;;
        esac

        # DEBUG fires before each simple command. history(1) gives us the
        # complete interactive input line, which avoids splitting `&&`, `||`,
        # pipelines, and semicolon-separated commands into separate events.
        _WHY_BASH_HOOK_BUSY=1
        local history_command
        history_command="$(_why_bash_history_command)"
        _WHY_BASH_HOOK_BUSY=0
        command="${history_command:-$command}"
        [[ "$command" == "$_WHY_BASH_PENDING_COMMAND" ]] && return 0

        # Finish the previous input line with its status, then begin this one.
        if [[ -n "${_WHY_BASH_PENDING_EVENT_ID:-}" ]]; then
            _WHY_BASH_HOOK_BUSY=1
            WHY_INTERNAL=1 command why internal end \
                --event-id "$_WHY_BASH_PENDING_EVENT_ID" \
                --exit-code "$previous_status" \
                --cwd "$PWD" >/dev/null 2>&1 || true
            _WHY_BASH_PENDING_EVENT_ID=""
            _WHY_BASH_PENDING_COMMAND=""
            _WHY_BASH_HOOK_BUSY=0
        fi

        _WHY_BASH_HOOK_BUSY=1
        _WHY_BASH_PENDING_EVENT_ID="$(WHY_INTERNAL=1 command why internal begin \
            --command "$command" \
            --cwd "$PWD" 2>/dev/null)" || _WHY_BASH_PENDING_EVENT_ID=""
        _WHY_BASH_PENDING_COMMAND="$command"
        _WHY_BASH_HOOK_BUSY=0
        return 0
    }

    _why_bash_debug_dispatch() {
        local previous_status=$?
        local command="${1:-}"
        if [[ -n "${_WHY_BASH_PREVIOUS_DEBUG_COMMAND:-}" ]]; then
            _WHY_BASH_HOOK_BUSY=1
            eval "$_WHY_BASH_PREVIOUS_DEBUG_COMMAND"
            _WHY_BASH_HOOK_BUSY=0
        fi
        _why_bash_debug "$command" "$previous_status"
    }

    _why_bash_precmd() {
        local previous_status=$?
        if [[ "${_WHY_BASH_HOOK_BUSY:-0}" == "1" ]]; then
            return "$previous_status"
        fi

        if [[ -n "${_WHY_BASH_PENDING_EVENT_ID:-}" ]]; then
            _WHY_BASH_HOOK_BUSY=1
            WHY_INTERNAL=1 command why internal end \
                --event-id "$_WHY_BASH_PENDING_EVENT_ID" \
                --exit-code "$previous_status" \
                --cwd "$PWD" >/dev/null 2>&1 || true
            _WHY_BASH_PENDING_EVENT_ID=""
            _WHY_BASH_PENDING_COMMAND=""
            _WHY_BASH_HOOK_BUSY=0
        fi

        # Preserve the command status for the next PROMPT_COMMAND entry and
        # for PS1/prompt themes.
        return "$previous_status"
    }

    trap '_why_bash_debug_dispatch "$BASH_COMMAND"' DEBUG

    if [[ "$(declare -p PROMPT_COMMAND 2>/dev/null)" == "declare -a"* ]]; then
        PROMPT_COMMAND=("_why_bash_precmd" "${PROMPT_COMMAND[@]}")
    elif [[ -n "${PROMPT_COMMAND:-}" ]]; then
        PROMPT_COMMAND="_why_bash_precmd;${PROMPT_COMMAND}"
    else
        PROMPT_COMMAND="_why_bash_precmd"
    fi

    _WHY_BASH_HOOK_INSTALLED=1
    WHY_INTERNAL=1 command why internal session \
        --session-id "$WHY_SESSION_ID" >/dev/null 2>&1 || true
    _WHY_BASH_HOOK_BUSY=0
fi
