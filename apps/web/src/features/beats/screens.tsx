"use client";

import { Button, Checkbox, EmptyState, ErrorState, FAB, GeoScopePicker, Icon, ListRow, Skeleton, StatusChip, TextField } from "humbee-design-system";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { BeatDetailResponse, ShopCategory } from "@humbee/api-contract";
import { SpCard, SpInlineAlert, SpProcessProgress, SpScreen, SpSectionLabel, SpStickyFooter, StatusHistory } from "@/src/features/shell/components";
import type { StatusHistoryStep } from "@/src/features/shell/components";
import { ApiClientError } from "@/src/shared/api";
import { shopCategoryLabel } from "@/src/shared/geography-master";
import { filterOutletsByQuery, sortOutletsTakenLast } from "@/src/shared/outlet-list";
import styles from "@/src/features/management/management.module.css";
import { useBeatDraft } from "./beat-draft";
import type { BeatFrequency } from "./beat-draft";
import type { Beat, BeatScope, OutletChoice } from "./service";
import { mapBeat, mapOutlet, useBeatDetail, useBeatMutations, useBeats, useGeographyMaster, useScopeOutlets } from "./service";
import { beatRunSectionFromBeatListItem, beatRunSectionLabel, beatRunSectionOrder, routePlanStartedBeatIds, useRouteDay, useRoutePlanMutations, type BeatRunSection } from "../routes/service";

const UNTITLED_BEAT = "Untitled beat";
const CREATE_BEAT_STEPS = ["Scope", "Outlets", "Review"];
type BeatListRow = Beat & { runOrigin: BeatRunSection; displayStatus: string };

function beatListChip(displayStatus: string) {
  if (displayStatus === "edit_pending") return { status: "pending" as const, label: "Edit pending" };
  if (displayStatus === "pending_approval") return { status: "pending" as const, label: "Pending approval" };
  if (displayStatus === "draft") return { status: "default" as const, label: "Draft" };
  if (displayStatus === "inactive") return { status: "cancelled" as const, label: "Inactive" };
  return { status: "approved" as const, label: "Approved" };
}

function draftCode(beatId: string, name: string) {
  if (!name || name === UNTITLED_BEAT) return beatId;
  return name;
}

function sentenceLabel(value: string) {
  const display = value.replace(/_/g, " ").trim().toLowerCase();
  return display ? `${display.charAt(0).toUpperCase()}${display.slice(1)}` : "—";
}

function outletCountLabel(count: number) {
  return `${count} outlet${count === 1 ? "" : "s"}`;
}

function beatStringArray(value: BeatDetailResponse["geo_scope"], key: string) {
  if (!value || typeof value !== "object") return [];
  const candidate = (value as Record<string, unknown>)[key];
  return Array.isArray(candidate) ? candidate.filter((item): item is string => typeof item === "string") : [];
}

function beatGeoLabelItems(scope: BeatDetailResponse["geo_scope"], key: string) {
  const labels = scope.labels;
  if (!labels || typeof labels !== "object" || Array.isArray(labels)) return [];
  const candidates = (labels as Record<string, unknown>)[key];
  if (!Array.isArray(candidates)) return [];
  return candidates.flatMap((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const label = item as Record<string, unknown>;
    return typeof label.id === "string" && typeof label.name === "string"
      ? [{ id: label.id, name: label.name }]
      : [];
  });
}

function beatGeoLabels(scope: BeatDetailResponse["geo_scope"], key: string, ids: string[]) {
  if (!ids.length) return "—";
  const lookup = new Map(beatGeoLabelItems(scope, key).map((item) => [item.id, item.name]));
  const labels = ids.map((id) => lookup.get(id)).filter((label): label is string => Boolean(label));
  return labels.length ? labels.join(", ") : "Label unavailable";
}

function categoryLabels(ids: string[]) {
  return ids.length ? ids.map((id) => shopCategoryLabel(id as ShopCategory)).join(", ") : "All categories";
}

function BeatDetailSection({ label: sectionLabel, children }: { label: string; children: ReactNode }) {
  return <section><p className={`${styles.sectionLabel} hb-heading`}>{sectionLabel}</p>{children}</section>;
}

function BeatDetailRow({ label: rowLabel, value }: { label: string; value: ReactNode }) {
  return (
    <div className={styles.detailRow}>
      <span>{rowLabel}</span>
      <strong>{value}</strong>
    </div>
  );
}

function asShopCategories(values: string[]): ShopCategory[] {
  return values as ShopCategory[];
}

function beatDisplayName(beat: Beat) {
  return beat.name.trim() || "Coverage plan";
}

function beatDisplaySubtitle(beat: Beat) {
  const locations = beat.locations.filter(Boolean).join(", ");
  return [locations, sentenceLabel(beat.frequency)]
    .filter((item) => item && item !== "—")
    .join(" · ");
}

function draftStatusQuery(statusValue: Beat["status"]) {
  return statusValue === "draft" ? "&status=draft" : "";
}

function pendingApprovalId(detail: BeatDetailResponse) {
  return detail.pending_edit?.approval_request_id ?? detail.approval_request_id;
}

function beatListIcon(beat: Beat, alreadyStarted: boolean) {
  if (alreadyStarted) {
    return (
      <span className="sp-started-beat-icon" aria-label="Started today">
        <Icon name="Check" size={18} color="currentColor" />
      </span>
    );
  }
  return <Icon name="Calendar" size={22} color={beat.status === "approved" ? "var(--color-primary)" : "var(--color-text-placeholder)"} />;
}

function beatStatusHistory(beat: Beat): StatusHistoryStep[] {
  if (beat.status === "draft") {
    return [
      { label: "Draft", detail: "Not submitted yet", state: "current" },
      { label: "Submit for approval", state: "future" },
      { label: "Manager approval", state: "future" },
    ];
  }
  if (beat.status === "pending") {
    return [
      { label: "Submitted", state: "done" },
      { label: "Pending manager approval", state: "current" },
      { label: "Ready to start route", state: "future" },
    ];
  }
  if (beat.status === "inactive") {
    return [
      { label: "Submitted", state: "done" },
      { label: "Approved", state: "done" },
      { label: "Inactive", state: "current" },
    ];
  }
  return [
    { label: "Submitted", state: "done" },
    { label: "Approved", state: "done" },
    { label: "Ready to start route", state: "current" },
  ];
}

