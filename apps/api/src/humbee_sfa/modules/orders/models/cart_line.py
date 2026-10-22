"""`orders_cart_lines` — child rows of a cart draft. database-design.md §10.

A child table rather than JSONB (M10 §3.3 permits either) so `qty`/price CHECKs are the *same*
constraints `orders_lines` carries — a cart that cannot be a valid order is rejected at cart time,
not deferred to submit.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from humbee_sfa.core.conventions import ConventionsMixin
from humbee_sfa.core.db import Base


class CartLine(Base, ConventionsMixin):
    __tablename__ = "orders_cart_lines"
    __table_args__ = (
        UniqueConstraint("cart_draft_id", "humbee_product_id", name="uq_orders_cart_lines"),
        CheckConstraint("qty >= 1", name="orders_cart_lines_qty_chk"),
        CheckConstraint(
            "unit_price_net_paise IS NULL OR unit_price_net_paise > 0",
            name="orders_cart_lines_price_chk",
        ),
        CheckConstraint(
            "form_type IS NULL OR form_type IN ('STRAIGHT','BEND')",
            name="orders_cart_lines_form_type_chk",
        ),
    )

    cart_draft_id: Mapped[str] = mapped_column(
        String(26), nullable=False
    )  # REFERENCES orders_cart_drafts(id)
    humbee_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    form_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_price_net_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    unit_price_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
