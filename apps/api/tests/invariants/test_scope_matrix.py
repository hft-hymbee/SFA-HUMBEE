from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.fixtures import seed

from humbee_sfa.core.errors.handlers import ApiError
from humbee_sfa.core.security import encrypt_phone, hmac_phone
from humbee_sfa.modules.org.models import Employee, HierarchyEdge
from humbee_sfa.modules.org.scope import (
    OrgResource,
    Scope,
    ScopeContext,
    ScopeResolver,
    apply_scope,
)

READ_RESOURCES = (OrgResource.EMPLOYEE, OrgResource.GEOGRAPHY_ASSIGNMENT, OrgResource.ACTIVITY_DATA)
OTHER_TENANT = "OtherTenant"


def _resolve(role: str, resource: OrgResource, *, actor_id: str = "01JTESTACTOR0000000000000") -> ScopeContext:
    return ScopeResolver.resolve(
        tenant_id=seed.tenant_id(), actor_employee_id=actor_id, actor_role=role, resource=resource
    )


@pytest.mark.parametrize(
    ("role", "resource", "scope", "can_write"),
    [
        *(
            (role, resource, scope, can_write)
            for resource in READ_RESOURCES
            for role, scope, can_write in (
                ("sales_person", Scope.SELF, False),
                ("manager", Scope.OWN_TREE, False),
                ("admin", Scope.ORG, True),
            )
        ),
        ("admin", OrgResource.HIERARCHY_MUTATION, Scope.ORG, True),
    ],
)
def test_role_resolves_to_one_scope(
    role: str, resource: OrgResource, scope: Scope, can_write: bool
) -> None:
    context = _resolve(role, resource)
    assert (context.scope, context.can_write) == (scope, can_write)


@pytest.mark.parametrize(
    ("role", "resource"),
    [
        ("sales_person", OrgResource.HIERARCHY_MUTATION),
        ("manager", OrgResource.HIERARCHY_MUTATION),
        ("system", OrgResource.EMPLOYEE),
        ("owner", OrgResource.ACTIVITY_DATA),
        ("ADMIN", OrgResource.EMPLOYEE),
    ],
)
def test_denied_resolutions(role: str, resource: OrgResource) -> None:
    with pytest.raises(ApiError) as denied:
        _resolve(role, resource)
    assert (denied.value.status_code, denied.value.code) == (403, "forbidden")


def _foreign_employee(db: Session, under: Employee) -> Employee:
    phone = "+919555500001"
    foreign = Employee(
        tenant_id=OTHER_TENANT,
        employee_code=under.employee_code,
        full_name="Foreign Person",
        first_name="Foreign",
        display_initials="FP",
        role_code="sales_person",
        designation_code="network_officer_salesperson",
        status="active",
        login_enabled=True,
        manager_employee_id=under.id,
        phone_e164_hmac=hmac_phone(phone),
        phone_e164_enc=encrypt_phone(phone),
        phone_last4=phone[-4:],
    )
    db.add(foreign)
    db.flush()
    db.add_all(
        [
            HierarchyEdge(
                tenant_id=OTHER_TENANT,
                ancestor_employee_id=foreign.id,
                descendant_employee_id=foreign.id,
                depth=0,
            ),
            HierarchyEdge(
                tenant_id=OTHER_TENANT,
                ancestor_employee_id=under.id,
                descendant_employee_id=foreign.id,
                depth=1,
            ),
        ]
    )
    db.flush()
    return foreign


def test_scoped_rows_never_cross_tenant(db_session: Session) -> None:
    admin = seed.employee(db_session, "admin")
    manager = seed.employee(db_session, "manager")
    sp = seed.employee(db_session, "sales_person", manager=manager)
    outsider = seed.employee(db_session, "manager")
    _foreign_employee(db_session, manager)

    def visible(actor: Employee) -> set[str]:
        context = _resolve(actor.role_code, OrgResource.EMPLOYEE, actor_id=actor.id)
        statement = apply_scope(
            select(Employee.id),
            context,
            tenant_column=Employee.tenant_id,
            employee_id_column=Employee.id,
        )
        return set(db_session.scalars(statement))

    assert visible(sp) == {sp.id}
    assert visible(manager) == {manager.id, sp.id}
    assert visible(admin) == {admin.id, manager.id, sp.id, outsider.id}
