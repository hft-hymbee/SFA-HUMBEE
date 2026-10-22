"use client";

import {
  BottomSheet,
  Button,
  Checkbox,
  EmptyState,
  ErrorState,
  Icon,
  Skeleton,
  StatusChip,
  TextField,
} from "humbee-design-system";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import type { EmployeeResponse } from "@humbee/api-contract";
import { ApiClientError } from "@/src/shared/api";
import { mutationErrorMessage } from "@/src/shared/state";
import { useEmployee } from "@/src/features/management/organization-hooks";
import { useManagementRole, useManagementRouter as useRouter } from "@/src/features/management/role-context";
import { DataRow, ManagementScreen, Notice, Section } from "@/src/features/management/ui";
import styles from "@/src/features/management/management.module.css";
import {
  OUTLET_CATEGORY_OPTIONS,
  buildCreateTargetBody,
  buildUpdateTargetBody,
  draftFromTargets,
  hasTargetDraftErrors,
  isTargetType,
  lineUnitLabel,
  parsePositiveInteger,
  salesTargetTotals,
  selectedSalesLines,
  syncSalesLinesWithManufacturers,
  validateTargetDraft,
  type TargetFormDraft,
  type TargetFormErrors,
} from "./form-state";
import {
  useCreateTarget,
  useEmployeeTargets,
  useRemoveTarget,
  useTargetManufacturers,
  useTargetRoster,
  useUpdateTarget,
} from "./hooks";
import {
  currentPeriodMonth,
  formatPeriodMonth,
  formatTargetValue,
  nextPeriodMonth,
  TARGET_TYPE_LABELS,
  type ManufacturerOut,
  type TargetOut,
  type TargetRosterMember,
  type TargetType,
} from "./service";

const TYPE_SEGMENT: Array<{ label: string; value: TargetType }> = [
  { label: "Sales", value: "sales" },
  { label: "Outlets", value: "outlets" },
  { label: "Leads", value: "leads" },
];

function employeeRoleLabel(roleCode: string) {
  if (roleCode === "admin") return "Admin";
  if (roleCode === "manager") return "Manager";
  return "Sales Person";
}

function targetCountLabel(count: number) {
  if (count <= 0) return "No target";
  return count === 1 ? "1 target" : `${count} targets`;
}

function targetEditHref(employeeId: string, periodMonth: string, targetType?: TargetType) {
  const params = new URLSearchParams({
    employeeId,
    periodMonth,
  });
  if (targetType) params.set("type", targetType);
  return `/mgmt/target-edit?${params.toString()}`;
}

function periodOptions(periodMonth = currentPeriodMonth()) {
  const next = nextPeriodMonth(periodMonth);
  return [
    { value: periodMonth, label: formatPeriodMonth(periodMonth) },
    { value: next, label: formatPeriodMonth(next) },
  ];
}

function salesStripValue(draft: TargetFormDraft, manufacturers: ManufacturerOut[]) {
  const totals = salesTargetTotals(draft, manufacturers);
  return {
    amount: totals.amountPaise === null ? null : formatTargetValue(totals.amountPaise, "amount"),
    volume: totals.volumeUnits === null ? null : `${formatTargetValue(totals.volumeUnits, "volume")} units`,
    selectedCount: totals.selectedCount,
    totalCount: totals.totalCount,
  };
}

const COUNT_CHIP_STYLE = {
  fontSize: "var(--text-caption-size)",
  lineHeight: "var(--text-body-line)",
  padding: "0 var(--space-sm)",
} as const;

