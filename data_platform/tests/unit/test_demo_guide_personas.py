"""The web demo guide only names personas that the seed of the committed sample loads.

`make seed` on the committed sample (the quickstart default and the deployed demo's job image) loads the personas
of `data_platform/seed/personas.sample.yaml`; four personas of the full delivery have no match in the sample. A
guide scenario played by one of them fails at sign-in on the demo, which is how the phase 17 audit found them.
"""

import re
from pathlib import Path

from bank_data.seed.config import DEFAULT_SAMPLE_PERSONAS_FILE, load_personas

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = ROOT / "apps" / "web" / "src" / "features" / "demo-guide" / "model" / "scenarios.ts"


def test_every_demo_guide_persona_is_seeded_from_the_committed_sample() -> None:
    named = set(re.findall(r"persona: '([a-z0-9-]+)'", SCENARIOS.read_text(encoding="utf-8")))
    seeded = {persona.id for persona in load_personas(DEFAULT_SAMPLE_PERSONAS_FILE).customers}
    assert named, "no persona found in the demo guide"
    assert named <= seeded, f"not seeded from the committed sample: {sorted(named - seeded)}"