function beatMutationErrorMessage(error: unknown) {
  if (error instanceof ApiClientError) return error.message;
  return "Beat could not be submitted. Try again.";
}

export function MyBeatsScreen() {
  const router = useRouter();
  const [tab, setTab] = useState("all");
  const beatsQuery = useBeats(tab);
  const current = useRouteDay(undefined, { refetchOnWindowFocus: false });
  const startedBeatIds = routePlanStartedBeatIds(current.data);
  const allBeats: BeatListRow[] = useMemo(() => (beatsQuery.data?.items ?? []).filter((item) => (
    item.lifecycle_state !== "draft"
    || item.display_name !== UNTITLED_BEAT
    || item.outlet_count > 0
  )).map((item) => ({
    id: item.id,
    name: item.display_name,
    zones: [],
    states: [],
    districts: [],
    locations: [],
    categories: [],
    outletIds: [],
    outletCount: item.outlet_count,
    frequency: String(item.frequency.frequency ?? ""),
    frequencyPlan: {
      cadence: (item.frequency.frequency as Beat["frequencyPlan"]["cadence"]) ?? "daily",
      days: [],
      weeks: [],
    },
    status: item.activation_state === "inactive" ? "inactive" : item.lifecycle_state === "approved" ? "approved" : item.lifecycle_state === "draft" ? "draft" : "pending",
    displayStatus: item.display_status,
    runOrigin: beatRunSectionFromBeatListItem(item),
  })), [beatsQuery.data]);
  const visibleBeats = allBeats;
  const beatSections = useMemo(() => (["assigned_beat", "unplanned_beat", "draft_beat"] as const)
    .map((section) => ({
      section,
      heading: beatRunSectionLabel(section),
      items: visibleBeats.filter((beat) => beat.runOrigin === section),
    }))
    .filter((section) => section.items.length)
    .sort((left, right) => beatRunSectionOrder(left.section) - beatRunSectionOrder(right.section)), [visibleBeats]);
  if (beatsQuery.isPending) return <SpScreen title="My beats" bell><div className="sp-content"><Skeleton height={240} radius={12} /></div></SpScreen>;
  if (beatsQuery.isError) return <SpScreen title="My beats" bell><ErrorState onRetry={() => void beatsQuery.refetch()} /></SpScreen>;
  if (!allBeats.length && tab === "all") return <SpScreen title="My beats" bell><EmptyState icon="Calendar" title="No beats yet" message="Create a beat plan from your assigned geography to start covering outlets." actionLabel="Create beat" onAction={() => router.push("/sp/beats/create/scope")} /></SpScreen>;
  return (
    <SpScreen title="My beats" bell bottomAction={<FAB iconName="Add" label="Create beat" onClick={() => router.push("/sp/beats/create/scope")} style={{ position: "static" }} />}>
      <div className="sp-filter-bar">
        {([["all", "All"], ["approved", "Approved"], ["pending", "Pending"], ["draft", "Draft"]] as const).map(([value, text]) => (
          <button className="sp-filter-chip" data-active={tab === value} key={value} onClick={() => setTab(value)} type="button">{text}</button>
        ))}
      </div>
      {visibleBeats.length ? (
        beatSections.map(({ section, heading, items }) => (
          <div key={section}>
            <div style={{ padding: "var(--space-md) var(--space-md) var(--space-sm)" }}>
              <SpSectionLabel>{heading}</SpSectionLabel>
            </div>
            <div className="sp-list">
              {items.map((beat) => {
                const alreadyStarted = startedBeatIds.has(beat.id);
                const chip = beatListChip(beat.displayStatus);
                return <ListRow key={beat.id} leading={beatListIcon(beat, alreadyStarted)} title={beatDisplayName(beat)} subtitle={alreadyStarted ? `${beatDisplaySubtitle(beat)} · Started today` : beatDisplaySubtitle(beat)} trailing={alreadyStarted ? <StatusChip status="verified" label="Started today" type="outlined" /> : <StatusChip status={chip.status} label={chip.label} type="outlined" />} showChevron onClick={() => router.push(`/sp/beats/detail?beatId=${encodeURIComponent(beat.id)}${draftStatusQuery(beat.status)}`)} />;
              })}
            </div>
          </div>
        ))
      ) : (
        <EmptyState icon="Calendar" title={`No ${tab} beats`} message="Choose another status to see your beats." actionLabel="Show all beats" onAction={() => setTab("all")} />
      )}
    </SpScreen>
  );
}

