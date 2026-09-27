"""Deterministic test doubles shared by every package's tests and by the evaluation harness.

Production layers never import this package (an import-linter contract enforces it). It imports only
``bank_agent.domain`` and ``bank_agent.ports``.
"""
