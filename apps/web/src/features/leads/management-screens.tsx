"use client";

import {
  BottomSheet,
  EmptyState,
  ErrorState,
  Icon,
  IconButton,
  ListRow,
  SkeletonRow,
  TextField,
} from "humbee-design-system";
import type { EmployeeResponse } from "@humbee/api-contract";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type ChangeEvent, type KeyboardEvent, type ReactNode } from "react";
import { ApiClientError } from "@/src/shared/api";
import { useConnectivity } from "@/src/shared/capabilities";
import { useDebouncedSearchQuery } from "@/src/shared/state";
import { useEmployees } from "@/src/features/management/organization-hooks";
import { useManagementRole, useManagementRouter } from "@/src/features/management/role-context";
import { ManagementScreen } from "@/src/features/management/ui";
import managementStyles from "@/src/features/management/management.module.css";
import { LeadDetailBody } from "./detail-parts";
import {
  DEFAULT_LEAD_FILTERS,
  hasActiveLeadFilters,
  leadFiltersFromSearchParams,
  leadFiltersToSearchParams,
  type LeadFilters,
} from "./filters";
import { leadRoleLabel } from "./format";
import { useActorId, useLead, useLeadCountsByEmployee, useLeads } from "./hooks";
import { LeadFilterBar, LeadInitials, LeadListBody } from "./list-parts";
import type { LeadEmployeeCount } from "./service";
import styles from "./leads.module.css";

const LEADS_PATH = "/mgmt/leads";
const ME_LABEL = "Me (my own leads)";

function allLabel(isAdmin: boolean) {
  return isAdmin ? "All employees" : "All my team";
}

interface CapturerOption {
  id: string;
  name: string;
  subtitle: string;
  code: string;
  count: number;
}

