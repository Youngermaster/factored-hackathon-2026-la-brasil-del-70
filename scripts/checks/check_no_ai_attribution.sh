#!/usr/bin/env bash
# Fail if any commit in the given range carries AI tool attribution or an AI author identity.
#
# Usage:
#   scripts/checks/check_no_ai_attribution.sh              # every commit reachable from HEAD
#   scripts/checks/check_no_ai_attribution.sh main..HEAD   # a specific range
set -euo pipefail

range="${1:-HEAD}"

message_pattern='co-authored-by:.*(claude|anthropic|copilot|chatgpt|openai|gemini|cursor)|generated (with|by) \[?(claude|claude code|an ai|ai)\]?|claude\.(ai|com)/(code|claude-code)'
identity_pattern='anthropic\.com|noreply@anthropic|(^|[^a-z])claude([^a-z]|$)'

tip="${range##*..}"
if ! git rev-parse --verify --quiet "${tip}^{commit}" >/dev/null; then
  echo "check-no-ai-attribution: no commits to check for range '${range}'"
  exit 0
fi

status=0
while read -r sha; do
  body="$(git log -1 --format=%B "${sha}")"
  if grep -Eiq "${message_pattern}" <<<"${body}"; then
    echo "check-no-ai-attribution: ${sha:0:12} has attribution text in its message" >&2
    grep -Ei "${message_pattern}" <<<"${body}" | sed 's/^/    /' >&2
    status=1
  fi
  identity="$(git log -1 --format='%an <%ae> | %cn <%ce>' "${sha}")"
  if grep -Eiq "${identity_pattern}" <<<"${identity}"; then
    echo "check-no-ai-attribution: ${sha:0:12} has an AI author or committer identity: ${identity}" >&2
    status=1
  fi
done < <(git rev-list "${range}")

if [[ "${status}" -eq 0 ]]; then
  echo "check-no-ai-attribution: clean for range '${range}'"
fi
exit "${status}"
