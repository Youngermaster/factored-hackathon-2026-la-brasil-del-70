"""Versioned evaluation prompts (B1, the simulated customer, the judge) and their output models (``outputs``).

They follow the application's prompt file format (``bank_agent/prompts/README.md``) and load into a registry of
their own with ``EVAL_OUTPUT_MODELS``, so evaluation output models never enter ``bank_agent.domain``.
"""
