# Lead Viewing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sales officers, managers and admins can browse captured manufacturer leads (scoped by role, filtered, paged) and open a lead to see everything captured; each lead is exactly one manufacturer.

**Architecture:**
- **Backend.** One scoped endpoint trio in the `targets` module: `GET /api/v1/leads`, `GET /api/v1/leads/{id}` and `GET /api/v1/leads/counts-by-employee`.
  - Role behaviour comes entirely from the existing `ScopeResolver` + `apply_scope`.
  - Employee names, codes and managers come through `org_service` public functions. Importing org models is forbidden by import-linter.
- **Web.**
  - Shared data layer in `apps/web/src/features/leads/`.
  - SO screens under `app/(sp)/sp/leads/`.
  - Manager/admin screens as two new management views (`leads`, `lead`) in the existing `[view]` route.

**Tech Stack:**
- API: FastAPI, Pydantic v2, SQLAlchemy 2, Postgres. Tests use pytest with testcontainers.
- Contract: OpenAPI is generated into `@humbee/api-contract` by hey-api.
- Web: Next 16 App Router with static export, React Query, `humbee-design-system` (MUI 5), and `design-tokens` CSS vars.

**Spec:** `docs/superpowers/specs/2026-11-20-lead-viewing-design.md`. The approved prototype is at https://claude.ai/artifact/Q9axwM3DV4kocTCK4eGGhk.

## Global Constraints

- **Branch:** `PLAT-12366`. Backend and web edits are both allowed.
- **Commits:**
  - Invoke the `commit` skill before every commit.
  - No Claude/AI attribution lines.
  - Messages are prefixed `PLAT-12366`, e.g. `PLAT-12366 feat(api): …`.
- **Scope:**
  - SO = own leads.
  - Manager = whole tree (all depths) + own.
  - Admin = whole tenant.
  - Out-of-scope or missing → **404**, never 403.
- **One manufacturer per lead.** The manufacturer name is `company_name`, 2–120 chars. The client never sends a manufacturer list.
- **Full mobile number** (E.164) on detail for all three roles.
- **Paging:** newest first (`occurred_at DESC, id DESC`). `limit` 1–50, default 20. Composite cursor `"{occurred_at iso}|{id}"`. "Load more" plus infinite scroll; no numbered pages.
- **No status/interest filters.** The status chip is still displayed.
- **UI uses only `humbee-design-system` components and `design-tokens` CSS vars.**
  - No literal colours, no hand-made lookalikes of DS components.
  - Read each component's `.prompt.md` in `packages/humbee-design-system/src/**` before using it.
- **Read `apps/web/node_modules/next/dist/docs/` before writing web code** (per `apps/web/AGENTS.md`). Static export ⇒ detail via `?id=`, not a dynamic segment.
- **Copy (exact):**
  - Titles: "My leads" (SO list), "Leads" (mgmt list), "Lead details" (detail).
  - Empty, SO: "No leads yet" / "Leads you capture for new manufacturers will show up here." + button "Capture a lead".
  - Empty, manager: "No one in your team has captured a lead yet."
  - Empty, admin: "No one in the organisation has captured a lead yet."
  - No match: "No leads match these filters" / "Try a different date range or search." + "Clear filters".
  - Error: "Couldn't load leads" / "Check your connection and try again." + "Try again".
  - Not found: "Lead not found" / "This lead doesn't exist or isn't in your scope." + "Back to leads".
  - Blank optional field: "Not provided". Blank message: "No message added."
  - Date chips: "All time" (default), "This month", "Last 30 days", "Custom".
  - Captured-by sheet: "All my team" / "All employees", "Me (my own leads)", group "Former employees".
  - Unresolvable capturer: "Former employee".
- **Commands:**
  - API tests: `cd apps/api && .venv/bin/pytest <path> -q`. Docker must be running for testcontainers.
  - Contract regen: `cd packages/api-contract && HUMBEE_API_PYTHON=../../apps/api/.venv/bin/python npm run generate && npm run check:breaking`.
  - Web: `cd apps/web && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/eslint .`
  - Web build: `cd apps/web && NEXT_PUBLIC_SFA_API_BASE_URL=https://api.example.invalid npx next build`.

## Review Focus

