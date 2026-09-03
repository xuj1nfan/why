# Development checkout entrypoint. Installed users should use:
#   eval "$(why init zsh)"
#
# Keep the implementation inside the Python package so installed wheels and
# editable checkouts use the same hook.
typeset _why_hook_dir="${${(%):-%N}:A:h}"
source "${_why_hook_dir:h}/src/why/why.zsh"
unset _why_hook_dir