export function TargetsScreen() {
  const router = useRouter();
  const { isAdmin } = useManagementRole();
  const periodMonth = currentPeriodMonth();
  const roster = useTargetRoster(periodMonth);
  const members = roster.data?.members ?? [];
  const [pickerOpen, setPickerOpen] = useState(false);
  const withTarget = roster.data?.with_target ?? 0;
  const total = roster.data?.total ?? 0;

  return (
    <ManagementScreen
      view="targets"
      footer={(
        <Button
          variant="filled"
          color="primary"
          label="Set target"
          disabled={!members.length}
          onClick={() => setPickerOpen(true)}
        />
      )}
    >
      <div className={styles.content}>
        <div className={`${styles.card} ${styles.targetContextCard}`}>
          <p className={styles.sectionLabel}>Target context</p>
          <p className={styles.targetContextCopy}>
            Track sales, outlet, and lead targets across sales people and managers in your reporting line.
          </p>
          {roster.isPending ? (
            <Skeleton height={22} radius={6} />
          ) : roster.data ? (
            <p className={styles.targetContextStat}>
              <strong>{withTarget} / {total}</strong>
              <span>have a target set for {formatPeriodMonth(periodMonth)}</span>
            </p>
          ) : null}
        </div>
        {isAdmin ? null : (
          <Section label="Progress">
            <div className={styles.card}>
              <DataRow
                icon="Dashboard"
                title="Team progress against target"
                subtitle="Booked versus target for everyone in your reporting line"
                onClick={() => router.push("/mgmt/team-performance")}
              />
            </div>
          </Section>
        )}
        <Section label="Team">
          {roster.isPending ? (
            <>
              <Skeleton height={72} radius={12} />
              <Skeleton height={72} radius={12} />
              <Skeleton height={72} radius={12} />
            </>
          ) : roster.isError ? (
            <ErrorState
              title="Team unavailable"
              message="The target list could not load people in your reporting line."
              onRetry={() => { void roster.refetch(); }}
            />
          ) : members.length ? (
            <div className={`${styles.card} ${styles.targetTeamCard}`}>
              {members.map((member) => (
                <TargetMemberRow
                  key={member.employee_id}
                  member={member}
                  periodMonth={periodMonth}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              icon="PersonRounded"
              title="No people in your reporting line"
              message="Targets can be set once sales people or managers are active in your scope."
              actionLabel="Open employees"
              onAction={() => router.push("/mgmt/employees")}
            />
          )}
        </Section>
      </div>
      <BottomSheet open={pickerOpen} onClose={() => setPickerOpen(false)} title="Set target">
        <div className={styles.targetTeamCard}>
          {members.map((member) => (
            <TargetMemberRow
              key={member.employee_id}
              member={member}
              periodMonth={periodMonth}
              onPick={() => setPickerOpen(false)}
            />
          ))}
        </div>
      </BottomSheet>
    </ManagementScreen>
  );
}

function TargetMemberRow({
  member,
  periodMonth,
  onPick,
}: {
  member: TargetRosterMember;
  periodMonth: string;
  onPick?: () => void;
}) {
  const router = useRouter();
  const href = targetEditHref(member.employee_id, periodMonth);
  const count = member.active_target_count;

  return (
    <button
      className={styles.targetMemberRow}
      onClick={() => {
        onPick?.();
        router.push(href);
      }}
      type="button"
    >
      <span className={styles.avatar}>{member.display_initials}</span>
      <span className={styles.targetMemberCopy}>
        <strong className="hb-heading">{member.full_name}</strong>
        <span>{employeeRoleLabel(member.role_code)}</span>
        {member.zone_label ? <span>{member.zone_label}</span> : null}
      </span>
      <span className={styles.targetMemberMeta}>
        <StatusChip
          status={count > 0 ? "verified" : "default"}
          label={targetCountLabel(count)}
          type="outlined"
          style={COUNT_CHIP_STYLE}
        />
        <Icon name="KeyboardArrowRight" size={20} color="var(--color-text-placeholder)" />
      </span>
    </button>
  );
}

export function TargetEditScreen() {
  const searchParams = useSearchParams();
  const requestedType = searchParams.get("type");
  const [targetType, setTargetType] = useState<TargetType>(() => (
    isTargetType(requestedType) ? requestedType : "sales"
  ));
  const [periodMonth, setPeriodMonth] = useState(searchParams.get("periodMonth") ?? currentPeriodMonth());
  const employeeId = searchParams.get("employeeId") ?? "";
  const employee = useEmployee(employeeId);
  const employeeTargets = useEmployeeTargets(employeeId ? { employeeId, periodMonth } : null);
  const manufacturers = useTargetManufacturers();
  const manufacturerRows = useMemo(() => manufacturers.data?.manufacturers ?? [], [manufacturers.data?.manufacturers]);
  const targetRows = useMemo(() => employeeTargets.data?.targets ?? [], [employeeTargets.data?.targets]);
  const existingTarget = targetRows.find((target) => target.target_type === targetType) ?? null;
  const initialDraft = useMemo(
    () => syncSalesLinesWithManufacturers(
      draftFromTargets(employeeId, periodMonth, targetType, targetRows, manufacturerRows),
      manufacturerRows,
    ),
    [employeeId, periodMonth, targetType, targetRows, manufacturerRows],
  );

  if (!employeeId) {
    return (
      <ManagementScreen view="target-edit">
        <div className={styles.content}>
          <EmptyState
            icon="PersonRounded"
            title="Select a person"
            message="Choose someone from the team list to set a target."
          />
        </div>
      </ManagementScreen>
    );
  }

  if (employee.isPending || (employeeTargets.isPending && !employeeTargets.data)) {
    return (
      <ManagementScreen view="target-edit">
        <div className={styles.content}>
          <Skeleton height={92} radius={12} />
          <Skeleton height={180} radius={12} />
        </div>
      </ManagementScreen>
    );
  }

  if (employee.isError) {
    return (
      <ManagementScreen view="target-edit">
        <div className={styles.content}>
          <ErrorState
            title="Person unavailable"
            message="This person could not be loaded in your reporting line."
            onRetry={() => { void employee.refetch(); }}
          />
        </div>
      </ManagementScreen>
    );
  }

  if (employeeTargets.isError) {
    return (
      <ManagementScreen view="target-edit">
        <div className={styles.content}>
          <ErrorState
            title="Target unavailable"
            message="Existing targets for this person could not be loaded."
            onRetry={() => { void employeeTargets.refetch(); }}
          />
        </div>
      </ManagementScreen>
    );
  }

  return (
    <TargetEditForm
      key={`${employeeId}-${periodMonth}`}
      draft={initialDraft}
      employee={employee.data ?? null}
      existingTarget={existingTarget}
      loadingTarget={employeeTargets.isPending}
      manufacturers={manufacturerRows}
      rosterError={manufacturers.isError}
      rosterLoading={manufacturers.isPending}
      targets={employeeTargets.data?.targets ?? []}
      onPeriodMonthChange={setPeriodMonth}
      onTargetTypeChange={setTargetType}
      onTargetRefetch={() => { void employeeTargets.refetch(); }}
    />
  );
}

function TargetEditForm({
  draft: initialDraft,
  employee,
  existingTarget,
  loadingTarget,
  manufacturers,
  rosterError,
  rosterLoading,
  targets,
  onPeriodMonthChange,
  onTargetTypeChange,
  onTargetRefetch,
}: {
  draft: TargetFormDraft;
  employee: EmployeeResponse | null;
  existingTarget: TargetOut | null;
  loadingTarget: boolean;
  manufacturers: ManufacturerOut[];
  rosterError: boolean;
  rosterLoading: boolean;
  targets: TargetOut[];
  onPeriodMonthChange: (periodMonth: string) => void;
  onTargetTypeChange: (targetType: TargetType) => void;
  onTargetRefetch: () => void;
}) {
  const router = useRouter();
  const createTarget = useCreateTarget();
  const updateTarget = useUpdateTarget();
  const removeTarget = useRemoveTarget();
  const [draft, setDraft] = useState(initialDraft);
  const [errors, setErrors] = useState<TargetFormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [removeOpen, setRemoveOpen] = useState(false);
  const [periodOpen, setPeriodOpen] = useState(false);
  const manufacturerIds = manufacturers.map((item) => item.manufacturer_id).join(",");
  const [rosterSignature, setRosterSignature] = useState(manufacturerIds);
  if (manufacturerIds !== rosterSignature) {
    setRosterSignature(manufacturerIds);
    if (manufacturers.length) {
      setDraft((current) => syncSalesLinesWithManufacturers(current, manufacturers));
    }
  }
  const pending = createTarget.isPending || updateTarget.isPending || removeTarget.isPending;
  const currentTarget = targets.find((target) => target.target_type === draft.targetType) ?? existingTarget;
  const saveDisabled = pending || loadingTarget || !draft.employeeId || (draft.targetType === "sales" && rosterError);
  const roleLabel = employee ? employeeRoleLabel(employee.role_code) : "Person";

  const updateDraft = (patch: Partial<TargetFormDraft>) => {
    setDraft((current) => ({ ...current, ...patch }));
    setErrors({});
    setSubmitError(null);
  };
  const handleError = (error: Error) => {
    setSubmitError(mutationErrorMessage(error));
    if (error instanceof ApiClientError && error.code === "target_already_set") {
      onTargetRefetch();
    }
  };
  const handleSuccess = () => router.push("/mgmt/targets");
  const save = () => {
    const nextErrors = validateTargetDraft(draft);
    setErrors(nextErrors);
    setSubmitError(null);
    if (hasTargetDraftErrors(nextErrors)) return;
    if (currentTarget) {
      updateTarget.mutate(
        { body: buildUpdateTargetBody(draft, currentTarget.version), targetId: currentTarget.id },
        { onError: handleError, onSuccess: handleSuccess },
      );
      return;
    }
    createTarget.mutate(
      { body: buildCreateTargetBody(draft) },
      { onError: handleError, onSuccess: handleSuccess },
    );
  };
  const remove = () => {
    if (!currentTarget) return;
    removeTarget.mutate(
      { targetId: currentTarget.id },
      { onError: handleError, onSuccess: handleSuccess },
    );
  };
  const selectType = (nextType: TargetType) => {
    if (nextType === "sales" && rosterError) return;
    updateDraft({ targetType: nextType });
    onTargetTypeChange(nextType);
  };

  return (
    <ManagementScreen
      view="target-edit"
      footer={(
        <>
          <Button
            variant="outlined"
            color="neutral"
            label="Remove"
            disabled={!currentTarget || pending}
            onClick={() => setRemoveOpen(true)}
          />
          <Button
            variant="filled"
            color="primary"
            label={pending ? "Saving..." : "Save target"}
            disabled={saveDisabled}
            onClick={save}
          />
        </>
      )}
    >
      <div className={`${styles.content} ${styles.targetFormContent}`}>
        <div className={styles.targetHero}>
          <div className={styles.leadingIcon}>
            <Icon name="RewardsOutlined" size={22} color="var(--color-primary)" />
          </div>
          <div className={styles.targetHeroCopy}>
            <p>{currentTarget ? "Edit target plan" : "New target plan"}</p>
            <h2>{TARGET_TYPE_LABELS[draft.targetType]}</h2>
            <strong>{employee?.full_name ?? "Person unavailable"}</strong>
            <span>{roleLabel} · {formatPeriodMonth(draft.periodMonth)}</span>
          </div>
          <StatusChip
            status={currentTarget ? "verified" : "default"}
            label={currentTarget ? "Configured" : "Draft"}
            type="outlined"
            style={COUNT_CHIP_STYLE}
          />
        </div>
        {submitError ? <Notice tone="warning">{submitError}</Notice> : null}
        <Section label="Target selection">
          <div className={`${styles.card} ${styles.targetPlannerCard} ${styles.targetCompactCard}`}>
            <button className={styles.targetPeriodPill} onClick={() => setPeriodOpen(true)} type="button">
              <span>{formatPeriodMonth(draft.periodMonth)}</span>
              <Icon name="KeyboardArrowDown" size={18} color="var(--color-text-primary)" />
            </button>
            <div className={styles.targetSegment}>
              {TYPE_SEGMENT.map((item) => {
                const disabled = item.value === "sales" && rosterError;
                return (
                  <button
                    className={styles.targetSegmentItem}
                    data-active={draft.targetType === item.value}
                    disabled={disabled}
                    key={item.value}
                    onClick={() => selectType(item.value)}
                    type="button"
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        </Section>
        {loadingTarget ? (
          <Skeleton height={160} radius={12} />
        ) : draft.targetType === "sales" ? (
          <SalesTargetFields
            draft={draft}
            errors={errors}
            manufacturers={manufacturers}
            rosterError={rosterError}
            rosterLoading={rosterLoading}
            onChange={updateDraft}
          />
        ) : draft.targetType === "outlets" ? (
          <OutletTargetFields draft={draft} errors={errors} onChange={updateDraft} />
        ) : (
          <LeadsTargetFields draft={draft} errors={errors} onChange={updateDraft} />
        )}
        <Notice>
          Targets are optional. People without a target can still sell, and achievement cannot be edited here.
        </Notice>
      </div>
      <BottomSheet open={periodOpen} onClose={() => setPeriodOpen(false)} title="Period">
        {periodOptions(currentPeriodMonth()).map((option) => (
          <DataRow
            key={option.value}
            title={option.label}
            chevron={false}
            selected={option.value === draft.periodMonth}
            onClick={() => {
              setPeriodOpen(false);
              if (option.value === draft.periodMonth) return;
              updateDraft({ periodMonth: option.value });
              onPeriodMonthChange(option.value);
            }}
          />
        ))}
      </BottomSheet>
      <BottomSheet open={removeOpen} onClose={() => setRemoveOpen(false)} title="Remove target">
        <p className={styles.meta}>
          This person will see no target for this type and period. Historical records stay auditable.
        </p>
        <div style={{ marginTop: 16 }}>
          <Button
            variant="filled"
            color="error"
            label={removeTarget.isPending ? "Removing..." : "Remove target"}
            disabled={removeTarget.isPending}
            onClick={remove}
            style={{ width: "100%" }}
          />
        </div>
      </BottomSheet>
    </ManagementScreen>
  );
}

function SalesTargetFields({
  draft,
  errors,
  manufacturers,
  rosterError,
  rosterLoading,
  onChange,
}: {
  draft: TargetFormDraft;
  errors: TargetFormErrors;
  manufacturers: ManufacturerOut[];
  rosterError: boolean;
  rosterLoading: boolean;
  onChange: (patch: Partial<TargetFormDraft>) => void;
}) {
  const orderedLines = useMemo(
    () => [...draft.salesLines].sort((left, right) => Number(right.selected) - Number(left.selected)),
    [draft.salesLines],
  );
  const strip = useMemo(() => salesStripValue(draft, manufacturers), [draft, manufacturers]);
  const noneSelectedError = errors.salesLines && !selectedSalesLines(draft).length
    ? errors.salesLines
    : null;
  const updateLine = (manufacturerId: string, patch: Partial<TargetFormDraft["salesLines"][number]>) => {
    onChange({
      salesLines: draft.salesLines.map((line) =>
        line.manufacturerId === manufacturerId ? { ...line, ...patch } : line,
      ),
    });
  };

  return (
    <>
      <div className={styles.targetTotalStrip}>
        <div className={styles.targetTotalValues}>
          {strip.amount ? <strong>{strip.amount}</strong> : null}
          {strip.volume ? <strong>{strip.volume}</strong> : null}
          {!strip.amount && !strip.volume ? <strong>—</strong> : null}
        </div>
        <div>
          <span>{strip.selectedCount} of {strip.totalCount} manufacturers selected</span>
          <p>Running total across selected lines</p>
        </div>
      </div>
      <Section label="Target values">
        {rosterLoading ? (
          <Skeleton height={160} radius={12} />
        ) : rosterError ? (
          <ErrorState
            title="Manufacturer roster unavailable"
            message="Sales targets need the Humbee manufacturer roster. Try again before saving this target."
          />
        ) : orderedLines.length ? (
          <div className={styles.targetManufacturerList}>
            {orderedLines.map((line) => (
              line.selected ? (
                <div className={styles.targetLineCard} data-selected="true" key={line.manufacturerId}>
                  <div className={styles.targetLineHeader}>
                    <Checkbox
                      checked
                      label={line.manufacturerLabel}
                      style={{ width: "100%" }}
                      onChange={(event) => updateLine(line.manufacturerId, {
                        selected: (event.target as HTMLInputElement).checked,
                        value: (event.target as HTMLInputElement).checked ? line.value : "",
                      })}
                    />
                  </div>
                  <TextField
                    label={`Target value (${lineUnitLabel(line)})`}
                    value={line.value}
                    onChange={(event) => updateLine(line.manufacturerId, { value: (event.target as HTMLInputElement).value })}
                    error={Boolean(errors.salesLines && parsePositiveInteger(line.value) === null)}
                    helperText={errors.salesLines && parsePositiveInteger(line.value) === null ? errors.salesLines : undefined}
                  />
                </div>
              ) : (
                <button
                  className={`${styles.targetLineCard} ${styles.targetLineCardEmpty}`}
                  key={line.manufacturerId}
                  onClick={() => updateLine(line.manufacturerId, { selected: true })}
                  type="button"
                >
                  <div className={styles.targetLineHeader}>
                    <span className={styles.targetManuName}>{line.manufacturerLabel}</span>
                    <span className={styles.targetManuHint}>
                      <Icon name="Add" size={14} color="var(--color-primary)" />
                      Tap to add
                    </span>
                  </div>
                </button>
              )
            ))}
          </div>
        ) : (
          <EmptyState
            icon="InventoryOutlined"
            title="No manufacturers"
            message="The roster returned no manufacturers, so a sales target cannot be created."
          />
        )}
        {noneSelectedError ? <p className={styles.meta}>{noneSelectedError}</p> : null}
      </Section>
    </>
  );
}

function OutletTargetFields({
  draft,
  errors,
  onChange,
}: {
  draft: TargetFormDraft;
  errors: TargetFormErrors;
  onChange: (patch: Partial<TargetFormDraft>) => void;
}) {
  return (
    <>
      <Section label="Outlet category">
        <div className={styles.targetScopeRow}>
          {OUTLET_CATEGORY_OPTIONS.map((option) => (
            <button
              className={styles.targetScopeChip}
              data-active={draft.outletCategoryScope === option.value}
              key={option.value}
              onClick={() => onChange({ outletCategoryScope: option.value })}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </Section>
      <Section label="Target value">
        <div className={`${styles.card} ${styles.targetCompactCard}`}>
          <TextField
            label="New outlets (MTD)"
            placeholder="e.g. 25"
            value={draft.outletTargetValue}
            onChange={(event) => onChange({ outletTargetValue: (event.target as HTMLInputElement).value })}
            error={Boolean(errors.targetValue)}
            helperText={errors.targetValue ?? "Counted month-to-date after each outlet is verified."}
          />
        </div>
      </Section>
    </>
  );
}

function LeadsTargetFields({
  draft,
  errors,
  onChange,
}: {
  draft: TargetFormDraft;
  errors: TargetFormErrors;
  onChange: (patch: Partial<TargetFormDraft>) => void;
}) {
  return (
    <Section label="Target value">
      <div className={`${styles.card} ${styles.targetCompactCard}`}>
        <TextField
          label="Leads to capture"
          placeholder="e.g. 10"
          value={draft.leadTargetValue}
          inputProps={{ inputMode: "numeric", pattern: "[0-9]*" }}
          onChange={(event) => onChange({ leadTargetValue: (event.target as HTMLInputElement).value })}
          error={Boolean(errors.targetValue)}
          helperText={errors.targetValue ?? `Counted from leads captured in ${formatPeriodMonth(draft.periodMonth)}.`}
        />
      </div>
    </Section>
  );
}
