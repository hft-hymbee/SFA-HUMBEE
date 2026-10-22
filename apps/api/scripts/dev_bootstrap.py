"""Seed dev identity/org rows after SQL schema bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import humbee_sfa.models_registry  # noqa: F401
from humbee_sfa.core.db import get_engine, get_sessionmaker
from humbee_sfa.core.security import encrypt_phone, hmac_phone
from humbee_sfa.core.settings import get_settings
from humbee_sfa.modules.org.models import Employee
from humbee_sfa.modules.org.service import rebuild_hierarchy

_ADMINS = (
    ("Ashmit Singh", "+918948163193"),
    ("Aditya Nikhil", "+919990202144"),
    ("Felix Ferrao", "+919623670347"),
    ("Sandeep Singh", "+917011975793"),
)


def _upsert_employee(
    session,
    *,
    tenant_id: str,
    employee_code: str,
    first_name: str,
    full_name: str,
    role_code: str,
    designation_code: str,
    status: str,
    phone_e164: str,
) -> Employee:
    existing = session.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.employee_code == employee_code,
            Employee.is_active.is_(True),
        )
    ).scalar_one_or_none()

    phone_hash = hmac_phone(phone_e164)
    phone_enc = encrypt_phone(phone_e164)
    phone_last4 = phone_e164[-4:]
    initials = "".join(part[0].upper() for part in full_name.split()[:2])[:3] or first_name[:1].upper()

    if existing is not None:
        existing.first_name = first_name
        existing.full_name = full_name
        existing.role_code = role_code
        existing.designation_code = designation_code
        existing.status = status
        existing.phone_e164_hmac = phone_hash
        existing.phone_e164_enc = phone_enc
        existing.phone_last4 = phone_last4
        existing.display_initials = initials
        return existing

    row = Employee(
        tenant_id=tenant_id,
        employee_code=employee_code,
        first_name=first_name,
        full_name=full_name,
        display_initials=initials,
        role_code=role_code,
        designation_code=designation_code,
        status=status,
        login_enabled=True,
        phone_e164_hmac=phone_hash,
        phone_e164_enc=phone_enc,
        phone_last4=phone_last4,
    )
    session.add(row)
    session.flush()
    return row


def main() -> None:
    settings = get_settings()
    if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError(
            "database_url must point to Postgres for dev bootstrap "
            "(expected postgresql:// or postgresql+psycopg://)."
        )
    engine = get_engine(settings.database_url)
    existing_tables = set(inspect(engine).get_table_names())
    required_tables = {"org_employees", "identity_otp_challenges", "platform_domain_events"}
    missing_tables = sorted(required_tables - existing_tables)
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            "Schema is not bootstrapped. Run apps/api/scripts/apply_dev_sql_bootstrap.sh first. "
            f"Missing tables: {missing}"
        )
    session_factory = get_sessionmaker(settings.database_url)

    with session_factory() as session:
        admins = [
            _upsert_employee(
                session,
                tenant_id=settings.tenant_id,
                employee_code=f"ADM-{number:03d}",
                first_name=full_name.split()[0],
                full_name=full_name,
                role_code="admin",
                designation_code="admin",
                status="active",
                phone_e164=phone_e164,
            )
            for number, (full_name, phone_e164) in enumerate(_ADMINS, start=1)
        ]

        # These rows are written directly, so the closure table and `hierarchy_path` are derived
        # from them afterwards rather than maintained by hand here.
        members, edges = rebuild_hierarchy(session, tenant_id=settings.tenant_id)
        session.commit()

    print("Seed complete:")
    print(f"  hierarchy: {members} tree members, {edges} closure edges")
    for admin in admins:
        print(f"  admin: id={admin.id} code={admin.employee_code}")


if __name__ == "__main__":
    main()
