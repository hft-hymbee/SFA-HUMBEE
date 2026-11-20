# Lead viewing: list + detail for SO, Manager, Admin

Date: 2026-11-20 · Branch base: `development` · Approved prototype: https://claude.ai/artifact/Q9axwM3DV4kocTCK4eGGhk

## Why
Sales officers capture new-manufacturer leads at `/sp/leads/new` (`POST /api/v1/leads` → `targets_leads`), but no one can see them afterwards: there is no read API and no screen. Admins need the org-wide picture, managers need their team's leads and who captured each, and SOs need their own history.

## What a lead is
A lead is exactly **one new manufacturer** that Humbee wants to onboard. The capture form takes one required "Manufacturer name" (stored as `company_name`, max 120). The old multi-manufacturer chip field was a bug and has been removed. On PLAT-12366 the API drops `associated_manufacturers` from the request and the response. It stores `[company_name]` in the existing array column, which keeps the column's "at least one" check satisfied with no migration. `company_name` is capped at 120 characters. Old app builds that still send the list keep working, because the extra field is ignored.

## Goals
- A paged, filterable lead list and a lead detail screen for each role:
  - **SO (`sales_person`)**: own leads only.
  - **Manager**: whole reporting tree (all levels, via `org_hierarchy_edges`) + own leads. Same `OWN_TREE` rule as orders/coverage.
  - **Admin**: every lead in the tenant.
- Manager/Admin can filter by the employee who captured the lead.
- Detail shows every field captured by the form, including the **full mobile number** with a Call action (all three roles; confirmed).
- UI is built from `humbee-design-system` components and `design-tokens` CSS vars only. No hand-rolled lookalikes and no literal colours (user requirement).

## Non-goals
- Editing leads, changing status/interest, converting a lead to an outlet, export.
- Status or interest filters. Every lead is currently written as `captured`/`hot`, so these filters would never narrow the list. Status chip is still displayed.
- Numbered pagination (confirmed: "Load more"/infinite scroll, app convention).

## Anti-goals
- Any role seeing a lead outside its scope, through the list, detail, counts or employee filter. Out-of-scope = **404**, never 403 (codebase convention).
- A UI that drifts from the design system (custom chips/rows/inputs where a DS component exists).

## Approaches considered
1. **One scoped endpoint pair (`GET /leads`, `GET /leads/{id}`) using the existing `apply_scope`.** Role behaviour falls out of `ScopeResolver` with no per-role branching. **Chosen.**
2. Separate endpoints per role (`/leads/mine`, `/manager/leads`, `/admin/leads`): triple the surface and duplicates scope logic the codebase centralises in `modules/org/scope.py`. Rejected.
3. Reporting read-model / materialised view: unnecessary at current volume, and `ix_targets_leads_mine` already covers the SO query. Rejected.

## Decided design

### Approved screens (see prototype)
- **Entry points**:
  - SO: More → Outlets → **My leads**, under "Capture lead".
  - Manager: More → Operations → **Leads**.
  - Admin: More → Operations → **Leads**.
- **After capture**, SO lands on `/sp/leads` (today: `/sp/more`), and the new lead is first in the list.
- **List**, top to bottom:
  - Search: manufacturer name, contact name, email.
  - **Captured by** selector (Manager/Admin only). Opens a searchable sheet:
    - "All my team" / "All employees", then "Me" (manager only, because `/org/employees` excludes the manager), then one row per employee.
    - Each employee row shows name, code, role, "reports to" and that person's total lead count.
    - A clear (×) control resets it.
  - Date chips: **All time** (default) · This month · Last 30 days · Custom (From/To date fields; To ≤ today, From ≤ To).
  - Count line "N leads [by X]" + "Clear filters" link when any filter is active.
  - Rows:
    - initials tile, manufacturer name, "contact · designation"
    - "captured by <name>" (Manager/Admin; "You" for own)
    - short date (Today / Yesterday / 18 Nov), chevron
  - Newest first, 20 per page, **Load more (n left)** button, plus infinite-scroll trigger; "That's all N leads" at end.
  - SO list has a floating **Capture lead** button.
  - States: skeleton loading, error + Try again, empty (SO variant has Capture CTA), "No leads match these filters" + Clear filters.
- **Detail**:
  - Header card: initials tile, manufacturer name, "Captured <date>, <time>", status chip, **Call** (primary) and **Email** (outlined) buttons.
  - Sections:
    - Manufacturer: Manufacturer name, Annual turnover `₹ X.XX cr`, Head office.
    - Contact: Name, Designation, Mobile, Email.
    - Message.
    - Captured by:
      - SO sees "You" + own code.
      - Manager/Admin see name, code · role, **Reports to**.
      - Date & time.
  - Blank optional fields read "Not provided"; blank message reads "No message added".
  - Unknown/out-of-scope id: "Lead not found" state with Back.
- Filters persist when returning from detail (URL query params).

### Backend (`apps/api/src/humbee_sfa/modules/targets/`)
- `GET /api/v1/leads`
  - Query params:
    - `from`, `to`: dates on `business_date`, inclusive. Inverted range → 422 `invalid_date_range`.
    - `employee_id`: validated with `org_service.get_employee_in_scope`, 404 if outside scope.
    - `q`: ≤120. `ilike` on company_name (manufacturer), prospect_name, contact_email.
    - `cursor`: composite `"{occurred_at iso}|{id}"`, as in `approvals/service.py`.
    - `limit`: 1–50, default 20.
  - Returns `LeadPage { items: LeadListItem[], total, next_cursor }`.
  - Order: `occurred_at DESC, id DESC`.
  - `total` uses the same predicate, without the cursor.
