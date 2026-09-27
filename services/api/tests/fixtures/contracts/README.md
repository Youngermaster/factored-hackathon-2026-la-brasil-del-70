# Golden contract documents

Frozen fixtures, not organizer data. Each file under `v1.0.0/` is the `model_dump(mode="json")` output of a phase 02 test builder (`bank_agent_builders.handoff`, `execution_record`, and `decision`) at commit `4973018`, before any `1.1.0` field existed. All values are synthetic and team-made.

They stand for documents that were stored under version `1.0.0` of each contract. `tests/unit/domain/test_contract_compatibility.py` checks that every later minor version of the models and of the generated schemas in `contracts/schemas/` still accepts them unchanged. Never regenerate or edit these files: a change that needs them to change is a breaking contract change and needs a new major version.
