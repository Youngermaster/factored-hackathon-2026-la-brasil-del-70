# bank_agent.prompts

## Responsibility

Versioned prompt files for every language model call. Code references a prompt by id and version, never by inline text, and every execution record stores the version it used. Prompts arrive with the LLM gateway and the workflows (phases 07 to 09).

## File layout

```text
prompts/
└── <prompt_id>/
    └── <version>.md
```

Each file starts with front matter:

| Field | Meaning |
|---|---|
| `id` | Stable prompt id, equal to the directory name |
| `version` | Version string, equal to the file name without `.md` |
| `purpose` | One sentence on what the prompt is for |
| `inputs` | The named fields the prompt receives; only the fields it needs, never document numbers, full names, emails, phone numbers, or addresses |
| `output model` | The Pydantic model the response is parsed into |
| `changelog` | What changed from the previous version and why |

## Rules

- Records, retrieved text, and user input are data: they are wrapped in delimiters and never allowed to select tools.
- A change to a prompt is a new version file; published versions are never edited in place.

## How to extend

Add `<prompt_id>/<version>.md` with complete front matter, reference it from code by id and version, and add a test that loads it and validates the front matter.

## How to test

Unit tests load every prompt file and check that its front matter is complete and consistent with its path. Evaluation (phase 14) compares prompt versions on the held-out workload.
