# Backlog

Items that are out of scope for the phase that found them. Each row names the reason and the phase that owns it. Remove a row in the same commit that resolves it.

| Item | Reason | Owning phase | Priority |
|---|---|---|---|
| Add the `make env-check` target that runs `scripts/checks/check_env_keys.py` | No Makefile exists before phase 01; the phase 00 prompt defers the target | 01 | High |
| Add pytest unit tests for `scripts/checks/check_env_keys.py` (set, unset, quoted, commented, missing file, no value in output) | pytest arrives with the phase 01 workspace; phase 00 adds no dependencies and verified the script with manual scratch-file tests | 01 | Medium |
| Decide whether to pin Node 22 LTS or accept Node 24 LTS through `engines` and `.nvmrc` | The local toolchain is Node v24.14.1 while the kit prefers 22 LTS; the web package does not exist yet | 01 | Medium |
| Run `pre-commit autoupdate` so the gitleaks hook moves off v8.21.2 | The seed config pins older hook releases; phase 01 extends the config and pins current releases | 01 | Medium |
| Consider running the repository guard scripts through the uv-managed Python 3.12 instead of the system `python3` | The hooks call Homebrew Python 3.14; harmless while the scripts use only the standard library | 01 | Low |
| Move the LLM API key variables into the `REQUIRED` set of `check_env_keys.py` when a live provider is selected | They are optional while `LLM_PROVIDER=fake` | 08 | Medium |
