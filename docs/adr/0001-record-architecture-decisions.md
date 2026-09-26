# 0001: Record architecture decisions

- Status: accepted
- Date: 2026-09-26

## Context

The system is built in phases, by humans and by automated sessions that do not share memory. Judges and reviewers need to see why the architecture looks the way it does, and later phases need to know which choices are settled and which constraints they inherit. Decisions that live only in chat history or commit messages are lost or hard to find.

## Considered options

1. **No formal records.** Rely on commit messages, code comments, and the phase log.
2. **A single design document** that is edited as decisions change.
3. **Architecture decision records**: one short, numbered, immutable file per decision, in the MADR format.

## Decision

Option 3. Every choice between real alternatives gets a record in `docs/adr/NNNN-title.md` with context, options, decision, and consequences, and `docs/adr/README.md` stays the index. Records are added in the same commit as the change they describe. A superseded record is kept and marked, with a link to its successor.

## Consequences

- Reviewers can read the reasoning behind each structural choice in one place, with the alternatives that were rejected.
- The phase log in `docs/PROGRESS.md` links to records instead of repeating their reasoning.
- Writing a record costs a few minutes per decision; corrections and routine choices without alternatives do not need one.
- Immutable records mean the history of a reversed decision stays visible.
