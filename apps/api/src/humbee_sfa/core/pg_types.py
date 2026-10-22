"""Postgres column types SQLAlchemy has no built-in for.

`sqlalchemy.dialects.postgresql` has never shipped an `LTREE` type (confirmed against
SQLAlchemy 2.0.52) despite `ltree` being a documented extension this schema requires (§2.7).
`LtreeType` is a minimal passthrough `UserDefinedType` — values move as plain strings, DDL
renders as `LTREE`.
"""

from __future__ import annotations

from sqlalchemy.types import UserDefinedType


class LtreeType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "LTREE"

    def bind_processor(self, dialect: object) -> None:
        return None

    def result_processor(self, dialect: object, coltype: object) -> None:
        return None
