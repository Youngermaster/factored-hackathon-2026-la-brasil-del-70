#!/usr/bin/env bash
# Release or roll back the production stack ON the Azure VM (ADR 0038; deploy/README.md, "Continuous deployment on
# Azure"). The deploy workflow runs it as root through `az vm run-command invoke`: deploy/azure/run-on-vm.sh puts the
# settings below as `export` lines in front of a copy of this file. An administrator can run it on the VM the same way:
#
#   sudo DEPLOY_ACTION=rollback VM_CHECKOUT=/home/azureuser/bank-agent deploy/azure/vm-deploy.sh
#
# Settings (environment):
#   DEPLOY_ACTION    deploy (default) or rollback
#   VM_CHECKOUT      the repository checkout, owned by the operator account (passwordless sudo, docker group); every
#                    git and deploy/prod.sh command runs as that account, never as root
#   DEPLOY_SHA       deploy: the full commit SHA to release (the ci workflow passed on it)
#   IMAGE_REGISTRY   deploy: the lower-case image prefix, for example ghcr.io/<owner>/<repository>
#   IMAGE_DIGEST_API, IMAGE_DIGEST_JOB, IMAGE_DIGEST_WEB   deploy: the digests the workflow pushed (pull by digest)
#   REGISTRY_USER, REGISTRY_TOKEN   deploy: a short-lived read-only registry token (empty for public images)
#
# deploy: fetch and check out DEPLOY_SHA, then `deploy/prod.sh release` (pull, back up, migrate, start). When the
# release fails, the previous commit and image tag start again before this script fails. rollback: check out the
# previous release's commit and run `deploy/prod.sh rollback`. Either way the images older than the current and the
# previous release are removed. The last line is "vm-deploy: result=<action>-ok" only on success: run-command reports
# success whatever the exit status, so the caller looks for that line. The token is written only to a mode 600 file for
# `docker login --password-stdin` and deleted on exit; it is never printed or a command-line argument. Every run leaves
# a log in /var/log/bank-agent-deploy/.
set -euo pipefail

ACTION="${DEPLOY_ACTION:-deploy}"
CHECKOUT="${VM_CHECKOUT:-}"
LOG_DIR=/var/log/bank-agent-deploy
SHA_PATTERN='^[0-9a-f]{40}$'
TAG_PATTERN='^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$'
TOKEN_FILE=""
OWNER=""

say() { printf 'vm-deploy: %s\n' "$*"; }
fail() {
  say "error: $*"
  say "result=${ACTION}-failed"
  exit 1
}

as_owner() {
  # runuser sets HOME, USER, and LOGNAME for the operator and keeps the rest of the environment.
  runuser -u "${OWNER}" -- "$@"
}

state() {
  # A recorded image tag (current or previous), or nothing; refuses anything that is not a plain tag.
  local file="${CHECKOUT}/deploy/.state/$1" value=""
  [[ -f "${file}" ]] && value="$(cat "${file}")"
  if [[ -n "${value}" && ! "${value}" =~ ${TAG_PATTERN} ]]; then
    say "error: deploy/.state/$1 does not hold an image tag" >&2
    return 1
  fi
  printf '%s' "${value}"
}

checkout_commit() {
  as_owner git -C "${CHECKOUT}" -c advice.detachedHead=false checkout --quiet --detach "$1"
}

prune_images() {
  # Keep the images of the current and the previous release (rollback needs them), drop older ones and dangling layers.
  local current previous repository tag
  current="$(state current)"
  previous="$(state previous)"
  docker image ls --format '{{.Repository}} {{.Tag}}' | while read -r repository tag; do
    case "${repository}" in bank-agent-api | bank-agent-job | bank-agent-web) ;; *) continue ;; esac
    [[ "${tag}" == "${current}" || "${tag}" == "${previous}" ]] && continue
    docker image rm "${repository}:${tag}" > /dev/null 2>&1 || true
  done
  docker image prune --force > /dev/null 2>&1 || true
}

