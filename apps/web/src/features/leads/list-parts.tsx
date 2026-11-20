"use client";

import {
  Button,
  DateField,
  EmptyState,
  ErrorState,
  Icon,
  ListRow,
  Skeleton,
  SkeletonRow,
  TextField,
} from "humbee-design-system";
import type { ChangeEvent, ReactNode } from "react";
import { useInfiniteScrollTrigger } from "@/src/shared/state";
import { isLeadIsoDate, leadIsoDate, type LeadDateRange, type LeadFilters } from "./filters";
import { leadInitials, leadShortDate } from "./format";
import { useActorId, type useLeads } from "./hooks";
import type { LeadListItem } from "./service";
import styles from "./leads.module.css";

const DATE_CHIPS: ReadonlyArray<readonly [LeadDateRange, string]> = [
  ["all", "All time"],
  ["month", "This month"],
  ["30", "Last 30 days"],
  ["custom", "Custom"],
];

function displayDate(iso: string): string {
  if (!isLeadIsoDate(iso)) return "";
  // Date-time form without an offset parses as local time (date-only would be UTC).
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function LeadInitials({ name, large = false }: { name: string; large?: boolean }) {
  return (
    <span aria-hidden="true" className={large ? `${styles.initials} ${styles.initialsLarge}` : styles.initials}>
      {leadInitials(name)}
    </span>
  );
}

export function LeadFilterBar({
  filters,
  onChange,
  employeeSlot,
}: {
  filters: LeadFilters;
  onChange: (next: LeadFilters) => void;
  employeeSlot?: ReactNode;
}) {
  const today = leadIsoDate(new Date());
  const selectRange = (range: LeadDateRange) => {
    if (range === filters.range) return;
    onChange(range === "custom"
      ? { ...filters, range }
      : { ...filters, range, from: "", to: "" });
  };

  return (
    <div className={styles.filters}>
      <TextField
        placeholder="Search manufacturer, contact, email"
        fullWidth
        value={filters.q}
        startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
        inputProps={{
          "aria-label": "Search leads",
          type: "search",
          autoComplete: "off",
          autoCapitalize: "none",
          autoCorrect: "off",
          enterKeyHint: "search",
          maxLength: 120,
        }}
        onChange={(event: ChangeEvent) => onChange({ ...filters, q: (event.target as HTMLInputElement).value })}
      />
      {employeeSlot}
      <div className={styles.chips} role="group" aria-label="Date range">
        {DATE_CHIPS.map(([range, label]) => (
          <button
            key={range}
            type="button"
            className="sp-filter-chip"
            data-active={filters.range === range}
            aria-pressed={filters.range === range}
            onClick={() => selectRange(range)}
          >
            {label}
          </button>
        ))}
      </div>
      {filters.range === "custom" ? (
        <div className={styles.dateRow}>
          <DateField
            label="From"
            placeholder="Any date"
            value={displayDate(filters.from)}
            dateValue={filters.from || undefined}
            max={filters.to || today}
            onChange={(from) => onChange({ ...filters, from })}
          />
          <DateField
            label="To"
            placeholder="Today"
            value={displayDate(filters.to)}
            dateValue={filters.to || undefined}
            min={filters.from || undefined}
            max={today}
            onChange={(to) => onChange({ ...filters, to })}
          />
        </div>
      ) : null}
    </div>
  );
}

function LeadRow({
  lead,
  showCapturer,
  viewerId,
  today,
  onOpen,
}: {
  lead: LeadListItem;
  showCapturer: boolean;
  viewerId: string;
  today: Date;
  onOpen: (id: string) => void;
}) {
  const contact = lead.designation ? `${lead.name} · ${lead.designation}` : lead.name;
  const capturer = lead.captured_by.id === viewerId ? "You" : lead.captured_by.name;
  return (
    <ListRow
      leading={<LeadInitials name={lead.company_name} />}
      title={lead.company_name}
      subtitle={showCapturer ? (
        <>
          {contact}
          <span className={styles.capturer}>
            <Icon name="PersonRounded" size={14} color="currentColor" />
            <strong>{capturer}</strong>
          </span>
        </>
      ) : contact}
      meta={leadShortDate(lead.captured_at, today)}
      showChevron
      onClick={() => onOpen(lead.id)}
    />
  );
}

function plural(count: number) {
  return `${count} lead${count === 1 ? "" : "s"}`;
}

export function LeadListBody({
  query,
  showCapturer,
  onOpen,
  emptyState,
  onClearFilters,
  filtersActive,
}: {
  query: ReturnType<typeof useLeads>;
  showCapturer: boolean;
  onOpen: (id: string) => void;
  emptyState: ReactNode;
  onClearFilters: () => void;
  filtersActive: boolean;
}) {
  const viewerId = useActorId();
  const listRef = useInfiniteScrollTrigger<HTMLDivElement>({
    hasNextPage: query.hasNextPage,
    isFetchingNextPage: query.isFetchingNextPage,
    fetchNextPage: query.fetchNextPage,
  });

  if (query.isPending) {
    return (
      <div aria-busy="true" aria-label="Loading leads">
        <div className={styles.countLine}>
          <Skeleton width="32%" height={14} />
        </div>
        <div className={styles.list}>
          {Array.from({ length: 5 }, (_, index) => <SkeletonRow key={index} />)}
        </div>
      </div>
    );
  }

  if (query.isError && !query.data) {
    return (
      <ErrorState
        title="Couldn't load leads"
        message="Check your connection and try again."
        retryLabel="Try again"
        onRetry={() => void query.refetch()}
      />
    );
  }

  const pages = query.data.pages;
  const items = pages.flatMap((page) => page.items);
  const total = pages[0]?.total ?? items.length;

  if (total === 0 || items.length === 0) {
    if (!filtersActive) return <>{emptyState}</>;
    return (
      <EmptyState
        icon="FilterList"
        title="No leads match these filters"
        message="Try a different date range or search."
        actionLabel="Clear filters"
        onAction={onClearFilters}
      />
    );
  }

  const today = new Date();
  const remaining = Math.max(total - items.length, 0);

  return (
    <div>
      <div className={styles.countLine}>
        <span aria-live="polite">
          <strong>{total}</strong> lead{total === 1 ? "" : "s"}
        </span>
        {filtersActive ? (
          <Button variant="text" color="primary" size="small" label="Clear filters" onClick={onClearFilters} />
        ) : null}
      </div>
      <div className={styles.list} ref={listRef}>
        {items.map((lead) => (
          <LeadRow
            key={lead.id}
            lead={lead}
            showCapturer={showCapturer}
            viewerId={viewerId}
            today={today}
            onOpen={onOpen}
          />
        ))}
      </div>
      <div className={styles.listFooter}>
        {query.hasNextPage ? (
          <Button
            variant="outlined"
            color="primary"
            loading={query.isFetchingNextPage}
            label={remaining > 0 ? `Load more (${remaining} left)` : "Load more"}
            onClick={() => void query.fetchNextPage()}
            style={{ width: "100%" }}
          />
        ) : (
          <p className={styles.endNote}>That&apos;s all {plural(total)}</p>
        )}
      </div>
    </div>
  );
}