1. **Search text containing `%` or `_`.** Must match literally, not act as a wildcard. Test in Task 2 (`test_search_is_literal`).
2. **Two leads with the identical `occurred_at` across a page boundary.** Neither may be skipped or repeated. Test in Task 2 (`test_cursor_paging_is_stable_on_ties`).
3. **Garbage `cursor` value.** 422 `invalid_cursor`, not 500. Test in Task 2.
4. **A manager filtering `employee_id` = themselves, an SO filtering on their own id.** Both allowed. An SO filtering on someone else → 404. Test in Task 2 (`test_employee_filter_scope`).
5. **Soft-deactivated lead (`is_active = false`).** Absent from list, `total`, counts and detail. Test in Task 3 (`test_inactive_lead_hidden_everywhere`).

---

### Task 1: One manufacturer per lead (API + form)

**Files:**
- Modify: `apps/api/src/humbee_sfa/modules/targets/schemas.py` (`CaptureLeadBody`, `LeadOut`, delete `ManufacturerName` + `_dedupe_manufacturers`)
- Modify: `apps/api/src/humbee_sfa/modules/targets/service.py` (`capture_lead`, `_lead_payload`)
- Modify: `apps/api/tests/modules/targets/test_targets.py` (`test_reused_lead_id_conflicts` body)
- Create: `apps/api/tests/modules/targets/test_leads.py`
- Create: `packages/api-contract/CHANGELOG.md`
- Regenerate: `packages/api-contract/openapi.json`, `packages/api-contract/src/generated/*`
- Modify: `apps/web/src/features/leads/form-state.ts`. The form/screen edits are already in the working tree: the chip field is removed and "Company name" is relabelled "Manufacturer name".
- Commit with it: `docs/superpowers/specs/2026-11-20-lead-viewing-design.md`, this plan.

**Interfaces:**
- Produces: a `CaptureLeadBody` without `associated_manufacturers`, with `company_name: str = Field(min_length=2, max_length=120)`.
  - The service stores `associated_manufacturer_names=[body.company_name]`. The DB keeps its array column and cardinality check, so no migration.
  - `LeadOut` drops `associated_manufacturers`.
  - Pydantic's default `extra="ignore"` means old app builds that still send the list keep working.

- [ ] **Step 1: Write failing tests** in a new `apps/api/tests/modules/targets/test_leads.py`. Use the same imports/fixtures as `test_targets.py`, plus a module helper `_lead_body(**overrides) -> dict` (name "Ravi Kumar", mobile "+919845012345", email "ravi@example.com", company_name "Kumar Oils").

```python
def test_capture_stores_company_as_the_single_manufacturer(api_client, db_session):
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    resp = login(api_client, sp).post("/api/v1/leads", _lead_body(associated_manufacturers=["A", "B"]))
    assert resp.status_code == 201, resp.text
    assert "associated_manufacturers" not in resp.json()
    lead = db_session.scalars(select(Lead)).one()
    assert lead.associated_manufacturer_names == ["Kumar Oils"]

def test_capture_rejects_manufacturer_name_over_120(api_client, db_session):
    sp = seed.employee(db_session, "sales_person", manager=seed.employee(db_session, "manager"))
    resp = login(api_client, sp).post("/api/v1/leads", _lead_body(company_name="X" * 121))
    assert resp.status_code == 422
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/modules/targets/test_leads.py -q`. Expected: both FAIL.
- [ ] **Step 3: Implement the schema/service change.**
  - Update the `CaptureLeadBody` docstring to say a lead is one manufacturer not on Humbee, named by `company_name`.
  - In `test_reused_lead_id_conflicts`, drop `associated_manufacturers` from the body.
- [ ] **Step 4: Run** `.venv/bin/pytest tests/modules/targets -q`. Expected: all PASS.
- [ ] **Step 5: Regenerate the contract** (Global Constraints command).
  - If `check:breaking` reports the removed fields, create `packages/api-contract/CHANGELOG.md` with a dated entry: `BREAKING CHANGE: CaptureLeadBody.associated_manufacturers and LeadOut.associated_manufacturers removed — a lead is exactly one manufacturer (company_name, max 120).`
  - Re-run until it passes.
- [ ] **Step 6: Web.** In `buildCaptureLeadBody`:
  - Remove the `associated_manufacturers` line and the two-line comment above the function.
  - Add `maxLength: 120` to the Manufacturer name `inputProps` in `screens.tsx`.
  - Run the web tsc + eslint command. Expected: no errors.
