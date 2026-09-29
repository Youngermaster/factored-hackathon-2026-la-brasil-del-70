---
name: github-collaboration
description: Use GitHub CLI for this repository's pull requests, issues, reviews, comments, and related GitHub operations when the user's task calls for them.
---

# GitHub collaboration

Use `gh` for live GitHub state and actions related to the current task. Identify the repository from `git remote get-url origin`; do not assume a branch or pull request number from prior work.

Before a GitHub operation, check that `gh` is available and authenticated with `gh auth status`. If the CLI is missing, find an existing installation or install it through the available package workflow. If authentication is missing or expired, ask the user to complete `gh auth login`; never request or store a token in this repository. Recheck authentication after login. If a network or sandbox restriction blocks a necessary command, retry through the environment's approval mechanism.

Fetch current GitHub state before acting. For a review or requested comment, inspect the relevant PR or issue and its existing discussion, then post useful, specific comments with `gh` when the task authorizes that action. Avoid duplicate comments. For multiline text, use `--body-file` with a temporary file. Verify the result with `gh` and share the URL in the final response.

Do not treat this skill as authorization to make unrelated GitHub changes. Follow the user's task and the environment's approval requirements for each action.
