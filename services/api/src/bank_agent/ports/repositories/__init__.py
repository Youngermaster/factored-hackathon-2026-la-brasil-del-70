"""Repository ports, one module per aggregate.

Every repository is bound to one ``AccessContext`` when it is created (usually by a unit of work) and scopes
every query by it. No method accepts a customer identifier. A resource that belongs to another customer
behaves exactly like a missing one: reads return ``None`` or leave it out, and writes raise the entity's
``NotFoundError``. A role the repository does not serve raises ``AccessContextError``.
"""