- [ ] **Step 7: Commit** (via `commit` skill): `PLAT-12366 fix(leads): a lead is exactly one manufacturer`. Include the spec + plan docs.

---

### Task 2: `GET /api/v1/leads` (scoped list)

**Files:**
- Modify: `apps/api/src/humbee_sfa/modules/targets/schemas.py`
- Modify: `apps/api/src/humbee_sfa/modules/targets/repository.py`
- Modify: `apps/api/src/humbee_sfa/modules/targets/service.py`
- Modify: `apps/api/src/humbee_sfa/modules/targets/router.py`
- Test: `apps/api/tests/modules/targets/test_leads.py`

**Interfaces:**
- Consumes: Task 1's capture endpoint (tests create leads through it).
- Produces, all in `schemas.py`:
  - `LeadCapturedBy(BaseModel)`: `id: str`, `name: str`.
  - `LeadListItem`: `id`, `company_name`, `name`, `designation: str | None`, `status: LeadStatus`, `captured_at: datetime`, `captured_by: LeadCapturedBy`.
  - `LeadPage`: `items: list[LeadListItem]`, `total: int`, `next_cursor: str | None`.
- Produces, in `repository.py`:
  - `def _leads_in_scope(scope: ScopeContext, *, from_date: date | None, to_date: date | None, employee_id: str | None, q: str | None) -> Select[tuple[Lead]]`
    - Applies `apply_scope(select(Lead), scope, tenant_column=Lead.tenant_id, employee_id_column=Lead.captured_by_employee_id)` and `Lead.is_active.is_(True)`.
    - `business_date` bounds are inclusive.
    - `employee_id` → `captured_by_employee_id ==`.
    - `q` → `or_(Lead.company_name.icontains(q, autoescape=True), Lead.prospect_name.icontains(...), Lead.contact_email.icontains(...))`.
  - `def list_leads_in_scope(session, *, scope, from_date, to_date, employee_id, q, after: tuple[datetime, str] | None, limit: int) -> list[Lead]`
    - Ordered `occurred_at.desc(), id.desc()`.
    - `after` → `tuple_(Lead.occurred_at, Lead.id) < tuple_(*after)`.
  - `def count_leads_matching(session, *, scope, from_date, to_date, employee_id, q) -> int`
- Produces, in `service.py`:
  - `TargetService.list_leads(self, *, claims, from_date: date | None, to_date: date | None, employee_id: str | None, q: str | None, cursor: str | None, limit: int) -> dict[str, Any]`
    - Validates the range: copy `_validate_date_range` from `approvals/service.py:212` as a module function `_validate_lead_date_range`.
    - Validates `employee_id` via `org_service.get_employee_in_scope(self._session, scope=scope, employee_id=employee_id)`.
    - Decodes the cursor: copy `_encode_cursor`/`_decode_cursor` from `approvals/service.py:188-199` as `_encode_lead_cursor(lead)` / `_decode_lead_cursor(cursor)`, raising 422 `invalid_cursor`.
    - Resolves names with one `org_service.list_employee_names(...)` call for the page. A missing name → "Former employee".
    - `next_cursor` is set only when `len(items) == limit`.
- Route: `GET /leads`, `response_model=schemas.LeadPage`. Query params:
  - `from_date: date | None = Query(None, alias="from")`, `to_date: date | None = Query(None, alias="to")`
  - `employee_id: str | None = Query(None, min_length=26, max_length=26)`
  - `q: str | None = Query(None, max_length=120)`
  - `cursor: str | None = Query(None, max_length=64)`
  - `limit: int = Query(20, ge=1, le=50)`
  - The SDK name will be `listLeadsApiV1LeadsGet`.