/** Sheet + trigger data: active employees, the viewer, and former capturers, each with an all-time count. */
function useCapturerOptions() {
  const { isAdmin } = useManagementRole();
  const actorId = useActorId();
  const employees = useEmployees({ status: "active" });
  const counts = useLeadCountsByEmployee(true);

  return useMemo(() => {
    const countItems: LeadEmployeeCount[] = counts.data?.items ?? [];
    const countById = new Map(countItems.map((item) => [item.employee_id, item]));
    const active: EmployeeResponse[] = employees.data?.items ?? [];
    const activeById = new Map(active.map((employee) => [employee.id, employee]));

    const reportsTo = (managerId: string | null) => {
      if (!managerId) return "";
      if (managerId === actorId) return "You";
      return activeById.get(managerId)?.full_name ?? "";
    };

    const team: CapturerOption[] = active
      .filter((employee) => employee.id !== actorId)
      .map((employee) => {
        const boss = reportsTo(employee.manager_employee_id);
        return {
          id: employee.id,
          name: employee.full_name,
          code: employee.employee_code,
          subtitle: [employee.employee_code, leadRoleLabel(employee.role_code), boss ? `reports to ${boss}` : ""]
            .filter(Boolean)
            .join(" · "),
          count: countById.get(employee.id)?.count ?? 0,
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name));

    const former: CapturerOption[] = countItems
      .filter((item) => item.employee_id !== actorId && !activeById.has(item.employee_id))
      .map((item) => ({ id: item.employee_id, name: item.name, code: "", subtitle: "", count: item.count }))
      .sort((a, b) => a.name.localeCompare(b.name));

    return {
      isAdmin,
      actorId,
      team,
      former,
      total: countItems.reduce((sum, item) => sum + item.count, 0),
      myCount: countById.get(actorId)?.count ?? 0,
      ready: employees.isSuccess && counts.isSuccess,
      isPending: employees.isPending || counts.isPending,
      isError: employees.isError || counts.isError,
      retry: () => {
        if (employees.isError) void employees.refetch();
        if (counts.isError) void counts.refetch();
      },
      nameFor: (id: string) =>
        activeById.get(id)?.full_name ?? countById.get(id)?.name ?? null,
    };
  }, [actorId, counts, employees, isAdmin]);
}

function matches(option: CapturerOption, q: string) {
  return option.name.toLowerCase().includes(q) || option.code.toLowerCase().includes(q);
}

function OptionRow({
  label,
  subtitle,
  count,
  leading,
  selected,
  onSelect,
}: {
  label: string;
  subtitle?: string;
  count: number;
  leading: ReactNode;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <ListRow
      leading={leading}
      title={label}
      subtitle={subtitle || undefined}
      meta={String(count)}
      trailing={selected ? <Icon name="Check" size={20} color="var(--color-primary)" /> : undefined}
      onClick={onSelect}
    />
  );
}

export function CapturedBySheet({
  open,
  value,
  onSelect,
  onClose,
}: {
  open: boolean;
  value: string;
  onSelect: (employeeId: string) => void;
  onClose: () => void;
}) {
  // Same cached queries as the screen's trigger label; React Query dedupes them.
  const options = useCapturerOptions();
  const [search, setSearch] = useState("");
  const q = search.trim().toLowerCase();
  const close = () => {
    setSearch("");
    onClose();
  };
  const pick = (id: string) => {
    setSearch("");
    onSelect(id);
  };

  const team = options.team.filter((option) => !q || matches(option, q));
  const former = options.former.filter((option) => !q || matches(option, q));

  let body: ReactNode;
  if (options.isPending) {
    body = Array.from({ length: 4 }, (_, index) => <SkeletonRow key={index} />);
  } else if (options.isError && !options.ready) {
    body = (
      <ErrorState
        title="Couldn't load employees"
        message="Check your connection and try again."
        retryLabel="Try again"
        onRetry={options.retry}
      />
    );
  } else {
    body = (
      <>
        {!q ? (
          <>
            <OptionRow
              label={allLabel(options.isAdmin)}
              count={options.total}
              leading={<Icon name="Group" size={24} color="var(--color-primary)" />}
              selected={value === ""}
              onSelect={() => pick("")}
            />
            {!options.isAdmin ? (
              <OptionRow
                label={ME_LABEL}
                count={options.myCount}
                leading={<Icon name="PersonRounded" size={24} color="var(--color-primary)" />}
                selected={value === options.actorId}
                onSelect={() => pick(options.actorId)}
              />
            ) : null}
          </>
        ) : null}
        {team.length ? (
          <>
            <h3 className={styles.sectionLabel}>{options.isAdmin ? "Employees" : "My team"}</h3>
            {team.map((option) => (
              <OptionRow
                key={option.id}
                label={option.name}
                subtitle={option.subtitle}
                count={option.count}
                leading={<LeadInitials name={option.name} />}
                selected={value === option.id}
                onSelect={() => pick(option.id)}
              />
            ))}
          </>
        ) : null}
        {former.length ? (
          <>
            <h3 className={styles.sectionLabel}>Former employees</h3>
            {former.map((option) => (
              <OptionRow
                key={option.id}
                label={option.name}
                count={option.count}
                leading={<LeadInitials name={option.name} />}
                selected={value === option.id}
                onSelect={() => pick(option.id)}
              />
            ))}
          </>
        ) : null}
        {q && !team.length && !former.length ? (
          <p className={styles.endNote}>No employee matches “{search.trim()}”.</p>
        ) : null}
      </>
    );
  }

  return (
    <BottomSheet open={open} onClose={close} title="Captured by">
      <div className={styles.sheetBody}>
        <TextField
          placeholder="Search name or code"
          fullWidth
          value={search}
          startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
          inputProps={{
            "aria-label": "Search employees",
            type: "search",
            autoComplete: "off",
            autoCapitalize: "none",
            autoCorrect: "off",
          }}
          onChange={(event: ChangeEvent) => setSearch((event.target as HTMLInputElement).value)}
        />
        <div className={styles.sheetOptions}>
          {body}
        </div>
      </div>
    </BottomSheet>
  );
}

function CapturedByTrigger({
  label,
  isSet,
  open,
  onOpen,
  onClear,
}: {
  label: string;
  isSet: boolean;
  open: boolean;
  onOpen: () => void;
  onClear: () => void;
}) {
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen();
    }
  };
  return (
    <TextField
      label="Captured by"
      fullWidth
      value={label}
      startAdornment={<Icon name="PersonRounded" size={20} color="var(--color-text-secondary)" />}
      endAdornment={isSet ? (
        <IconButton
          icon={(
            <>
              <Icon name="Close" size={20} color="currentColor" />
              <span className={styles.visuallyHidden}>Clear employee</span>
            </>
          )}
          color="neutral"
          onClick={onClear}
          style={{ width: 32, height: 32 }}
        />
      ) : (
        <Icon name="KeyboardArrowDown" size={20} color="var(--color-text-secondary)" />
      )}
      inputProps={{
        readOnly: true,
        role: "button",
        "aria-haspopup": "dialog",
        "aria-expanded": open,
        "aria-label": `Captured by: ${label}`,
        className: styles.pickerInput,
        onClick: onOpen,
        onKeyDown,
      }}
    />
  );
}

