"""`targets_manufacturer_lines` — per-manufacturer breakdown of a `sales` target. database-design.md
§11.2. `target_id` is a declared FK (§2.6 exception list) since this child has no life outside its
parent target.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class TargetManufacturerLine(Base, ConventionsMixin):
    __tablename__ = "targets_manufacturer_lines"
    __table_args__ = (
        Index("uq_targets_lines", "target_id", "humbee_manufacturer_id", unique=True),
        CheckConstraint("line_value > 0", name="targets_lines_value_chk"),
        CheckConstraint("line_basis IN ('amount','volume')", name="targets_lines_basis_chk"),
    )

    target_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    humbee_manufacturer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    manufacturer_label_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    # Resolved server-side from `GET /sfa/v1/targets/manufacturers` at write time and snapshotted,
    # same reasoning as the label above — a manufacturer's unit does not silently rewrite history.
    line_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    uom_label_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    line_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