release() {
  [[ "${DEPLOY_SHA:-}" =~ ${SHA_PATTERN} ]] || fail "DEPLOY_SHA must be a full 40-character commit SHA"
  [[ -n "${IMAGE_REGISTRY:-}" ]] || fail "IMAGE_REGISTRY is required"
  local before_commit before_tag
  before_commit="$(as_owner git -C "${CHECKOUT}" rev-parse HEAD)"
  before_tag="$(state current)"
  if [[ -n "${REGISTRY_TOKEN:-}" ]]; then
    TOKEN_FILE="$(mktemp)"
    chown "${OWNER}" "${TOKEN_FILE}"
    chmod 600 "${TOKEN_FILE}"
    printf '%s' "${REGISTRY_TOKEN}" > "${TOKEN_FILE}"
  fi
  unset REGISTRY_TOKEN
  say "releasing ${DEPLOY_SHA} (running before: ${before_tag:-nothing})"
  as_owner git -C "${CHECKOUT}" fetch --quiet origin "${DEPLOY_SHA}"
  checkout_commit "${DEPLOY_SHA}"
  if ! as_owner env IMAGE_REGISTRY="${IMAGE_REGISTRY}" IMAGE_DIGEST_API="${IMAGE_DIGEST_API:-}" \
    IMAGE_DIGEST_JOB="${IMAGE_DIGEST_JOB:-}" IMAGE_DIGEST_WEB="${IMAGE_DIGEST_WEB:-}" \
    REGISTRY_USER="${REGISTRY_USER:-}" REGISTRY_TOKEN_FILE="${TOKEN_FILE}" "${CHECKOUT}/deploy/prod.sh" release; then
    if [[ -n "${before_tag}" ]]; then
      say "the release failed; starting the previous release ${before_tag} again"
      checkout_commit "${before_commit}"
      as_owner env IMAGE_TAG="${before_tag}" "${CHECKOUT}/deploy/prod.sh" up ||
        say "the previous release did not start either; see deploy/prod.sh status and the log"
    fi
    fail "the release of ${DEPLOY_SHA} failed"
  fi
}

rollback() {
  local previous
  previous="$(state previous)"
  [[ -n "${previous}" ]] || fail "no previous release is recorded in deploy/.state/previous"
  # A tag from deploy/prod.sh build or pull is a commit prefix: start it with the compose file it was released with.
  if as_owner git -C "${CHECKOUT}" rev-parse --quiet --verify "${previous}^{commit}" > /dev/null; then
    checkout_commit "${previous}"
  else
    say "tag ${previous} is not a commit in the checkout; keeping the checked-out files"
  fi
  as_owner "${CHECKOUT}/deploy/prod.sh" rollback
}

main() {
  # main runs in the pipeline's subshell (for tee), so the trap that deletes the token file is set here.
  trap 'if [[ -n "${TOKEN_FILE}" ]]; then rm -f -- "${TOKEN_FILE}"; fi' EXIT
  [[ "$(id -u)" == "0" ]] || fail "run as root (run-command does; otherwise sudo)"
  [[ "${ACTION}" == "deploy" || "${ACTION}" == "rollback" ]] || fail "DEPLOY_ACTION must be deploy or rollback"
  [[ "${CHECKOUT}" == /* && -d "${CHECKOUT}/.git" && -x "${CHECKOUT}/deploy/prod.sh" ]] ||
    fail "VM_CHECKOUT must name the repository checkout on the VM"
  OWNER="$(stat -c '%U' "${CHECKOUT}")"
  [[ "${OWNER}" != "root" ]] || fail "the checkout must belong to the operator account, not root"
  if [[ "${ACTION}" == "deploy" ]]; then release; else rollback; fi
  prune_images
  say "running image tag $(state current)"
  say "result=${ACTION}-ok"
}

install -d -m 0700 "${LOG_DIR}"
LOG="${LOG_DIR}/$(date -u +%Y%m%dT%H%M%SZ)-${ACTION}.log"
main 2>&1 | tee -a "${LOG}"
exit "${PIPESTATUS[0]}"
