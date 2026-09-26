# Progress

Continuity for the build lives in this file, not in chat history. Every phase adds an entry to the phase log and updates the current state.

## Current state

| Field | Value |
|---|---|
| Last completed phase | 00, bootstrap and guardrail verification |
| Next phase | 01, monorepo scaffold and quality gates (`kit/prompts/01-scaffold.md`) |
| Blocked | None |

Pending human actions (not blocking phase 01):

1. Create `.env` from `.env.example` and fill in the organizer S3 values and local secrets. Never paste the values into a session. Then run `python3 scripts/checks/check_env_keys.py` and confirm every required name reports `set`. Phase 03 needs the S3 values and phase 01 integration tests need the PostgreSQL passwords.
2. Run `/status` in Claude Code from the repository root and record the loaded setting sources in the phase 00 entry below.

## Phase log

### Phase 00: bootstrap and guardrail verification (2026-09-26)

Plan: `docs/plans/phase-00.md`.

#### What was done

- Verified the toolchain, skills, attribution settings, ignore rules, and hooks without installing anything.
- Ran the guard self-tests on scratch files and recorded the outputs below.
- Fixed a `.gitignore` defect: `data/` excluded the directory itself, so the existing `!data/.gitkeep` negation had no effect. The rule is now `**/data/*`, which still ignores the contents of every `data` directory at any depth. Added `data/.gitkeep`.
- Added `scripts/checks/check_env_keys.py`, which reports `set` or `unset` for every name documented in `.env.example`, never a value, and exits 1 when a required name is unset.
- Created this file, `docs/BACKLOG.md`, and `docs/plans/`.

#### Environment report

| Tool | Version | Notes |
|---|---|---|
| git | 2.55.0 | |
| uv | 0.11.17 | |
| Python | 3.12.13, uv-managed | System `python3` is Homebrew 3.14.7; the guard scripts are stdlib-only and run under it through pre-commit |
| Node | v24.14.1 | Newer than the preferred 22 LTS; see `docs/BACKLOG.md` |
| npm | 11.11.0 | |
| Docker | 29.8.0, daemon running | |
| Docker Compose | v5.5.1 | |
| pre-commit | 4.6.2 | pre-commit and commit-msg hooks installed; `core.hooksPath` unset |
| gitleaks | 8.30.1 | The pre-commit hook pins v8.21.2 until phase 01 runs `pre-commit autoupdate` |
| AWS CLI | 2.36.26 | Optional; ingestion uses boto3 |
| go | 1.26.1 | Builds the gitleaks pre-commit hook |
| libomp | 23.1.2 | LightGBM prerequisite |

Skills present under `.claude/skills/`: `design-taste-frontend`, `minimalist-ui`, `full-output-enforcement`.

Settings: `.claude/settings.json` sets `attribution.commit` and `attribution.pr` to empty strings and `attribution.sessionUrl` to `false`. A gitignored `.claude/settings.local.json` allows `git commit *`; the project deny rules for `--no-verify` and `-n` still apply. Loaded setting sources from `/status`: pending human action.

Ignore rules: `git check-ignore -v` confirms `.env`, `.env.*` except `.env.example`, `data/` contents, `kit/`, `mlruns/`, `node_modules/`, `dist/`, `.coverage`, `coverage.xml`, `htmlcov/`, `apps/web/coverage/`, and `*.duckdb`. Nothing under `kit/` is tracked; the only tracked file under `data/` is `data/.gitkeep`.

Secret hygiene: `.env` does not exist yet (checked for existence only, never read). Running `python3 scripts/checks/check_env_keys.py` in the repository prints the notice `.env not found; checking the process environment only`, reports all 9 required names as unset, and exits 1.

#### Guard self-test results

| Test | Command | Result |
|---|---|---|
| Attribution stripping | `python3 scripts/hooks/strip_ai_attribution.py msg.txt` on a scratch message containing `Co-Authored-By: Claude Opus <noreply@anthropic.com>` and `Generated with [Claude Code](https://claude.com/claude-code)` | Printed `strip-ai-attribution: removed attribution lines from the commit message`, exit 0. The file kept only the subject and body; a grep for either line found 0 matches |
| Emoji check, failing case | `python3 scripts/checks/check_no_emoji.py emoji.txt` on a file written by Python with U+1F600 | `emoji.txt:1:7: emoji character U+1F600 is not allowed`, `check-no-emoji: 1 emoji character(s) found`, exit 1 |
| Emoji check, passing case | `python3 scripts/checks/check_no_emoji.py CLAUDE.md` | exit 0 |
| Attribution history | `scripts/checks/check_no_ai_attribution.sh` | `check-no-ai-attribution: clean for range 'HEAD'`, exit 0 |
| All hooks | `pre-commit run --all-files` | gitleaks, large files, private key, merge conflict, end of file, trailing whitespace, and emoji hooks all passed |
| Secrets in history | `gitleaks git --redact .` | no leaks found |

Environment key check self-tests, all with scratch env files and an emptied process environment, never the real `.env`:

| Case | Result |
|---|---|
| Every required name set to a unique sentinel, mixing quoted, `export`, and inline-comment forms | exit 0, `all 9 required variable(s) set`, 0 sentinel strings in the output |
| `SESSION_SECRET` empty with a trailing comment, `CSRF_SECRET` absent | exit 1, both reported `unset`, `2 of 9 required variable(s) unset`, 0 sentinel strings in the output |
| Env file does not exist | notice printed, process environment used, exit 1 |
| Name set only in the process environment | reported `set`, value not printed |

#### Decisions

- `.gitignore` uses `**/data/*` instead of `data/` so that `data/.gitkeep` can be tracked. Approved by the human with the phase plan. No ADR: this is a correction, not a choice between alternatives.
- The required variable set for `check_env_keys.py` is the S3 values, both PostgreSQL passwords, and the session and CSRF secrets. The LLM keys stay optional while `LLM_PROVIDER=fake`. Approved by the human.
- No dependencies were added.

#### How to verify

```bash
pre-commit run --all-files
python3 scripts/checks/check_no_emoji.py
scripts/checks/check_no_ai_attribution.sh
gitleaks git --redact .
git ls-files kit data          # expected: data/.gitkeep only
python3 scripts/checks/check_env_keys.py
```

#### Known limitations

- `make check` does not exist until phase 01, so this phase used the commands above as its substitute.
- `check_env_keys.py` has manual self-tests only; automated tests are in `docs/BACKLOG.md` for phase 01.
- `/status` output and `.env` creation are pending human actions.

#### Next phase

Phase 01, monorepo scaffold and quality gates (`kit/prompts/01-scaffold.md`), in plan mode.