- [ ] **Step 1: Write failing tests** in `test_leads.py`. Add a helper `_capture(client, company, **overrides) -> str` that posts and returns the id. Org fixture per test:
  - `admin = seed.employee(db,"admin")`
  - `m1 = seed.employee(db,"manager")`, `m2 = seed.employee(db,"manager", manager=m1)`
  - `so1 = seed.employee(db,"sales_person", manager=m1)`, `so2 = seed.employee(db,"sales_person", manager=m2)`
  - `m3 = seed.employee(db,"manager")`, `so3 = seed.employee(db,"sales_person", manager=m3)`
  - Leads captured by `so1`, `so2`, `m1`, `so3`.

  Check that admin seeding with no manager is valid; if `seed.employee(db, "admin")` fails, use `OrgService.create_admin` as `tests/invariants/test_scope_matrix.py` does.

  - `test_list_scope_by_role`:
    - `so1` sees exactly its own lead.
    - `m1` sees `so1`, `so2` (grand-report) and `m1`'s leads, but not `so3`'s.
    - `admin` sees all 4.
    - Each response's `total` equals its item count.
    - `captured_by.name` equals the employee's `full_name`.
  - `test_list_other_tenant_never_visible`: insert a `Lead` row directly with `repository.insert_lead(..., tenant_id="other-tenant", captured_by_employee_id=so1.id, ...)`. Admin's list excludes it.
  - `test_employee_filter_scope`:
    - `m1` with `employee_id=so2.id` → only `so2`'s lead.
    - `m1` with `employee_id=m1.id` → only `m1`'s.
    - `m1` with `employee_id=so3.id` → 404.
    - `so1` with `employee_id=so1.id` → 200.
    - `so1` with `employee_id=so2.id` → 404.
  - `test_date_range`:
    - Use the `travel` fixture to capture leads on two business dates.
    - `from`/`to` keeps only the matching date.
    - `from > to` → 422 `invalid_date_range`.
  - `test_search_matches_manufacturer_contact_email`: `q` on part of company_name, of contact name and of email each returns the lead; the matching ignores case.
  - `test_search_is_literal`: leads "100% Pure Oils" and "1000 Pure Oils". `q="100%"` returns only the first.
  - `test_cursor_paging_is_stable_on_ties`:
    - 5 leads captured with time frozen (`travel` with `tick=False`, or `time_machine.travel(NOW, tick=False)`) so `occurred_at` is equal.
    - Pages of `limit=2`, collecting ids, give 5 unique ids.
    - Last page `next_cursor is None`.
    - `total == 5` on every page.
  - `test_invalid_cursor_is_422`: `cursor="garbage"` → 422 `invalid_cursor`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/modules/targets/test_leads.py -q`. Expected: the new tests FAIL (404/405 on the route).
- [ ] **Step 3: Implement** the schemas, repository functions, service method and route above.
  - Declare `GET /leads` next to `POST /leads`.
  - Unparseable cursor timestamps raise 422. A cursor with no `|` should also 422 rather than query with an empty id.
- [ ] **Step 4: Run** `.venv/bin/pytest tests/modules/targets -q tests/invariants -q`. Expected: all PASS.
- [ ] **Step 5: Commit:** `PLAT-12366 feat(api): scoped, paged lead list`.

---

### Task 3: `GET /api/v1/leads/{id}` and `GET /api/v1/leads/counts-by-employee`

**Files:** same four API files + `test_leads.py`; regenerate the contract.

**Interfaces:**
- Consumes: Task 2's `_leads_in_scope`, `LeadCapturedBy`.
- Produces, in `schemas.py`:
  - `LeadCapturedByDetail(LeadCapturedBy)`: `employee_code: str | None`, `role_code: str | None`, `reports_to_name: str | None`.
  - `LeadDetailOut`: `id`, `name`, `designation`, `mobile: str` (E.164), `email`, `company_name`, `annual_turnover_cr: float | None`, `head_office_location: str | None`, `message: str | None`, `interest_level`, `status`, `captured_at`, `business_date: date`, `captured_by: LeadCapturedByDetail`.
  - `LeadEmployeeCount`: `employee_id`, `name`, `count: int`.
  - `LeadCountsByEmployee`: `items: list[LeadEmployeeCount]`.
- Produces, in `repository.py`:
  - `get_lead_in_scope(session, *, scope, lead_id) -> Lead | None` (active only)
  - `count_leads_by_employee(session, *, scope) -> list[tuple[str, int]]` (active only, all-time)
- Produces, in `service.py`:
  - `TargetService.get_lead(*, claims, lead_id) -> dict`
    - `None` → `ApiError(404, "lead_not_found", "Lead was not found.")`.
    - Mobile via `core.security.decrypt_phone(lead.contact_mobile_enc)`.
    - Capturer via `org_service.get_employee_dimension_fields(self._session, scope=internal_routing_scope(claims.tenant_id), employee_id=...)` (import `internal_routing_scope` from `modules.org.scope`).
    - Reports-to name via `org_service.list_employee_names` on its `manager_employee_id`.
    - Unresolvable capturer → name "Former employee", other fields `None`.
  - `TargetService.lead_counts_by_employee(*, claims) -> dict`. Names via `list_employee_names`; sorted by name.
- Routes:
  - `GET /leads/counts-by-employee` (declared **before** the detail route) → SDK `leadCountsByEmployeeApiV1LeadsCountsByEmployeeGet`.
  - `GET /leads/{lead_id:ulid}` → SDK `getLeadApiV1LeadsLeadIdGet`.
  - Path names may differ in generated output; use whatever the generator emits in Tasks 4–6.

- [ ] **Step 1: Write failing tests** (same org fixture; extract it into a module-level `_org(db)` helper returning a simple namespace):
  - `test_detail_in_scope_shows_full_mobile_and_capturer`:
    - `m1` opens `so2`'s lead → 200.
    - `mobile == "+919845012345"`.
    - `captured_by.employee_code == so2.employee_code`, `role_code == "sales_person"`, `reports_to_name == m2.full_name`.
  - `test_detail_out_of_scope_is_404`:
    - `m1` opens `so3`'s lead → 404 `lead_not_found`.
    - `so1` opens `so2`'s → 404.
    - An unknown ULID → 404.
  - `test_counts_by_employee_scoped`:
    - `m1` gets `{so1:1, so2:1, m1:1}`, without `so3`.
    - Admin gets all 4.
    - `so1` gets only itself.
  - `test_inactive_lead_hidden_everywhere`:
    - Set one lead's `is_active=False` + flush.
    - It is gone from the list items, `total`, counts and detail (404).
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `.venv/bin/pytest tests/modules/targets tests/invariants -q`. Expected: PASS.
- [ ] **Step 5: Regenerate the contract**. `check:breaking` must pass, since these are additive.
- [ ] **Step 6: Commit:** `PLAT-12366 feat(api): lead detail and per-employee lead counts`.

---

### Task 4: Web data layer

**Files:**
- Modify: `apps/web/src/features/leads/service.ts`
- Modify: `apps/web/src/features/leads/hooks.ts`
- Create: `apps/web/src/features/leads/filters.ts` (pure)
- Create: `apps/web/src/features/leads/format.ts` (pure)

**Interfaces:**
- Consumes: the Task 2–3 SDK functions and types `LeadPage`, `LeadListItem`, `LeadDetailOut`, `LeadCountsByEmployee`.
- Produces, in `filters.ts`:
  - `type LeadDateRange = "all" | "month" | "30" | "custom"`
  - `interface LeadFilters { q: string; range: LeadDateRange; from: string; to: string; employeeId: string }`. `employeeId` `""` = all.
  - `DEFAULT_LEAD_FILTERS`
  - `leadFiltersFromSearchParams(params: URLSearchParams): LeadFilters` and `leadFiltersToSearchParams(f: LeadFilters): URLSearchParams`. Keys: `q`, `range`, `from`, `to`, `emp`; defaults are omitted.
  - `resolveLeadDateWindow(f: LeadFilters, today: Date): { from?: string; to?: string }`
    - `month` = first of the month..today.
    - `30` = today−29..today.
    - `custom` passes through whichever bounds are set.
    - `all` = {}.
    - All values are ISO `YYYY-MM-DD` in local time.
  - `hasActiveLeadFilters(f): boolean`
- Produces, in `format.ts`:
  - `leadInitials(name: string): string` (≤2 letters)
  - `leadShortDate(iso: string, today: Date): string` ("Today" / "Yesterday" / "18 Nov")
  - `leadDateTime(iso: string): string` ("18 Nov 2026, 4:12 pm", `en-IN`)
  - `leadTurnover(cr: number | null): string | null` ("₹ 12.50 cr")
- Produces, in `service.ts`:
  - `leadsService.list(params: { from?; to?; employeeId?; q?; cursor?; limit? }, signal?)`
  - `leadsService.detail(id, signal?)`
  - `leadsService.countsByEmployee(signal?)`
- Produces, in `hooks.ts`:
  - `leadKeys = createActorQueryKeys("leads")` plus `list(actorId, filters)`, `detail(actorId, id)`, `counts(actorId)`.
  - `useLeads(filters: LeadFilters)`: `useInfiniteQuery`, limit 20, `getNextPageParam: last.next_cursor ?? undefined`. The search value passed in is already debounced by the screen.
  - `useLead(id: string)`
  - `useLeadCountsByEmployee(enabled: boolean)`
  - `useCaptureLead` gains `invalidate` of `leadKeys.all(actorId)`. Follow `useAppMutation`'s `invalidate` option in `shared/state/mutations.ts`.
  - Use `useActorId()` the way `management/organization-hooks.ts` does.

- [ ] **Step 1:** There is no web test runner (spec: CI runs lint/typecheck/build only), so verify the pure functions with a throwaway `node --experimental-strip-types` script in the scratchpad. Cover:
  - `resolveLeadDateWindow` for each range with `today = 2026-11-20`: `month` → `{from:"2026-11-01",to:"2026-11-20"}`; `30` → `{from:"2026-10-22",to:"2026-11-20"}`.
  - The search-params round-trip.
  - `leadShortDate` for today, yesterday and older.

  Do not commit the script.
- [ ] **Step 2: Implement** the four files.
- [ ] **Step 3: Run** the script. Expected: all asserts pass. Run web tsc + eslint. Expected: clean.
- [ ] **Step 4: Commit:** `PLAT-12366 feat(web): leads data layer`.

---

### Task 5: SO screens — My leads + Lead details

**Files:**
- Create: `apps/web/app/(sp)/sp/leads/page.tsx` → `<MyLeadsScreen />`
- Create: `apps/web/app/(sp)/sp/leads/detail/page.tsx` → `<LeadDetailScreen />` (wrap in `Suspense` the way `app/(sp)/sp/orders/detail/page.tsx` does for `useSearchParams`)
- Create: `apps/web/src/features/leads/list-parts.tsx`
- Create: `apps/web/src/features/leads/detail-parts.tsx`
- Create: `apps/web/src/features/leads/leads.module.css` (token vars only)
- Modify: `apps/web/src/features/leads/screens.tsx`
  - Add `MyLeadsScreen` and `LeadDetailScreen`.
  - On capture success: `router.replace("/sp/leads")`.
- Modify: `apps/web/src/features/more/screens.tsx:31-38`. Add `{ label: "My leads", href: "/sp/leads" }` after "Capture lead", matching the existing item shape and icon style.
- Modify: `apps/web/src/features/shell/components.tsx`. In `activeTab`, `/sp/leads` → `"more"`.

**Interfaces:**
- Consumes: Task 4 hooks/filters/format.
- Produces, shared parts reused by Task 6:
  - `LeadFilterBar({ filters, onChange, employeeSlot?: ReactNode })`: search `TextField` + date chips + custom `DateField` pair (To ≤ today, From ≤ To).
  - `LeadListBody({ query, showCapturer, onOpen, emptyState, onClearFilters, filtersActive })`: count line, `ListRow` list, Load more `Button` + `useInfiniteScrollTrigger`, skeleton/error/empty/no-match states.
  - `LeadDetailBody({ lead, viewerIsCapturer })`: header card with `StatusChip`, Call (`tel:`) and Email (`mailto:`) `Button`s, sections Manufacturer, Contact, Message, Captured by.

  Shell-neutral: these take no `Sp*` or `Management*` wrappers.

- [ ] **Step 1:** Read the `.prompt.md` for `ListRow`, `StatusChip`, `TextField`, `DateField`, `Button`, `Feedback` (EmptyState/ErrorState), `Overlays` (BottomSheet) and `Skeleton`. Read `next/dist/docs` on `useSearchParams` under static export.
- [ ] **Step 2: Implement the parts and the SO screens** to match the prototype's SO view.
  - Filters sync to the URL via `router.replace("/sp/leads?" + params)`.
  - Search is debounced with `useDebouncedSearchQuery`.
  - Use SP shell pieces (`SpScreen`, `SpSectionLabel`, `SpCard`) and `.sp-filter-bar` / `.sp-filter-chip` for the date chips.
  - Add a floating "Capture lead" `Button` linking to `/sp/leads/new`.
- [ ] **Step 3: Run** web tsc + eslint + build. Expected: clean, with `/sp/leads` and `/sp/leads/detail` in the build output.
- [ ] **Step 4: Manual check** against the local API on this branch's code:
  - Capture a lead → you land on My leads with it first.
  - Search, the date chips and Load more (seed >20) work.
  - Detail shows the full mobile.
  - `?id=<someone else's>` → "Lead not found".
