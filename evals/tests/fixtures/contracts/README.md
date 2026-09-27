# Golden contract documents

Frozen fixtures, not organizer data. `v1.0.0/scenario.json` is the `model_dump(mode="json")` output of the scenario built by `tests/unit/test_scenario_model.py` at commit `4973018`, before any `1.1.0` field existed. All values are synthetic and team-made.

`tests/unit/test_scenario_compatibility.py` checks that every later minor version of the scenario model and of `contracts/schemas/scenario.v1.json` still accepts it unchanged. Never regenerate or edit this file: a change that needs it to change is a breaking contract change and needs a new major version.
