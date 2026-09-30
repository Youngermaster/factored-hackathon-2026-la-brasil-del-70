#!/usr/bin/env bash
# Pre-submission check: runs every automated gate, then prints the steps only a person can do.
#
#   make submission-check            (or scripts/submission_check.sh from the repository root)
#
# Gates, in order: make check, make security, make eval-smoke, the slides' pnpm verify, make docs-check. Every gate
# runs even when an earlier one fails, so one run shows everything; the exit status is non-zero when any failed.
# It never deploys, pushes, sends anything, or reads .env. Checklist: docs/submission/SUBMISSION.md.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2

declare -a names=()
declare -a results=()

run_gate() {
  local name="$1"
  shift
  printf '\n==> %s: %s\n' "${name}" "$*"
  if "$@"; then
    results+=("pass")
  else
    results+=("FAIL")
  fi
  names+=("${name}")
}

# shellcheck disable=SC2329  # called through run_gate below
slides_verify() {
  if [[ ! -d slides/node_modules ]]; then
    printf 'slides/node_modules is missing: run (cd slides && pnpm install) first\n'
    return 1
  fi
  (cd slides && pnpm verify)
}

run_gate "make check" make check
run_gate "make security" make security
run_gate "make eval-smoke" make eval-smoke
run_gate "slides pnpm verify" slides_verify
run_gate "make docs-check" make docs-check

printf '\n== Gate results (commit %s)\n' "$(git rev-parse --short HEAD)"
failed=0
for index in "${!names[@]}"; do
  printf '%-22s %s\n' "${names[${index}]}" "${results[${index}]}"
  [[ "${results[${index}]}" == "pass" ]] || failed=1
done

printf '\n== Remaining human steps (docs/submission/SUBMISSION.md)\n'
if grep -Eq '^deploy\.url: \{status: pending' slides/data/metrics.yml; then
  printf -- '- deploy.url is still pending in slides/data/metrics.yml\n'
fi
if grep -q 'Pending: the host is being chosen' README.md; then
  printf -- '- the README still shows the deployed demo link as pending\n'
fi
cat <<'STEPS'
1. Choose the host and deploy (deploy/README.md), seed on a fresh volume, then from a laptop:
   make smoke SMOKE_URL=https://<host> and make csp-check SMOKE_URL=https://<host>
2. Fill deploy.url in slides/data/metrics.yml and the deployed link in README.md; commit.
3. Export the slides: cd slides && pnpm verify && pnpm check:fit (dev server running) && pnpm export:final
4. Record the video against the deployed URL right after a fresh seed (slides/VIDEO.md, docs/demo/script.md);
   upload it and put the link in README.md and the email.
5. Push main, then make the repository public; confirm its name is factored-hackathon-2026-la-brasil-del-70.
6. Send docs/submission/email-draft.md to hackathon.admin@factored.ai before 2026-10-05.
7. After 2026-10-16: deploy/prod.sh destroy --yes, then release the cloud resources.
STEPS

exit "${failed}"