- [ ] **Step 5: Commit:** `PLAT-12366 feat(web): My leads list and detail for sales officers`.

---

### Task 6: Manager/Admin screens — Leads + Lead details

**Files:**
- Modify: `apps/web/src/features/management/service.ts`. Add `"leads" | "lead"` to `ManagementView` and to `managementViews`.
- Modify: `apps/web/src/features/management/ui.tsx`.
  - `viewTitles`: `leads: "Leads"`, `lead: "Lead details"`.
  - `activeTab`: both → `"more"`.
- Modify: `apps/web/src/features/management/screens.tsx`.
  - Add `case "leads"` / `case "lead"` in `ManagementFeaturePage`.
  - Add `{ icon: <match neighbours>, label: "Leads", href: "/mgmt/leads" }` to the Operations group of both `managerGroups` and `adminGroups`.
- Create: `apps/web/src/features/leads/management-screens.tsx` with `ManagementLeadsScreen`, `ManagementLeadDetailScreen` and `CapturedBySheet`. A separate file keeps `screens.tsx`, already 4k+ lines, from growing.

**Interfaces:**
- Consumes:
  - Task 5 parts.
  - `useEmployees({ status: "active" })` from `management/organization-hooks.ts`.
  - `useLeadCountsByEmployee(true)`.
  - `useManagementRole()` (`isAdmin`).
  - `useManagementRouter`.
  - The session's own employee id: use the same `useActorId()` as hooks.
