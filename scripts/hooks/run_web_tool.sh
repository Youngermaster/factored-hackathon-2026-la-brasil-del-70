#!/usr/bin/env bash
# Run a web tool (eslint or prettier) from apps/web on files that pre-commit passes as repository paths.
#
# Usage: scripts/hooks/run_web_tool.sh TOOL [TOOL_ARGS...] -- FILE...
# The apps/web/ prefix is stripped so the tool runs with the web app's own configuration and tsconfig.
set -euo pipefail

tool="$1"
shift
tool_args=()
while [[ $# -gt 0 && "$1" != "--" ]]; do
  tool_args+=("$1")
  shift
done
[[ $# -gt 0 ]] && shift

files=()
for path in "$@"; do
  files+=("${path#apps/web/}")
done
[[ ${#files[@]} -eq 0 ]] && exit 0

cd "$(dirname "$0")/../../apps/web"
exec pnpm exec "${tool}" "${tool_args[@]}" "${files[@]}"