- `GET /api/v1/leads/{id:ulid}` → `LeadDetailOut`. 404 when missing, inactive or out of scope.
- `GET /api/v1/leads/counts-by-employee` → `{ items: [{ employee_id, name, count }] }`.
  - Scoped group-by over active leads in scope. `name` comes from `list_employee_names`, which also covers deactivated employees.
  - Ignores list filters: totals, as in the prototype sheet.
  - Feeds the counts in the Captured-by sheet.
  - **Route must be declared before `/leads/{id}`** (or rely on the ulid converter rejecting it).
- Scope: `ScopeResolver.resolve_from_claims(claims, OrgResource.EMPLOYEE)` + `apply_scope(..., tenant_column=Lead.tenant_id, employee_id_column=Lead.captured_by_employee_id)`, plus `Lead.is_active`. This is the same resource the existing `count_leads_in_scope` uses.
- Schemas (`schemas.py`):
  - `CapturedBy { id, name, employee_code, role_code, reports_to_name | null }`. The list only needs `id`, `name`; `employee_code`, `role_code` and `reports_to_name` are filled on detail only. Builder may split this into two models.
  - `LeadListItem { id, company_name, name, designation, status, captured_at, captured_by }`
  - `LeadDetailOut`: all `LeadOut` fields + `mobile` (E.164, via `core/security.decrypt_phone`) + `business_date` + `captured_by`.
- Name/code/manager resolution goes through `org_service` public functions only; import-linter forbids importing org models into targets.
  - List: `list_employee_names` (one query per page).
  - Detail: `get_employee_dimension_fields` (code, role, manager id), then `list_employee_names` for the manager.
  - A deactivated employee still renders by name, because `list_employee_names` deliberately includes them. Only an id that no longer resolves renders as "Former employee".
- No migration. `ix_targets_leads_mine` serves the SO path.
- Regenerate `@humbee/api-contract` in the same commit.

### Web (`apps/web/src/features/leads/`)
- Next 16 static export ⇒ detail via query param:
  - SO: `/sp/leads/detail?id=`.
  - Mgmt: `/mgmt/lead?id=`.
- Read `node_modules/next/dist/docs/` before writing (per `apps/web/AGENTS.md`).
- `service.ts`/`hooks.ts`: `useLeads(filters)` (`useInfiniteQuery`, as in `orders/hooks.ts`), `useLead(id)`, `useLeadCountsByEmployee()`, actor-scoped keys. `useCaptureLead` invalidates them.
- SO:
  - `app/(sp)/sp/leads/page.tsx` (`MyLeadsScreen`) and `app/(sp)/sp/leads/detail/page.tsx`, built from SP shell pieces (`SpScreen`, `SpCard`, `SpSectionLabel`, `SpStatusRow`).
  - Map `/sp/leads*` → More tab.
- Management:
  - Views `leads` and `lead` added to `managementViews`, `viewTitles`, `ManagementFeaturePage` cases, `managerGroups`/`adminGroups` (Operations), and `activeTab` → More.
  - Built from `ManagementScreen`, `Section`, detail-row styles.
- Design-system components to use: `ListRow`, `StatusChip`, `TextField` (search), `DateField` (custom range), `Select` searchable or `BottomSheet` + `ListRow` (Captured by), `Button`, `IconButton`, `EmptyState`, `ErrorState`, `Skeleton`. Existing filter-chip classes are `.sp-filter-chip` (SP) and `.filterBar` (mgmt).
  - Where the prototype shows something the DS lacks (e.g. initials tile), compose it from DS primitives + token CSS vars in the feature's CSS module.
  - **No literal colours.**
- Captured-by sheet data:
  - Employees from `useEmployees({ status: "active" })`. It is already scoped server-side, and it loads every page through `fetchAllPages`, so it is not capped at 100. Rows carry name, `employee_code`, role and `manager_employee_id`. Resolve "reports to" from the same list; a manager's direct reports show "reports to You".
  - Counts from the counts endpoint. Active employees with no leads show 0.
  - Any capturer in the counts response who is not in the active list (deactivated) is appended under a "Former employees" group, by name, and is still selectable, so their leads stay filterable.
- Call/Email use `tel:`/`mailto:` links.

## Calls I made (check these)
- "All time" is the default date chip.
- Counts in the Captured-by sheet are all-time totals, not filtered.
- A deactivated capturer keeps their name everywhere. In the Captured-by sheet they sit under a "Former employees" group and can still be selected. "Former employee" appears only for an id that no longer resolves.
- `limit` max 50 (orders convention) rather than 100.

## Left to the builder
- Exact component composition and CSS module names, within the DS-only rule.
- Whether to split `CapturedBy` into list/detail variants.
- Query-key naming, debounce timing (reuse `useDebouncedSearchQuery`).

## Verification
- API tests `apps/api/tests/modules/targets/test_leads_read.py`:
  - Scope matrix: SO own; manager direct + grand-report + own, not peer team; admin all; other tenant never.
  - 404 cases.
  - `employee_id` out of scope.
  - Date range + 422.
  - Search across all three fields.
  - Cursor paging stable across pages; `total`; counts endpoint scoped.
  - Full mobile on detail.
- `tests/invariants/test_scope_matrix.py`, `tooling/ci/check-contract-drift.sh`, `tooling/ci/check-web.sh` pass.
- Manual run per role against the local API, compared side by side with the prototype.