export function CreateBeatScopeScreen() {
  const router = useRouter();
  const geography = useGeographyMaster();
  const { draft, availableOutlets, outletsError, outletsLoading, outletsRefreshing, refreshOutlets, setGeoScope } = useBeatDraft();
  useEffect(() => {
    router.prefetch("/sp/beats/create/outlets");
  }, [router]);
  const scope: BeatScope = useMemo(() => ({
    zones: geography.data?.pool?.zones ?? [],
    states: geography.data?.pool?.states ?? [],
    districts: geography.data?.pool?.districts ?? [],
    categories: [],
  }), [geography.data]);
  const zones = useMemo(
    () => (geography.data?.zones ?? []).filter((zone) => scope.zones.includes(zone.id)).map((zone) => ({ id: zone.id, label: zone.name })),
    [geography.data, scope.zones],
  );
  const states = useMemo(
    () => (geography.data?.states ?? []).filter((state) => scope.states.includes(state.id)).map((state) => ({ id: state.id, label: state.name, zoneId: state.zone_id })),
    [geography.data, scope.states],
  );
  const districts = useMemo(
    () => (geography.data?.districts ?? []).filter((district) => scope.districts.includes(district.id)).map((district) => ({ id: district.id, label: district.name, stateId: district.state_id })),
    [geography.data, scope.districts],
  );
  const shopCategories = useMemo(
    () => (geography.data?.cats ?? []).map((category) => ({ id: category.id, label: category.name })),
    [geography.data],
  );
  if (geography.isPending) return <SpScreen title="Create beat" back><div className="sp-content"><Skeleton height={320} radius={12} /></div></SpScreen>;
  if (geography.isError || !geography.data) return <SpScreen title="Create beat" back><ErrorState onRetry={() => void geography.refetch()} /></SpScreen>;

  return (
    <SpScreen title="Create beat" back>
      <div className="sp-content">
        <SpProcessProgress steps={CREATE_BEAT_STEPS} activeStep={0} />
        <GeoScopePicker
          zones={zones}
          states={states}
          districts={districts}
          shopCategories={shopCategories}
          cascadeChildren={false}
          assigned={{
            zones: scope.zones,
            states: scope.states,
            districts: scope.districts,
          }}
          value={{
            zones: draft.zones,
            states: draft.states,
            districts: draft.districts,
            shopCategories: draft.categories,
          }}
          onChange={(value) => setGeoScope({
            zones: value.zones,
            states: value.states,
            districts: value.districts,
            categories: value.shopCategories,
          })}
        />
        {outletsError ?
          <SpInlineAlert tone="error">{outletsError instanceof ApiClientError ? outletsError.message : "Outlet details could not be loaded. Retry after saving the scope."}</SpInlineAlert> : ""
        }
        {outletsRefreshing ? <SpInlineAlert>Refreshing outlets for this scope...</SpInlineAlert> : null}
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          label={outletsError ? "Retry outlets" : "Choose outlets"}
          loading={outletsLoading}
          disabled={!draft.zones.length || !draft.states.length || !draft.districts.length || (!outletsError && !availableOutlets.length)}
          onClick={() => {
            if (outletsError) {
              refreshOutlets();
              return;
            }
            router.push("/sp/beats/create/outlets");
          }}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

export function OutletPickerScreen() {
  const router = useRouter();
  const { availableOutlets, draft, outletQuery, outletsComplete, outletsError, outletsLoading, outletsRefreshing, refreshOutlets, selectedOutlets, setOutletQuery, toggleAllOutlets, toggleOutlet, toggleOutletGroup } = useBeatDraft();
  const sortedAvailableOutlets = useMemo(() => sortOutletsTakenLast(availableOutlets, "location_then_name"), [availableOutlets]);
  const availableOutletsOnly = useMemo(() => sortedAvailableOutlets.filter((outlet) => !outlet.takenBy), [sortedAvailableOutlets]);
  const assignedOutletsOnly = useMemo(() => sortedAvailableOutlets.filter((outlet) => Boolean(outlet.takenBy)), [sortedAvailableOutlets]);
  const availableLocations = useMemo(() => [...new Set(availableOutletsOnly.map((outlet) => outlet.location))], [availableOutletsOnly]);
  const assignedLocations = useMemo(() => [...new Set(assignedOutletsOnly.map((outlet) => outlet.location))], [assignedOutletsOnly]);
  const selectedOutletIds = useMemo(() => new Set(draft.outletIds), [draft.outletIds]);
  const selectableOutlets = availableOutletsOnly;
  const allOutletsSelected = selectableOutlets.length > 0 && selectableOutlets.every((outlet) => selectedOutletIds.has(outlet.id));
  useEffect(() => {
    router.prefetch("/sp/beats/create/review");
  }, [router]);

  return (
    <SpScreen title="Choose outlets" back>
      <div className="sp-search-toolbar">
        <TextField placeholder="Search outlets" startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />} value={outletQuery} onChange={(event) => setOutletQuery((event.target as HTMLInputElement).value)} />
      </div>
      <div className="sp-content">
        <SpProcessProgress steps={CREATE_BEAT_STEPS} activeStep={1} />
        {selectableOutlets.length ? (
          <Button
            variant="text"
            color="primary"
            size="small"
            label={outletsRefreshing ? "Loading all outlets..." : allOutletsSelected ? "Clear all outlets" : `Select all outlets (${selectableOutlets.length})`}
            disabled={outletsRefreshing}
            onClick={toggleAllOutlets}
          />
        ) : null}
      </div>
      {outletsLoading ? (
        <div className="sp-content"><Skeleton height={280} radius={12} /></div>
      ) : outletsError ? (
        <ErrorState title="Outlets unavailable" message={outletsError instanceof ApiClientError ? outletsError.message : "Outlet details could not be loaded for this scope."} onRetry={refreshOutlets} />
      ) : !draft.districts.length ? (
        <EmptyState icon="LocationPin" title="Select a district first" message="Choose geography scope before selecting outlets." actionLabel="Change scope" onAction={() => router.push("/sp/beats/create/scope")} />
      ) : !sortedAvailableOutlets.length && outletQuery ? (
        <EmptyState icon="SearchOutlined" title={`No outlets match "${outletQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setOutletQuery("")} />
      ) : !sortedAvailableOutlets.length ? (
        <EmptyState icon="LocationPin" title="No outlets in this scope" message="Change the geography or category selection to continue." actionLabel="Change scope" onAction={() => router.push("/sp/beats/create/scope")} />
      ) : availableLocations.map((location) => {
        const group = availableOutletsOnly.filter((outlet) => outlet.location === location);
        const selectableGroup = group.filter((outlet) => !outlet.takenBy);
        const allSelected = selectableGroup.length > 0 && selectableGroup.every((outlet) => selectedOutletIds.has(outlet.id));
        return (
          <div key={location}>
            <div className="sp-group-header">
              <div>
                <strong>{location || "Area not set"}</strong>
                <span>{group.length} outlets</span>
              </div>
              {selectableGroup.length ? <Button variant="text" color="primary" size="small" label={allSelected ? "Clear" : "Select all"} disabled={outletsRefreshing} onClick={() => toggleOutletGroup(location)} /> : null}
            </div>
            <div className="sp-list">
              {group.map((outlet) => (
                <ListRow
                  key={outlet.id}
                  leading={<span onClick={(event) => event.stopPropagation()}><Checkbox checked={selectedOutletIds.has(outlet.id)} onChange={() => toggleOutlet(outlet.id)} /></span>}
                  title={outlet.name}
                  subtitle={undefined}
                  meta={outlet.category || undefined}
                  onClick={() => toggleOutlet(outlet.id)}
                />
              ))}
            </div>
          </div>
        );
      })}
      {assignedLocations.map((location) => {
        const group = assignedOutletsOnly.filter((outlet) => outlet.location === location);
        return (
          <div key={`assigned-${location}`}>
            <div className="sp-group-header">
              <div>
                <strong>{location || "Area not set"}</strong>
                <span>{group.length} outlets</span>
              </div>
            </div>
            <div className="sp-list">
              {group.map((outlet) => (
                <ListRow
                  key={outlet.id}
                  leading={<span onClick={(event) => event.stopPropagation()}><Checkbox checked={false} disabled onChange={() => toggleOutlet(outlet.id)} /></span>}
                  title={outlet.name}
                  subtitle={outlet.takenBy ? `Already on beat ${outlet.takenBy}` : outlet.location || undefined}
                  meta={outlet.category || undefined}
                  disabled
                />
              ))}
            </div>
          </div>
        );
      })}
      <SpStickyFooter>
        <div className="sp-row">
          <strong>{`${outletsComplete ? selectedOutlets.length : draft.outletIds.length} selected`}</strong>
          <Button variant="filled" color="primary" label="Review beat" disabled={!draft.outletIds.length} onClick={() => { setOutletQuery(""); router.push("/sp/beats/create/review"); }} style={{ flex: 1 }} />
        </div>
      </SpStickyFooter>
    </SpScreen>
  );
}

interface FrequencyChooserFieldsProps {
  frequency: BeatFrequency;
  days: number[];
  weeks: number[];
  setFrequency: (frequency: BeatFrequency) => void;
  toggleDay: (day: number) => void;
  toggleWeek: (week: number) => void;
}

function FrequencyChooserFields({ frequency: selectedFrequency, days: selectedDays, weeks: selectedWeeks, setFrequency, toggleDay, toggleWeek }: FrequencyChooserFieldsProps) {
  const frequencies: Array<{ value: BeatFrequency; label: string }> = [
    { value: "daily", label: "Daily" },
    { value: "weekly", label: "Weekly" },
    { value: "fortnightly", label: "Fortnightly" },
    { value: "monthly", label: "Monthly" },
  ];
  const days = ["S", "M", "T", "W", "T", "F", "S"];
  const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const coverage = selectedFrequency === "daily"
    ? "~26 visits/mo"
    : selectedFrequency === "weekly"
      ? `${selectedDays.length}×/wk · ~${selectedDays.length * 4}/mo`
      : `${selectedDays.length * selectedWeeks.length}/mo`;

  return (
    <div>
      <SpSectionLabel>Visit frequency</SpSectionLabel>
      <div className="sp-choice-grid">
        {frequencies.map((frequency) => <button className="sp-choice-button" data-active={selectedFrequency === frequency.value} key={frequency.value} type="button" onClick={() => setFrequency(frequency.value)}>{frequency.label}</button>)}
      </div>
      {selectedFrequency !== "daily" ? (
        <div className="sp-frequency-section">
          <strong>{selectedFrequency === "monthly" ? "Visit day of week" : "Visit days"}</strong>
          <div className="sp-day-grid">
            {days.map((day, index) => <button aria-label={`${dayNames[index]} ${selectedDays.includes(index) ? "selected" : "not selected"}`} className="sp-day-button" data-active={selectedDays.includes(index)} key={`${day}-${index}`} type="button" onClick={() => toggleDay(index)}>{day}</button>)}
          </div>
        </div>
      ) : null}
      {selectedFrequency === "fortnightly" || selectedFrequency === "monthly" ? (
        <div className="sp-frequency-section">
          <strong>{selectedFrequency === "monthly" ? "Which week" : "Week cycle"}</strong>
          <div className="sp-week-grid">
            {[1, 2, 3, 4].map((week) => <button className="sp-week-button" data-active={selectedWeeks.includes(week)} key={week} type="button" onClick={() => toggleWeek(week)}>W{week}</button>)}
          </div>
        </div>
      ) : null}
      <div className="sp-coverage">
        <Icon name="Autorenew" size={18} color="var(--color-primary)" />
        <span>Coverage: <strong>{coverage}</strong></span>
      </div>
    </div>
  );
}

function FrequencyChooser() {
  const { draft, setFrequency, toggleDay, toggleWeek } = useBeatDraft();
  return <FrequencyChooserFields frequency={draft.frequency} days={draft.days} weeks={draft.weeks} setFrequency={setFrequency} toggleDay={toggleDay} toggleWeek={toggleWeek} />;
}

export function NameBeatScreen() {
  const router = useRouter();
  const { draft, outletsComplete, outletsError, refreshOutlets, selectedOutlets, setName, submit, unavailableSelectionCount } = useBeatDraft();
  const submittingRef = useRef(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [outletSearchQuery, setOutletSearchQuery] = useState("");
  const sortedSelectedOutlets = useMemo(() => sortOutletsTakenLast(selectedOutlets, "location_then_name"), [selectedOutlets]);
  const visibleSelectedOutlets = useMemo(() => filterOutletsByQuery(sortedSelectedOutlets, outletSearchQuery), [outletSearchQuery, sortedSelectedOutlets]);
  const hasFrequencyDetails = draft.frequency === "daily"
    || (draft.days.length > 0 && (draft.frequency === "weekly" || draft.weeks.length > 0));
  const followsConvention = /^[A-Za-z0-9]+-[A-Za-z0-9]+-[A-Za-z0-9]+-\d{1,2}$/.test(draft.name.trim());
  const submitForApproval = async () => {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submit();
      router.push("/sp/beats");
    } catch (error) {
      submittingRef.current = false;
      setSubmitting(false);
      setSubmitError(beatMutationErrorMessage(error));
    }
  };

  return (
    <SpScreen title="Review beat" back>
      <div className="sp-content">
        <SpProcessProgress steps={CREATE_BEAT_STEPS} activeStep={2} />
        <TextField label="Beat name" value={draft.name} helperText={followsConvention ? "Convention: AREA-DIRECTION-LOCALITY-NN" : "Recommended format: AREA-DIRECTION-LOCALITY-NN"} onChange={(event) => setName((event.target as HTMLInputElement).value)} />
        {!followsConvention && draft.name.trim() ? <SpInlineAlert tone="warning">This name does not follow the recommended convention. You can still submit it.</SpInlineAlert> : null}
        <FrequencyChooser />
        <div>
          <SpSectionLabel>{outletsComplete ? `${outletCountLabel(selectedOutlets.length)} in this beat` : "Outlets in this beat"}</SpSectionLabel>
          {outletsError ? (
            <ErrorState title="Outlets unavailable" message={outletsError instanceof ApiClientError ? outletsError.message : "Outlet details could not be loaded for this scope."} onRetry={refreshOutlets} />
          ) : !outletsComplete ? (
            <Skeleton height={160} radius={12} />
          ) : !sortedSelectedOutlets.length ? (
            <EmptyState icon="LocationPin" title="No outlets" message="No outlets are linked to this beat." />
          ) : (
            <>
              <div className="sp-search-toolbar">
                <TextField
                  placeholder="Search outlets"
                  startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
                  value={outletSearchQuery}
                  onChange={(event) => setOutletSearchQuery((event.target as HTMLInputElement).value)}
                />
              </div>
              {visibleSelectedOutlets.length ? (
                <SpCard padded={false}>
                  <div className="sp-list">
                    {visibleSelectedOutlets.map((outlet, index) => <ListRow key={outlet.id} leading={<span className="sp-sequence-number">{index + 1}</span>} title={outlet.name} subtitle={outlet.location || undefined} meta={outlet.category || undefined} />)}
                  </div>
                </SpCard>
              ) : (
                <EmptyState icon="SearchOutlined" title={`No outlets match "${outletSearchQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setOutletSearchQuery("")} />
              )}
            </>
          )}
        </div>
        {unavailableSelectionCount > 0 ? <SpInlineAlert tone="warning">{`${outletCountLabel(unavailableSelectionCount)} you picked earlier ${unavailableSelectionCount === 1 ? "is" : "are"} no longer available (now on another beat or outside this scope) and will not be included.`}</SpInlineAlert> : null}
        {submitError ? <SpInlineAlert tone="error">{submitError}</SpInlineAlert> : null}
        <SpInlineAlert>Submitting this beat sends it to your manager for approval.</SpInlineAlert>
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          label="Submit for approval"
          loading={submitting}
          disabled={!draft.name.trim() || !outletsComplete || !selectedOutlets.length || !hasFrequencyDetails || submitting}
          onClick={() => { void submitForApproval(); }}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

export function BeatDetailScreen({ beatId, knownStatus }: { beatId: string; knownStatus?: string | null }) {
  const loaded = useBeatDetail(beatId, { knownDraft: knownStatus === "draft" });
  if (loaded.isPending) return <SpScreen title="Beat" back><div className="sp-content"><Skeleton height={320} radius={12} /></div></SpScreen>;
  if (loaded.isError || !loaded.detail) return <SpScreen title="Beat" back><ErrorState onRetry={() => { void loaded.refetch(); }} /></SpScreen>;
  return <BeatDetailContent beatId={beatId} detail={loaded.detail} />;
}

function BeatDetailContent({ beatId, detail }: { beatId: string; detail: BeatDetailResponse }) {
  const router = useRouter();
  const mutations = useBeatMutations();
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [outletSearchQuery, setOutletSearchQuery] = useState("");
  const [outletSearchBeatId, setOutletSearchBeatId] = useState(beatId);
  if (outletSearchBeatId !== beatId) {
    setOutletSearchBeatId(beatId);
    setOutletSearchQuery("");
  }
  const current = useRouteDay(undefined, { refetchOnWindowFocus: false });
  const routeMutations = useRoutePlanMutations();
  const beat = mapBeat(detail);
  const outlets: OutletChoice[] = detail.outlets.map((outlet) => ({
    id: outlet.outlet_ref,
    name: outlet.name,
    zone: "",
    state: "",
    district: "",
    location: outlet.locality?.trim() || "",
    category: outlet.category ? shopCategoryLabel(outlet.category) : "",
    selected: true,
  }));
  const inactive = beat.status === "inactive";
  const beatOutlets = outlets.filter((outlet) => beat.outletIds.includes(outlet.id));
  const sortedBeatOutlets = sortOutletsTakenLast(beatOutlets, "location_then_name");
  const visibleBeatOutlets = filterOutletsByQuery(sortedBeatOutlets, outletSearchQuery);
  const zones = beatStringArray(detail.geo_scope, "zones");
  const states = beatStringArray(detail.geo_scope, "states");
  const districts = beatStringArray(detail.geo_scope, "districts");
  const categories = beatStringArray(detail.geo_scope, "cats");
  const summaryTitle = detail.code || beat.name;
  const summarySubtitle = beat.frequency;
  const alreadyStarted = routePlanStartedBeatIds(current.data).has(beat.id);
  const routeStartError = routeMutations.switchBeat.error;
  const chip = beatListChip(detail.display_status);
  const approvalRequestId = pendingApprovalId(detail);
  const isPendingApproval = beat.status === "pending";
  const withdrawRequest = async () => {
    if (!approvalRequestId || mutations.withdraw.isPending) return;
    setWithdrawError(null);
    try {
      await mutations.withdraw.mutateAsync({ beatId: beat.id, approvalRequestId });
      if (detail.pending_edit) {
        router.push(`/sp/beats/detail?beatId=${encodeURIComponent(beat.id)}`);
        return;
      }
      router.push(`/sp/beats/edit?beatId=${encodeURIComponent(beat.id)}&status=draft`);
    } catch (error) {
      setWithdrawError(beatMutationErrorMessage(error));
    }
  };
  return (
    <SpScreen title={beatDisplayName(beat)} back>
      <div className="sp-content">
        <div className={styles.card}>
          <div className={styles.teamTop}>
            <span className={styles.rowCopy}>
              <strong>{summaryTitle}</strong>
              <span>{summarySubtitle}</span>
            </span>
            <StatusChip status={chip.status} label={chip.label} type="outlined" />
          </div>
        </div>
        <div>
          <SpSectionLabel>Outlets in this beat</SpSectionLabel>
          {sortedBeatOutlets.length ? (
            <>
              <div className="sp-search-toolbar">
                <TextField
                  placeholder="Search outlets"
                  startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
                  value={outletSearchQuery}
                  onChange={(event) => setOutletSearchQuery((event.target as HTMLInputElement).value)}
                />
              </div>
              {visibleBeatOutlets.length ? (
                <SpCard padded={false}>
                  <div className="sp-list">
                    {visibleBeatOutlets.map((outlet) => <ListRow key={outlet.id} leading={<Icon name="LocationPin" size={22} color="var(--color-primary)" />} title={outlet.name} subtitle={outlet.location || undefined} meta={outlet.category || undefined} />)}
                  </div>
                </SpCard>
              ) : (
                <EmptyState icon="SearchOutlined" title={`No outlets match "${outletSearchQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setOutletSearchQuery("")} />
              )}
            </>
          ) : (
            <SpCard padded={false}>
              <div className="sp-list">
                <div style={{ padding: "var(--space-md)" }}><p className="sp-meta">{outletCountLabel(beat.outletCount)} are linked to this beat. Outlet details will appear here.</p></div>
              </div>
            </SpCard>
          )}
        </div>
        <BeatDetailSection label="Geography scope">
          <div className={styles.card} style={{ padding: 0 }}>
            <BeatDetailRow label="Zones" value={beatGeoLabels(detail.geo_scope, "zones", zones)} />
            <BeatDetailRow label="States" value={beatGeoLabels(detail.geo_scope, "states", states)} />
            <BeatDetailRow label="Districts" value={beatGeoLabels(detail.geo_scope, "districts", districts)} />
            <BeatDetailRow label="Shop categories" value={categoryLabels(categories)} />
          </div>
        </BeatDetailSection>
        {inactive ? <SpInlineAlert tone="warning">This beat is inactive and cannot be used for new route planning. Existing history is retained.</SpInlineAlert> : null}
        {alreadyStarted ? <SpInlineAlert>This beat is already started in today&apos;s route.</SpInlineAlert> : null}
        {routeStartError ? <SpInlineAlert tone="error">{routeStartError instanceof ApiClientError ? routeStartError.message : "Route could not be started. Try again."}</SpInlineAlert> : null}
        {withdrawError ? <SpInlineAlert tone="error">{withdrawError}</SpInlineAlert> : null}
        {isPendingApproval ? <SpInlineAlert>This request is waiting for your manager. Withdraw it to make more changes.</SpInlineAlert> : null}
        <StatusHistory historyKey={beat.status} steps={beatStatusHistory(beat)} />
      </div>
      <SpStickyFooter>
        {isPendingApproval ? (
          <Button variant="outlined" color="error" label="Withdraw request" loading={mutations.withdraw.isPending} disabled={!approvalRequestId || mutations.withdraw.isPending} onClick={() => { void withdrawRequest(); }} style={{ width: "100%" }} />
        ) : (
          <div className="sp-row"><Button variant="outlined" color="neutral" label="Edit beat" disabled={inactive} onClick={() => router.push(`/sp/beats/edit?beatId=${encodeURIComponent(beat.id)}${draftStatusQuery(beat.status)}`)} style={{ flex: 1 }} /><Button variant="filled" color="primary" label={alreadyStarted ? "Beat started" : "Start route"} loading={routeMutations.switchBeat.isPending} disabled={inactive || beat.status !== "approved" || alreadyStarted || current.isPending || routeMutations.switchBeat.isPending} onClick={() => routeMutations.switchBeat.mutate(beat.id, { onSuccess: () => router.push("/sp/route") })} style={{ flex: 1 }} /></div>
        )}
      </SpStickyFooter>
    </SpScreen>
  );
}

export function EditBeatScreen({ beatId, knownStatus }: { beatId: string; knownStatus?: string | null }) {
  const loaded = useBeatDetail(beatId, { knownDraft: knownStatus === "draft", pendingEdit: true });
  const geography = useGeographyMaster();
  if (loaded.isPending || geography.isPending) return <SpScreen title="Edit beat" back><div className="sp-content"><Skeleton height={320} radius={12} /></div></SpScreen>;
  if (loaded.isError || geography.isError || !loaded.detail || !geography.data) return <SpScreen title="Edit beat" back><ErrorState onRetry={() => { void loaded.refetch(); void geography.refetch(); }} /></SpScreen>;
  const { detail, draft } = loaded;
  const beat = mapBeat(detail);
  const savedScopes = draft ? [beat, mapBeat(draft)] : [beat];
  const withSaved = (pool: string[] | undefined, saved: (item: typeof beat) => string[]) => [...new Set([...(pool ?? []), ...savedScopes.flatMap(saved)])];
  const scope: BeatScope = {
    zones: withSaved(geography.data.pool?.zones, (item) => item.zones),
    states: withSaved(geography.data.pool?.states, (item) => item.states),
    districts: withSaved(geography.data.pool?.districts, (item) => item.districts),
    categories: geography.data.pool?.cats ?? [],
  };
  const draftOutlets: OutletChoice[] = detail.outlets.map((outlet) => ({
    id: outlet.outlet_ref,
    name: outlet.name,
    zone: "",
    state: "",
    district: "",
    location: outlet.locality?.trim() || "",
    category: outlet.category ? shopCategoryLabel(outlet.category) : "",
    selected: true,
  }));
  const zoneOptions = geography.data.zones.filter((zone) => scope.zones.includes(zone.id)).map((zone) => ({ id: zone.id, label: zone.name }));
  const stateOptions = geography.data.states.filter((state) => scope.states.includes(state.id)).map((state) => ({ id: state.id, label: state.name, zoneId: state.zone_id }));
  const districtOptions = geography.data.districts.filter((district) => scope.districts.includes(district.id)).map((district) => ({ id: district.id, label: district.name, stateId: district.state_id }));
  const categoryOptions = geography.data.cats.filter((category) => !scope.categories.length || scope.categories.includes(category.id)).map((category) => ({ id: category.id, label: category.name }));
  return <EditBeatContent beat={beat} draft={draft} approvalRequestId={pendingApprovalId(detail)} hasApprovedVersion={Boolean(loaded.current)} scope={scope} persistedOutlets={draftOutlets} zoneOptions={zoneOptions} stateOptions={stateOptions} districtOptions={districtOptions} categoryOptions={categoryOptions} />;
}

function EditBeatContent({
  beat,
  draft,
  approvalRequestId,
  hasApprovedVersion,
  scope,
  persistedOutlets,
  zoneOptions,
  stateOptions,
  districtOptions,
  categoryOptions,
}: {
  beat: Beat;
  draft: BeatDetailResponse | null;
  approvalRequestId: string | null;
  hasApprovedVersion: boolean;
  scope: BeatScope;
  persistedOutlets: OutletChoice[];
  zoneOptions: Array<{ id: string; label: string }>;
  stateOptions: Array<{ id: string; label: string; zoneId: string }>;
  districtOptions: Array<{ id: string; label: string; stateId: string }>;
  categoryOptions: Array<{ id: string; label: string }>;
}) {
  const router = useRouter();
  const mutations = useBeatMutations();
  const isDraft = beat.status === "draft";
  const isPendingApproval = beat.status === "pending";
  const saving = mutations.submitEdit.isPending || mutations.submit.isPending || mutations.saveDraft.isPending || mutations.replaceOutlets.isPending || mutations.withdraw.isPending || mutations.branchEdit.isPending;
  // When resuming an already-in-progress edit of an approved beat, seed the form from that
  // draft (not the approved current version) so the user's previously saved changes reappear.
  const seed = !isDraft && draft ? mapBeat(draft) : beat;
  const [name, setName] = useState(seed.name);
  const [zones, setZones] = useState(seed.zones);
  const [states, setStates] = useState(seed.states);
  const [districts, setDistricts] = useState(seed.districts);
  const [categories, setCategories] = useState<ShopCategory[]>(() => asShopCategories(seed.categories));
  const unsavedOutletScope = useMemo(() => ({ districts, categories }), [districts, categories]);
  const outletScopeReady = districts.length > 0;
  const scopeOutlets = useScopeOutlets(beat.id, "", outletScopeReady, "edit", unsavedOutletScope);
  const outletsRefreshing = outletScopeReady && Boolean(scopeOutlets.isFetching || scopeOutlets.hasNextPage);
  const outletsError = outletScopeReady && scopeOutlets.isError
    ? (scopeOutlets.error instanceof ApiClientError ? scopeOutlets.error.message : "Outlets could not be loaded for this scope. Try adjusting it again.")
    : null;
  const scopeComplete = outletScopeReady && scopeOutlets.isSuccess && !scopeOutlets.isFetching && !scopeOutlets.hasNextPage;
  const outlets = useMemo<OutletChoice[]>(() => {
    const scopeChoices = (outletScopeReady ? scopeOutlets.data ?? [] : []).map(mapOutlet);
    if (scopeComplete) return scopeChoices;
    const outletsById = new Map(persistedOutlets.map((outlet) => [outlet.id, outlet] as const));
    scopeChoices.forEach((outlet) => outletsById.set(outlet.id, outlet));
    return [...outletsById.values()];
  }, [outletScopeReady, persistedOutlets, scopeComplete, scopeOutlets.data]);
  const [frequency, setFrequency] = useState<BeatFrequency>(seed.frequencyPlan.cadence);
  const [days, setDays] = useState(seed.frequencyPlan.days);
  const [weeks, setWeeks] = useState(seed.frequencyPlan.weeks);
  const [outletIds, setOutletIds] = useState(seed.outletIds);
  const [outletSearchQuery, setOutletSearchQuery] = useState("");
  const [showAvailableOutlets, setShowAvailableOutlets] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const savingRef = useRef(false);
  const effectiveOutletIds = useMemo(() => {
    if (!scopeComplete) return outletIds;
    const selectableIds = new Set(outlets.filter((outlet) => !outlet.takenBy).map((outlet) => outlet.id));
    return outletIds.filter((id) => selectableIds.has(id));
  }, [outletIds, outlets, scopeComplete]);
  const outletIdSet = useMemo(() => new Set(effectiveOutletIds), [effectiveOutletIds]);
  const droppedOutletCount = outletIds.length - effectiveOutletIds.length;
  const sortedOutlets = useMemo(() => sortOutletsTakenLast(outlets, "location_then_name"), [outlets]);
  const searchedOutlets = useMemo(() => filterOutletsByQuery(sortedOutlets, outletSearchQuery), [outletSearchQuery, sortedOutlets]);
  const visibleOutlets = showAvailableOutlets ? searchedOutlets : searchedOutlets.filter((outlet) => outletIdSet.has(outlet.id));
  const hasFrequencyDetails = frequency === "daily" || (days.length > 0 && (frequency === "weekly" || weeks.length > 0));
  const outletCount = effectiveOutletIds.length;
  const toggleEditOutlet = (outlet: OutletChoice) => {
    if (outlet.takenBy) return;
    setOutletIds((current) => current.includes(outlet.id) ? current.filter((id) => id !== outlet.id) : [...current, outlet.id]);
  };
  const submitLabel = isDraft ? "Submit for approval" : "Send for approval";
  const saveChanges = async () => {
    if (savingRef.current || isPendingApproval || !scopeComplete) return;
    const outletRefs = effectiveOutletIds;
    savingRef.current = true;
    const nextName = name.trim();
    setSaveError(null);
    try {
      if (isDraft) {
        await mutations.saveDraft.mutateAsync({
          beatId: beat.id,
          displayName: isDraft ? nextName : undefined,
          code: isDraft ? draftCode(beat.id, nextName) : undefined,
          geoScope: { zones, states, districts, cats: categories },
          frequency: { frequency, visit_days: days, week_cycle: weeks },
        });
        await mutations.replaceOutlets.mutateAsync({ beatId: beat.id, outletRefs });
        await mutations.submit.mutateAsync(beat.id);
        router.push("/sp/beats");
        return;
      }
      await mutations.branchEdit.mutateAsync(beat.id);
      await mutations.saveDraft.mutateAsync({
        beatId: beat.id,
        geoScope: { zones, states, districts, cats: categories },
        frequency: { frequency, visit_days: days, week_cycle: weeks },
      });
      await mutations.replaceOutlets.mutateAsync({ beatId: beat.id, outletRefs });
      await mutations.submitEdit.mutateAsync(beat.id);
      router.push(`/sp/beats/detail?beatId=${encodeURIComponent(beat.id)}`);
    } catch (error) {
      savingRef.current = false;
      setSaveError(beatMutationErrorMessage(error));
    }
  };
  const discardChanges = async () => {
    if (isDraft) {
      router.push(`/sp/beats/detail?beatId=${encodeURIComponent(beat.id)}&status=draft`);
      return;
    }
    setSaveError(null);
    try {
      if (isPendingApproval) {
        if (!approvalRequestId) {
          setSaveError("This request cannot be withdrawn right now.");
          return;
        }
        await mutations.withdraw.mutateAsync({ beatId: beat.id, approvalRequestId });
        if (hasApprovedVersion) {
          router.push(`/sp/beats/detail?beatId=${encodeURIComponent(beat.id)}`);
          return;
        }
        router.push(`/sp/beats/edit?beatId=${encodeURIComponent(beat.id)}&status=draft`);
        return;
      }
      await mutations.discardDraft.mutateAsync(beat.id);
      router.push(`/sp/beats/detail?beatId=${encodeURIComponent(beat.id)}`);
    } catch (error) {
      setSaveError(beatMutationErrorMessage(error));
    }
  };
  return (
    <SpScreen title="Edit beat" back>
      <div className="sp-content">
        <TextField
          label="Beat name"
          value={name}
          disabled={!isDraft}
          helperText={isDraft ? "You can rename this draft before submitting it." : "Beat name cannot be changed after creation."}
          onChange={(event) => setName((event.target as HTMLInputElement).value)}
        />
        {isPendingApproval ? <SpInlineAlert tone="warning">This change is waiting for approval. Withdraw the request to edit it again.</SpInlineAlert> : null}
        <div>
          <SpSectionLabel>Geography scope</SpSectionLabel>
          <GeoScopePicker
            zones={zoneOptions}
            states={stateOptions}
            districts={districtOptions}
            shopCategories={categoryOptions}
            showScopeSummary={false}
            assigned={{ zones: scope.zones, states: scope.states, districts: scope.districts, shopCategories: scope.categories }}
            value={{ zones, states, districts, shopCategories: categories }}
            readOnly={isPendingApproval}
            onChange={(value) => {
              setZones(value.zones);
              setStates(value.states);
              setDistricts(value.districts);
              setCategories(asShopCategories(value.shopCategories));
            }}
          />
          {outletsError ? <SpInlineAlert tone="error">{outletsError}</SpInlineAlert> : null}
          {outletsRefreshing ? <SpInlineAlert>Refreshing outlets for this scope...</SpInlineAlert> : null}
        </div>
        <FrequencyChooserFields
          frequency={frequency}
          days={days}
          weeks={weeks}
          setFrequency={setFrequency}
          toggleDay={(day) => setDays((current) => current.includes(day) ? current.filter((value) => value !== day) : [...current, day])}
          toggleWeek={(week) => setWeeks((current) => current.includes(week) ? current.filter((value) => value !== week) : [...current, week])}
        />
        <div>
          <SpSectionLabel>Outlets in this beat · {outletCount}</SpSectionLabel>
          <div className={styles.outletEditorStack}>
            <div className="sp-search-toolbar">
              <TextField
                placeholder="Search outlets"
                startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
                value={outletSearchQuery}
                onChange={(event) => setOutletSearchQuery((event.target as HTMLInputElement).value)}
              />
            </div>
            <Button
              variant="outlined"
              color="primary"
              size="small"
              label={showAvailableOutlets ? "Show selected outlets only" : "Add outlets from scope"}
              leftIcon={<Icon name={showAvailableOutlets ? "Check" : "Add"} size={18} color="currentColor" />}
              onClick={() => setShowAvailableOutlets((current) => !current)}
              style={{ width: "100%" }}
            />
            <SpInlineAlert>Clear an outlet checkbox to remove it. Show available outlets to add more outlets from the beat scope.</SpInlineAlert>
            {visibleOutlets.length ? (
              <SpCard padded={false}>
                <div className="sp-list">
                  {visibleOutlets.map((outlet) => <ListRow key={outlet.id} leading={<span onClick={(event) => event.stopPropagation()}><Checkbox checked={outletIdSet.has(outlet.id)} disabled={Boolean(outlet.takenBy)} onChange={() => toggleEditOutlet(outlet)} /></span>} title={outlet.name} subtitle={outlet.takenBy ? `Already on beat ${outlet.takenBy}` : outlet.location || undefined} meta={outlet.category || undefined} disabled={Boolean(outlet.takenBy)} onClick={outlet.takenBy ? undefined : () => toggleEditOutlet(outlet)} />)}
                </div>
              </SpCard>
            ) : (
              outletSearchQuery
                ? <EmptyState icon="SearchOutlined" title={`No outlets match "${outletSearchQuery}"`} message="Try another outlet name." actionLabel="Clear search" onAction={() => setOutletSearchQuery("")} />
                : <EmptyState icon="LocationPin" title="No outlets" message="No outlets are linked to this beat." />
            )}
          </div>
        </div>
        {droppedOutletCount > 0 ? <SpInlineAlert tone="warning">{`${outletCountLabel(droppedOutletCount)} ${droppedOutletCount === 1 ? "is" : "are"} outside the new scope or already on another beat and will be removed when you save.`}</SpInlineAlert> : null}
        {saveError ? <SpInlineAlert tone="error">{saveError}</SpInlineAlert> : null}
        <SpInlineAlert>You can edit beats that you created. The current version remains active until then.</SpInlineAlert>
      </div>
      <SpStickyFooter>
        {isPendingApproval ? (
          <Button variant="outlined" color="error" label="Withdraw request" loading={mutations.withdraw.isPending} disabled={saving || !approvalRequestId} onClick={() => { void discardChanges(); }} style={{ width: "100%" }} />
        ) : (
          <div className="sp-row">
            <Button variant="outlined" color="neutral" label="Discard" loading={mutations.discardDraft.isPending} disabled={saving || mutations.discardDraft.isPending} onClick={() => { void discardChanges(); }} style={{ flex: 1 }} />
            <Button variant="filled" color="primary" label={submitLabel} loading={saving} disabled={!name.trim() || !zones.length || !states.length || !districts.length || !scopeComplete || !effectiveOutletIds.length || !hasFrequencyDetails || saving} onClick={() => { void saveChanges(); }} style={{ flex: 1.6 }} />
          </div>
        )}
      </SpStickyFooter>
    </SpScreen>
  );
}
