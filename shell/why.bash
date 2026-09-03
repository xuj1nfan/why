# Development checkout entrypoint. Installed users should use:
#   eval "$(why init bash)"
#
# Keep the implementation inside the Python package so installed wheels and
# editable checkouts use the same hook.
_WHY_CHECKOUT_HOOK_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$_WHY_CHECKOUT_HOOK_DIR/../src/why/why.bash"
unset _WHY_CHECKOUT_HOOK_DIR