export function ManagementLeadsScreen() {
  const router = useManagementRouter();
  const searchParams = useSearchParams();
  const { isOnline } = useConnectivity();
  const options = useCapturerOptions();
  const [sheetOpen, setSheetOpen] = useState(false);
  // Local state is the source of truth; the URL mirrors it so filters survive opening a lead.
  const [filters, setFilters] = useState<LeadFilters>(
    () => leadFiltersFromSearchParams(new URLSearchParams(searchParams.toString())),
  );
  const debouncedQ = useDebouncedSearchQuery(filters.q);
  const applied = useMemo(() => ({ ...filters, q: debouncedQ }), [filters, debouncedQ]);
  const leads = useLeads(applied);
  const filtersActive = hasActiveLeadFilters(applied);

  useEffect(() => {
    const query = leadFiltersToSearchParams(applied).toString();
    if (query === window.location.search.replace(/^\?/, "")) return;
    router.replace(query ? `${LEADS_PATH}?${query}` : LEADS_PATH, { scroll: false });
  }, [applied, router]);

  const employeeId = filters.employeeId;
  const isMe = employeeId !== "" && employeeId === options.actorId;
  const selectedName = employeeId && !isMe
    ? options.nameFor(employeeId) ?? (options.ready ? "Former employee" : "…")
    : null;
  const triggerLabel = employeeId === "" ? allLabel(options.isAdmin) : isMe ? ME_LABEL : selectedName ?? "";
  const countSuffix = employeeId === "" ? undefined : isMe ? "by you" : `by ${selectedName}`;

  const setEmployee = (id: string) => setFilters((current) => ({ ...current, employeeId: id }));
  const clearFilters = () => setFilters(DEFAULT_LEAD_FILTERS);

  return (
    <ManagementScreen view="leads" offline={!isOnline}>
      <div className={managementStyles.content}>
        <LeadFilterBar
          filters={filters}
          onChange={setFilters}
          employeeSlot={(
            <CapturedByTrigger
              label={triggerLabel}
              isSet={employeeId !== ""}
              open={sheetOpen}
              onOpen={() => setSheetOpen(true)}
              onClear={() => setEmployee("")}
            />
          )}
        />
        <LeadListBody
          query={leads}
          showCapturer
          onOpen={(id) => router.push(`/mgmt/lead?id=${encodeURIComponent(id)}`)}
          emptyState={(
            <EmptyState
              icon="FormatListBulleted"
              title="No leads yet"
              message={options.isAdmin
                ? "No one in the organisation has captured a lead yet."
                : "No one in your team has captured a lead yet."}
            />
          )}
          onClearFilters={clearFilters}
          filtersActive={filtersActive}
          countSuffix={countSuffix}
        />
      </div>
      <CapturedBySheet
        open={sheetOpen}
        value={employeeId}
        onClose={() => setSheetOpen(false)}
        onSelect={(id) => {
          setEmployee(id);
          setSheetOpen(false);
        }}
      />
    </ManagementScreen>
  );
}

function isNotFound(error: unknown) {
  return error instanceof ApiClientError && error.status === 404;
}

export function ManagementLeadDetailScreen() {
  const router = useManagementRouter();
  const searchParams = useSearchParams();
  const { isOnline } = useConnectivity();
  const leadId = searchParams.get("id") ?? "";
  const lead = useLead(leadId);

  let body: ReactNode;
  if (!leadId || (lead.isError && isNotFound(lead.error))) {
    body = (
      <EmptyState
        icon="Warning"
        title="Lead not found"
        message="This lead doesn't exist or isn't in your scope."
        actionLabel="Back to leads"
        onAction={() => router.replace(LEADS_PATH)}
      />
    );
  } else if (lead.isPending) {
    body = (
      <div aria-busy="true" aria-label="Loading lead">
        {Array.from({ length: 4 }, (_, index) => <SkeletonRow key={index} />)}
      </div>
    );
  } else if (lead.isError) {
    body = (
      <ErrorState
        title="Couldn't load this lead"
        message="Check your connection and try again."
        retryLabel="Try again"
        onRetry={() => void lead.refetch()}
      />
    );
  } else {
    body = <LeadDetailBody lead={lead.data} viewerIsCapturer={false} />;
  }

  return (
    <ManagementScreen view="lead" offline={!isOnline}>
      <div className={managementStyles.content}>{body}</div>
    </ManagementScreen>
  );
}
