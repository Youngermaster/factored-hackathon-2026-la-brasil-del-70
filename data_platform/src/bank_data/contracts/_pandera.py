"""Import Pandera without its global patch of ``typing._GenericAlias.__call__``.

Importing ``pandera.pandas`` replaces ``typing._GenericAlias.__call__`` process-wide so that
``DataFrame[Model](data)`` can validate on construction. The replacement reads ``self.__origin__.__bases__``,
which a ``NewType`` does not have, so calling any ``Annotated[NewType, ...]`` alias fails afterwards; the
bank-agent identifiers (``CustomerId("C1")``) are such aliases, and tests of every package share one process.
This project only uses the object API (``DataFrameSchema``), never the generic ``DataFrame[Model]`` form, so
the original method is restored. Every module imports Pandera through here.
"""

import typing

import pandera.errors as errors
import pandera.pandas as pa
import pandera.typing.common as _pandera_typing_common

_ORIGINAL_CALL = getattr(_pandera_typing_common, "__orig_generic_alias_call", None)
if _ORIGINAL_CALL is not None:
    typing._GenericAlias.__call__ = _ORIGINAL_CALL  # type: ignore[attr-defined]

__all__ = ["errors", "pa"]