- `CapturedBySheet({ open, value, onSelect, onClose })` options, in order:
  1. All. Label "All employees" (admin) / "All my team" (manager). Count = sum of counts.
  2. Manager only: "Me (my own leads)", count from counts.
  3. Active employees sorted by name. Row shows `full_name`, subtitle `employee_code · role · reports to <name|You>`, and count (0 if absent).
  4. Group "Former employees": ids in counts but not in the active list, by `name`.

  Search filters name or code. Build it from the DS `BottomSheet` + `TextField` + `ListRow`, or `Select searchable` if its API supports the subtitle and count. Pick whichever the `.prompt.md` supports without custom styling.
  - Trigger: a field-styled button labelled "Captured by" showing the current choice, with a clear (×) `IconButton` when set.

- [ ] **Step 1: Implement** to match the prototype's Manager and Admin views.
  - Rows show "captured by <name>" ("You" for own).
  - Detail "Captured by" shows Employee (name + code · role), Reports to, and Date & time.
  - Filters sync to the URL (`/mgmt/leads?…`), and the detail link is `/mgmt/lead?id=`.
- [ ] **Step 2: Run** web tsc + eslint + build. Expected: clean; `admin/leads`, `admin/lead`, `manager/leads`, `manager/lead` are generated.
- [ ] **Step 3: Manual check** with the seed org from Task 2 (admin, m1 → m2 → so2, so1, m3 → so3):
  - m1 sees so1/so2/own and not so3.
  - The sheet lists so1, m2, so2 with counts, plus "Me".
  - Picking so2 filters the list.
  - Admin sees all.
  - `?id=` of so3's lead as m1 → "Lead not found".
- [ ] **Step 4: Commit:** `PLAT-12366 feat(web): Leads list and detail for managers and admins`.

---

### Task 7: Final verification

- [ ] **Step 1:** `cd apps/api && .venv/bin/pytest -q`. Expected: full suite passes.
- [ ] **Step 2:** Contract regen produces no diff (`npm run check` in `packages/api-contract`), and `check:breaking` passes.
- [ ] **Step 3:** Web tsc + eslint + build are clean.
- [ ] **Step 4:** Grep the new web files for literal colours. Expected: no matches.

  ```
  grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(" apps/web/src/features/leads/*.css apps/web/src/features/leads/*.tsx
  ```

- [ ] **Step 5:** Compare each role's screens side by side with the prototype; list any deviation in the PR description.
