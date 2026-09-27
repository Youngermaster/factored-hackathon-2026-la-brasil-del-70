"""Request and response models of the HTTP API, separate from the domain models.

Every response model is an allowlist: it names its top-level fields and ignores any other attribute of the domain
object it is built from, so a field added to the domain later never reaches a client by default. Nested parts reuse
the domain's value objects (money, references, masked numbers) and its published customer views and contract
components; ``tests/unit/api/test_credit_data_exposure.py`` walks every customer-role schema in the OpenAPI document
and fails on any internal, credit profile, or risk estimate field, nested or not.
"""
