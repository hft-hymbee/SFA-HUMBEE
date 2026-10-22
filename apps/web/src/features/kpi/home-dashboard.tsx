"use client";

import { Button, EmptyState, ErrorState, Icon, Select, Skeleton, StatusChip, TextField } from "humbee-design-system";
import { useRouter } from "next/navigation";
import { Fragment, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { flattenApprovals, useMyRequests } from "@/src/features/approvals/hooks";
import {
  requestChip,
  requestDisplayTitle,
  requestSubjectHref,
  submittedRelativeLabel,
} from "@/src/features/approvals/service";
import { istBusinessDate } from "@/src/features/attendance/service";
import { useManagementRouter } from "@/src/features/management/role-context";
import { ManagementScreen } from "@/src/features/management/ui";
import { useTeamCoverage } from "@/src/features/routes/service";
import { useEmployeeTargets, useTargetManufacturers } from "@/src/features/targets/hooks";
import { getServerSession, readSessionSync, subscribeToSession } from "@/src/shared/auth/session";
import {
  formatKpiDate,
  formatManufacturerQuantity,
  formatMonthLabel,
  formatMonthShort,
  initialsFromName,
  leagueBarFill,
  manufacturerRows,
  moneyFromPaise,
  monthDayProgress,
  monthPacePct,
  periodMonthFromBusinessDate,
  requiredDailyRateLabel,
  previousMonthLabel,
  progressColorBaseline,
  progressColorPct,
  progressScale,
  rosterCounts,
  rosterFromCoverage,
  rosterTone,
  shortDisplayName,
  spRollupOrderValueLabel,
  spRollupOrderVolumeLabel,
  toInNumber,
  visitHasValues,
  visitModelFromMetrics,
  visitSplitParts,
  workingDaysLeft,
  type ManufacturerRow,
  type VisitModel,
  type VisitSplitPart,
  type VisitWindow,
} from "./dashboard-model";
import {
  useAdminDashboardKpis,
  useManagerDashboardKpis,
  useSpAttention,
  useSpDashboardKpis,
  useSpTargetsKpis,
} from "./hooks";
import styles from "./home-dashboard.module.css";
import { KpiQueryFallback } from "./kpi-surface";
import type {
  AdminDashboardKpisResponse,
  AttentionKind,
  ManagerDashboardKpisResponse,
  SpAttentionResponse,
  SpTargetsKpisResponse,
} from "./service";

type DashboardTargetLine = NonNullable<SpTargetsKpisResponse["targets"]>[number];
type CountTarget = NonNullable<SpTargetsKpisResponse["count_targets"]>[number];

const COUNT_TARGET_CARDS: Record<CountTarget["target_type"], { title: string; tag: string; cta: string; href: string }> = {
  outlets: { title: "Outlets onboarded", tag: "MTD · manager-approved", cta: "Onboard outlet", href: "/sp/outlets/new" },
  leads: { title: "Leads captured", tag: "MTD", cta: "Capture lead", href: "/sp/leads/new" },
};
type ManagerScatterPoint = NonNullable<ManagerDashboardKpisResponse["scatter"]>[number];
type PlottedScatterPoint = ManagerScatterPoint & { adherence_pct: number; conversion_pct: number };
type ManagerLeagueRow = NonNullable<ManagerDashboardKpisResponse["league"]>[number];
type AdminMovementRow = NonNullable<AdminDashboardKpisResponse["manufacturer_movement"]>[number];

const SCATTER_W = 311;
const SCATTER_H = 248;
const SCATTER_PLOT = { h: 188, w: 259, x: 40, y: 18 };

function clampPct(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, value));
}

function scatterPlotX(pct: number) {
  return SCATTER_PLOT.x + (clampPct(pct) / 100) * SCATTER_PLOT.w;
}

function scatterPlotY(pct: number) {
  return SCATTER_PLOT.y + ((100 - clampPct(pct)) / 100) * SCATTER_PLOT.h;
}

function useSessionProfile() {
  const session = useSyncExternalStore(subscribeToSession, readSessionSync, getServerSession);
  return {
    displayName: session?.displayName ?? "",
    employeeId: session?.employeeId ?? "",
  };
}

function ScopeRow({ label, date }: { label: string; date: string }) {
  return (
    <div className={styles.scope}>
      <Icon name="LocationMarker" size={16} color="var(--ink-3)" />
      <span>{label}</span>
      <span className={styles.scopeDate}>{date}</span>
    </div>
  );
}

export function SectionHeader({
  action,
  id,
  label,
}: {
  action?: ReactNode;
  id?: string;
  label: string;
}) {
  return (
    <div className={styles.section}>
      <span>{label}</span>
      {id ? <span className={styles.sectionId}>{id}</span> : null}
      <span className={styles.sectionRule} aria-hidden="true" />
      {action}
    </div>
  );
}

function VisitSpineBar({ parts }: { parts: VisitSplitPart[] }) {
  const visible = parts.filter((part) => part.value > 0);
  if (!visible.length) {
    return (
      <div className={styles.spine}>
        <span className={`${styles.spineSeg} ${styles.spineRest}`} style={{ background: "var(--n-200)", flexGrow: 1 }} />
      </div>
    );
  }
  return (
    <div className={styles.spine}>
      {visible.map((part) => (
        <span
          className={`${styles.spineSeg} ${part.label === "Still to go" ? styles.spineRest : ""}`}
          key={part.label}
          style={{ background: part.color, flexGrow: part.value, minWidth: 8 }}
        />
      ))}
    </div>
  );
}

function ChartUnavailable({ title, message }: { title: string; message: string }) {
  return (
    <EmptyState icon="Dashboard" title={title} message={message} />
  );
}

function CoverageScatterChart({ points }: { points: PlottedScatterPoint[] }) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = points.find((point) => point.employee_id === activeId) ?? null;
  const stacked = active
    ? points.filter(
        (point) =>
          point.adherence_pct === active.adherence_pct
          && point.conversion_pct === active.conversion_pct,
      )
    : [];
  const midX = scatterPlotX(50);
  const midY = scatterPlotY(50);
  const plotRight = SCATTER_PLOT.x + SCATTER_PLOT.w;
  const plotBottom = SCATTER_PLOT.y + SCATTER_PLOT.h;
  const activeX = active ? scatterPlotX(active.adherence_pct) : 0;
  const activeY = active ? scatterPlotY(active.conversion_pct) : 0;
  const tooltipBelow = activeY < 56;
  const tooltipSide = activeX < 72 ? "start" : activeX > SCATTER_W - 72 ? "end" : "center";

  return (
    <div
      className={styles.managerScatterChart}
      onPointerDown={(event) => {
        const target = event.target as HTMLElement;
        if (!target.closest("[data-scatter-dot]")) setActiveId(null);
      }}
    >
      <svg
        aria-hidden="true"
        className={styles.managerScatterPlot}
        viewBox={`0 0 ${SCATTER_W} ${SCATTER_H}`}
      >
        <rect
          fill="var(--success)"
          height={midY - SCATTER_PLOT.y}
          opacity="0.05"
          width={plotRight - midX}
          x={midX}
          y={SCATTER_PLOT.y}
        />
        <rect
          fill="var(--error)"
          height={plotBottom - midY}
          opacity="0.04"
          width={midX - SCATTER_PLOT.x}
          x={SCATTER_PLOT.x}
          y={midY}
        />
        <g stroke="var(--n-300)" strokeWidth="1">
          <line x1={SCATTER_PLOT.x} x2={SCATTER_PLOT.x} y1={SCATTER_PLOT.y} y2={plotBottom} />
          <line x1={SCATTER_PLOT.x} x2={plotRight} y1={plotBottom} y2={plotBottom} />
        </g>
        <g stroke="var(--n-400)" strokeDasharray="4 3" strokeWidth="1">
          <line x1={midX} x2={midX} y1={SCATTER_PLOT.y} y2={plotBottom} />
          <line x1={SCATTER_PLOT.x} x2={plotRight} y1={midY} y2={midY} />
        </g>
        <text className={styles.scatterSvgHint} x={SCATTER_PLOT.x + 6} y={SCATTER_PLOT.y + 12}>High conversion</text>
        <text className={styles.scatterSvgHintStrong} textAnchor="end" x={plotRight - 6} y={SCATTER_PLOT.y + 12}>Strong on both</text>
        <text className={styles.scatterSvgHint} x={SCATTER_PLOT.x + 6} y={plotBottom - 8}>Needs Help</text>
        <text className={styles.scatterSvgHint} textAnchor="end" x={plotRight - 6} y={plotBottom - 8}>High productivity</text>
        <text className={styles.scatterSvgTick} textAnchor="end" x={SCATTER_PLOT.x - 6} y={SCATTER_PLOT.y + 4}>100</text>
        <text className={styles.scatterSvgTick} textAnchor="end" x={SCATTER_PLOT.x - 6} y={midY + 3}>50</text>
        <text className={styles.scatterSvgTick} textAnchor="end" x={SCATTER_PLOT.x - 6} y={plotBottom}>0</text>
        <text className={styles.scatterSvgTick} textAnchor="middle" x={SCATTER_PLOT.x} y={plotBottom + 14}>0</text>
        <text className={styles.scatterSvgTick} textAnchor="middle" x={midX} y={plotBottom + 14}>50</text>
        <text className={styles.scatterSvgTick} textAnchor="middle" x={plotRight} y={plotBottom + 14}>100</text>
        <text className={styles.scatterSvgAxis} textAnchor="middle" x={SCATTER_PLOT.x + SCATTER_PLOT.w / 2} y={SCATTER_H - 6}>Productivity %</text>
        <text
          className={styles.scatterSvgAxis}
          textAnchor="middle"
          transform={`rotate(-90 12 ${SCATTER_PLOT.y + SCATTER_PLOT.h / 2})`}
          x="12"
          y={SCATTER_PLOT.y + SCATTER_PLOT.h / 2}
        >
          Conversion %
        </text>
      </svg>
      {points.map((point) => {
        const x = scatterPlotX(point.adherence_pct);
        const y = scatterPlotY(point.conversion_pct);
        const isActive = point.employee_id === activeId;
        return (
          <button
            aria-label={`${point.name}, productivity ${point.adherence_pct} percent, conversion ${point.conversion_pct} percent`}
            className={`${styles.scatterDot} ${isActive ? styles.scatterDotActive : ""}`}
            data-scatter-dot=""
            key={point.employee_id}
            style={{ left: `${(x / SCATTER_W) * 100}%`, top: `${(y / SCATTER_H) * 100}%` }}
            type="button"
            onBlur={() => setActiveId((current) => (current === point.employee_id ? null : current))}
            onClick={() => setActiveId(point.employee_id)}
            onFocus={() => setActiveId(point.employee_id)}
            onMouseEnter={() => setActiveId(point.employee_id)}
            onMouseLeave={() => {
              if (typeof window !== "undefined" && window.matchMedia("(hover: hover)").matches) {
                setActiveId((current) => (current === point.employee_id ? null : current));
              }
            }}
          >
            <span className={styles.scatterDotPip} />
          </button>
        );
      })}
      {active ? (
        <div
          className={[
            styles.scatterTooltip,
            tooltipSide === "start" ? styles.scatterTooltipStart : tooltipSide === "end" ? styles.scatterTooltipEnd : styles.scatterTooltipCenter,
            tooltipBelow ? styles.scatterTooltipBelow : "",
          ].join(" ")}
          style={{ left: `${(activeX / SCATTER_W) * 100}%`, top: `${(activeY / SCATTER_H) * 100}%` }}
        >
          {stacked.map((point) => (
            <div className={styles.scatterTooltipRow} key={point.employee_id}>
              <span className={styles.scatterTooltipName}>{point.name}</span>
              <span className={styles.scatterTooltipMeta}>
                <span className={styles.num}>{point.adherence_pct}%</span> productivity
                {" · "}
                <span className={styles.num}>{point.conversion_pct}%</span> conversion
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function TeamPerformanceNav() {
  const router = useManagementRouter();
  return (
    <button
      aria-label="Open team performance"
      className={styles.perfNav}
      type="button"
      onClick={() => router.push("/mgmt/team-performance")}
    >
      <span aria-hidden="true" className={styles.perfNavIcon}>
        <Icon name="Dashboard" size={22} color="var(--color-primary)" />
      </span>
      <span className={styles.perfNavCopy}>
        <strong>Team performance</strong>
        <span>Manufacturer mix, team against target, league and district</span>
      </span>
      <span className={styles.perfNavCta}>
        Open
        <Icon name="KeyboardArrowRight" size={18} color="currentColor" />
      </span>
    </button>
  );
}

function designationLabel(code: string) {
  if (code === "all") return "All levels";
  return code
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function MetricTile({
  label,
  value,
  sub,
  tone,
  muted,
  borderColor,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
  muted?: boolean;
  borderColor?: string;
}) {
  return (
    <div
      className={`${styles.tile} ${muted ? styles.tileMuted : ""} ${borderColor ? styles.tileStat : ""}`}
      style={borderColor ? { borderTopColor: borderColor } : undefined}
    >
      <span className={styles.tileLabel}>{label}</span>
      <span className={`${styles.tileValue} ${styles.num}`} style={tone ? { color: tone } : undefined}>{value}</span>
      {sub ? <span className={`${styles.tileSub} ${styles.num}`}>{sub}</span> : null}
    </div>
  );
}

function ManufacturerScopedList({
  rows,
  selectedId,
  onSelect,
  onClose,
}: {
  rows: ManufacturerRow[];
  selectedId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  return createPortal(
    <div className={styles.scopedModal} role="dialog" aria-modal="true" aria-label="Select manufacturer">
      <div className={styles.scopedModalOverlay} onClick={onClose} />
      <div className={styles.scopedModalContent}>
        <span className={styles.scopedModalHandle} aria-hidden="true" />
        <div className={styles.scopedModalHeader}>
          <h3>Select manufacturer</h3>
          <button
            aria-label="Close"
            className={styles.scopedModalClose}
            type="button"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className={styles.scopedModalList} role="listbox">
          {rows.map((row) => {
            const isOn = selectedId === row.id;
            return (
              <button
                key={row.id}
                className={`${styles.scopedItem} ${isOn ? styles.scopedItemOn : ""}`}
                type="button"
                role="option"
                aria-selected={isOn}
                onClick={() => {
                  onSelect(row.id);
                  onClose();
                }}
              >
                <span className={styles.scopedItemName}>{row.name}</span>
                <span className={`${styles.scopedItemUnit} ${styles.num}`}>{row.unit}</span>
                {isOn && <Icon name="Check" size={18} color="var(--primary)" />}
              </button>
            );
          })}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function ManufacturerScoper({
  assignedOnly = false,
  embedded = false,
  rows,
  selectedId,
  onSelect,
}: {
  assignedOnly?: boolean;
  embedded?: boolean;
  rows: ManufacturerRow[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const visible = assignedOnly ? rows.filter((row) => row.hasTarget) : rows;
  const selected = visible.find((r) => r.id === selectedId);

  if (!rows.length) {
    return <ChartUnavailable title="No manufacturers" message="No manufacturer catalog was returned for this tenant." />;
  }
  if (assignedOnly && !visible.length) {
    return (
      <ChartUnavailable
        title="No targets assigned"
        message="No manufacturer target is assigned to you this month."
      />
    );
  }

  const header = (
    <div className={styles.scoperHd}>
      <span className={styles.scoperLb}>Manufacturer</span>
      <button
        className={styles.scoperAll}
        type="button"
        onClick={() => setShowAll(true)}
        aria-haspopup="listbox"
        aria-expanded={showAll}
        aria-label="Change manufacturer"
        title={selected ? selected.name : `All ${visible.length} manufacturers`}
      >
        <span className={styles.scoperAllLb}>{selected ? selected.name : `All ${visible.length}`}</span>
        <Icon name="KeyboardArrowDown" size={16} color="currentColor" />
      </button>
    </div>
  );

  return (
    <>
      {embedded ? header : <div className={styles.scoper}>{header}</div>}
      {showAll && (
        <ManufacturerScopedList
          rows={visible}
          selectedId={selectedId}
          onSelect={onSelect}
          onClose={() => setShowAll(false)}
        />
      )}
    </>
  );
}

function VisitCard({
  layout = "hero",
  loading = false,
  model,
  title,
  window,
  onWindowChange,
}: {
  layout?: "compact" | "hero";
  loading?: boolean;
  model: VisitModel;
  title: string;
  window?: VisitWindow;
  onWindowChange?: (next: VisitWindow) => void;
}) {
  const compact = layout === "compact";
  const parts = visitSplitParts(model, true);
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <h3>{title}</h3>
        {onWindowChange && window ? (
          <span className={styles.tog}>
            <button type="button" className={window === "today" ? styles.togOn : undefined} onClick={() => onWindowChange("today")}>Today</button>
            <button type="button" className={window === "mtd" ? styles.togOn : undefined} onClick={() => onWindowChange("mtd")}>MTD</button>
          </span>
        ) : model.planned !== null && model.visited !== null ? (
          <span className={`${styles.cardMeta} ${styles.num}`}>{toInNumber(model.visited)} of {toInNumber(model.planned)} planned</span>
        ) : null}
      </div>
      {loading ? (
        <Skeleton height={compact ? 88 : 140} radius={8} />
      ) : visitHasValues(model) ? (
        <>
          {compact ? null : (
            <div className={styles.bigHead}>
              <span className={`${styles.bigValue} ${styles.num}`}>{model.visited !== null ? toInNumber(model.visited) : "—"}</span>
              <span className={styles.bigOf}>{model.planned !== null ? `of ${toInNumber(model.planned)} planned` : "visits completed"}</span>
            </div>
          )}
          <VisitSpineBar parts={parts} />
          <div className={styles.spineLegend}>
            {parts.map((part) => (
              <span className={styles.spineLegendItem} key={part.label}>
                <span className={`${styles.dot} ${part.label === "Still to go" ? styles.dotBordered : ""}`} style={{ background: part.color }} />
                {part.label} <b className={styles.num}>{toInNumber(part.value)}</b>
              </span>
            ))}
          </div>
          <div className={styles.chipRow}>
            {compact ? (
              <>
                <span className={styles.chip}>TC <b>{model.tc ?? "—"}</b></span>
                <span className={styles.chip}>PC <b>{model.pc ?? "—"}</b></span>
                <span className={styles.chip}>UTC <b>{model.utc ?? "—"}</b></span>
              </>
            ) : (
              <>
                <span className={styles.chip}>TC <b>{model.tc ?? "—"}</b></span>
                <span className={styles.chip}>PC <b>{model.pc ?? "—"}</b></span>
                <span className={styles.chip}>UTC <b>{model.utc ?? "—"}</b></span>
                <span className={styles.chip}>ZO <b>{model.zo ?? "—"}</b></span>
              </>
            )}
          </div>
        </>
      ) : (
        <ChartUnavailable title="Visit split unavailable" message="Planned, visited and productive counts were not returned for this window." />
      )}
    </div>
  );
}

function TargetHero({
  eyebrow,
  rows,
  daysLeft,
}: {
  eyebrow: string;
  rows: ManufacturerRow[];
  daysLeft: number | null;
}) {
  const [open, setOpen] = useState(false);
  const assignedRows = rows.filter((row) => row.hasTarget);
  const withTarget = assignedRows.length;
  return (
    <div className={styles.targetPanel}>
      <button
        aria-expanded={open}
        className={styles.targetPanelHead}
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        <span className={styles.targetPanelTitle}>
          <span className={styles.heroEyebrow}>{eyebrow}</span>
          <span className={`${styles.targetPanelChevron} ${open ? styles.targetPanelChevronOpen : ""}`}>
            <Icon name="KeyboardArrowDown" size={20} color="currentColor" />
          </span>
        </span>
        <span className={styles.targetPanelStats}>
          <span>
            <span className={`${styles.heroBig} ${styles.num}`}>{withTarget}</span>
            <span className={styles.heroSub}>{withTarget === 1 ? "target assigned" : "targets assigned"}</span>
          </span>
          <span>
            <span className={`${styles.heroBig} ${styles.num}`}>{daysLeft !== null ? daysLeft : "—"}</span>
            <span className={styles.heroSub}>working days left</span>
          </span>
        </span>
      </button>
      {open ? (
        assignedRows.length ? (
          <div className={styles.targetPanelBody}>
            {assignedRows.map((row) => (
              <div className={styles.targetLine} key={row.id}>
                <span className={styles.targetMark}>
                  {initialsFromName(row.name)}
                </span>
                <span className={styles.targetLineCopy}>
                  <b>{row.name}</b>
                  <span>{row.unit}</span>
                </span>
                <span className={`${styles.targetLineValue} ${styles.num}`}>
                  {row.targetLabel}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.targetPanelEmpty}>No manufacturer targets this month.</div>
        )
      ) : null}
    </div>
  );
}

function DailyBookingsChart({
  businessDate,
  neededLabel,
  progress,
  unit,
}: {
  businessDate: string;
  neededLabel: string | null;
  progress: { day: number; total: number } | null;
  unit: string;
}) {
  const month = formatMonthShort(businessDate);
  return (
    <div className={styles.dailyChart}>
      <div className={styles.dailyChartAxis}>
        <span>{month ? `1 ${month}` : ""}</span>
        <span>{progress && month ? `${progress.day} ${month}` : ""}</span>
      </div>
      <div className={styles.spineLegend}>
        <span className={styles.spineLegendItem}>
          <span className={styles.dot} style={{ background: "var(--primary)" }} />
          {unit} booked per day
        </span>
        {neededLabel ? (
          <span className={styles.spineLegendItem}>
            <span className={styles.legendDash} />
            <b className={styles.num}>{neededLabel}</b> needed
          </span>
        ) : null}
      </div>
    </div>
  );
}

function SalesPerformanceCard({
  businessDate,
  momPct,
  progress,
  selected,
  selectedId,
  targetLine,
  title = "Target progress",
}: {
  businessDate: string;
  momPct?: number | null;
  progress: { day: number; total: number } | null;
  selected: ManufacturerRow | undefined;
  selectedId: string;
  targetLine?: {
    basis: string;
    pct: number | null;
    taken_paise: number;
    taken_qty: number;
    taken_lines: number;
    target_value: number;
  } | null;
  title?: string;
}) {
  const pacePct = monthPacePct(businessDate);
  const daysLeft = workingDaysLeft(businessDate);
  const daysMeta = progress ? `${progress.day} of ${progress.total} days` : null;
  const prevMonth = previousMonthLabel(businessDate);
  const compareAll = selectedId === "all";

  if (compareAll || !selected?.hasTarget) {
    return (
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3>{title}</h3>
          {selected && !compareAll ? <span className={styles.metricTag}>{selected.name}</span> : null}
        </div>
        <ChartUnavailable
          title={selected ? "No target set" : "Compare all"}
          message={
            selected
              ? `${selected.name} has no target this month.`
              : "Pick one manufacturer to see target progress in its own unit."
          }
        />
      </div>
    );
  }

  const targetDisplay = selected.targetValue !== null
    ? formatManufacturerQuantity(selected.targetValue, selected.basis)
    : selected.targetLabel;
  // What is still owed, not the whole target spread over the whole month — a target already
  // cleared needs nothing per day.
  const takenValue = targetLine
    ? targetLine.basis === "amount" ? targetLine.taken_paise : targetLine.taken_qty
    : null;
  const remaining = selected.targetValue !== null && takenValue !== null
    ? Math.max(selected.targetValue - takenValue, 0)
    : null;
  const targetMet = remaining === 0;
  const neededLegend = requiredDailyRateLabel(remaining, daysLeft, selected.basis);
  const neededCopy = requiredDailyRateLabel(remaining, daysLeft, selected.basis, selected.unit);
  const paceLeft = pacePct != null ? `${Math.min(pacePct, 100)}%` : null;
  const achievementPct = targetLine?.pct != null ? clampPct(targetLine.pct) : null;
  const takenLabel = targetLine
    ? targetLine.basis === "amount"
      ? moneyFromPaise(targetLine.taken_paise)
      : formatManufacturerQuantity(targetLine.taken_qty, selected.basis)
    : "—";
  const pctLabel = targetLine?.pct != null ? `${targetLine.pct}%` : "—";

  return (
    <>
      <div className={`${styles.card} ${styles.targetProgressCard}`}>
        <div className={styles.cardHeader}>
          <h3>{title}</h3>
          <span className={styles.metricTag}>{selected.name}</span>
          {daysMeta ? <span className={`${styles.cardMeta} ${styles.num}`}>{daysMeta}</span> : null}
        </div>
        <div className={styles.bigHead}>
          <span className={`${styles.bigValue} ${styles.num}`}>{takenLabel}</span>
          <span className={styles.bigUnit}>{selected.unit}</span>
          <span className={`${styles.bigOf} ${styles.num}`}>of {targetDisplay}</span>
          <span className={`${styles.bigPct} ${styles.bigPctAccent} ${styles.num}`}>{pctLabel}</span>
        </div>
        <div className={styles.paceTrack}>
          <div className={styles.paceBar}>
            {achievementPct !== null ? <span className={styles.paceFill} style={{ width: `${achievementPct}%` }} /> : null}
            {paceLeft ? <span className={styles.paceMark} style={{ left: paceLeft }} /> : null}
          </div>
          {paceLeft ? (
            <span className={`${styles.targetPaceLabel} ${styles.num}`} style={{ left: paceLeft }}>
              pace {pacePct}%
            </span>
          ) : null}
        </div>
        <DailyBookingsChart
          businessDate={businessDate}
          neededLabel={neededLegend}
          progress={progress}
          unit={selected.unit}
        />
        <div className={styles.note}>
          <Icon name="InfoFilled" size={15} color="var(--ink-3)" />
          <span>
            {pacePct !== null ? <>Pace today is <b>{pacePct}%</b>. </> : null}
            {targetMet ? <>Target of <b>{targetDisplay}</b> cleared</> : (
              <>
                Clearing <b>{targetDisplay}</b>
                {neededCopy ? <> needs <b className={styles.num}>{neededCopy}</b></> : null}
              </>
            )}
            {daysLeft !== null ? <>. <b>{daysLeft} working {daysLeft === 1 ? "day" : "days"}</b> left</> : null}.
          </span>
        </div>
      </div>
      <div className={styles.grid2}>
        <MetricTile
          label={`${selected.name} lines`}
          muted={!targetLine || targetLine.taken_lines === 0}
          value={targetLine ? toInNumber(targetLine.taken_lines) : "—"}
        />
        <MetricTile
          label={`vs ${prevMonth}`}
          muted={momPct == null}
          value={momPct != null ? `${momPct}%` : "—"}
        />
      </div>
    </>
  );
}

export function SalespersonVisitsSection() {
  const router = useRouter();
  const [visitsWindow, setVisitsWindow] = useState<VisitWindow>("today");
  const todayRollup = useSpDashboardKpis("today");
  const mtdRollup = useSpDashboardKpis("mtd");
  const rollup = visitsWindow === "today" ? todayRollup : mtdRollup;
  const visitModel = visitModelFromMetrics(rollup.data?.metrics, visitsWindow);
  const orderValue = spRollupOrderValueLabel(rollup.data?.metrics);
  const orderVolume = spRollupOrderVolumeLabel(rollup.data?.metrics);

  if (todayRollup.isPending || (todayRollup.isError && !todayRollup.data)) {
    return (
      <div className={`${styles.dashboardBody} ${styles.dashboardBodyFlush}`}>
        {todayRollup.isPending ? (
          <>
            <Skeleton height={18} radius={8} />
            <Skeleton height={168} radius={12} />
            <Skeleton height={88} radius={12} />
          </>
        ) : (
          <div className={styles.card}>
            <ErrorState
              title="Visit data unavailable"
              message="Live visit metrics could not be loaded."
              onRetry={() => {
                void todayRollup.refetch();
                void mtdRollup.refetch();
              }}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`${styles.dashboardBody} ${styles.dashboardBodyFlush}`}>
      <SectionHeader
        action={(
          <button
            className={styles.sectionAction}
            type="button"
            onClick={() => router.push("/sp/my-day")}
          >
            View my day
          </button>
        )}
        label="Visits"
      />
      <VisitCard
        loading={visitsWindow === "mtd" && mtdRollup.isPending}
        model={visitModel}
        title={visitsWindow === "today" ? "Visits today" : "Visits MTD"}
        window={visitsWindow}
        onWindowChange={setVisitsWindow}
      />
      <div className={styles.grid3}>
        <MetricTile
          label="Orders"
          muted={!visitModel.orders}
          sub="submitted"
          value={visitModel.orders ?? "—"}
        />
        <MetricTile
          label="Order value"
          muted={!orderValue}
          sub={orderValue ? "booked" : "unavailable"}
          value={orderValue ?? "—"}
        />
        <MetricTile
          label="Order volume"
          muted={!orderVolume}
          sub={orderVolume ? "booked" : "unavailable"}
          value={orderVolume ?? "—"}
        />
      </div>
    </div>
  );
}

function ManagerDashboardContent() {
  const router = useRouter();
  const profile = useSessionProfile();
  const coverage = useTeamCoverage({ onlySalesPerson: true });
  const [visitsWindow, setVisitsWindow] = useState<VisitWindow>("today");
  const todayRollup = useManagerDashboardKpis("today");
  const mtdRollup = useManagerDashboardKpis("mtd");
  const rollup = visitsWindow === "today" ? todayRollup : mtdRollup;

  const businessDate = todayRollup.data?.business_date ?? coverage.data?.business_date ?? "";
  const todayMetrics = todayRollup.data?.team_metrics;
  const mtdMetrics = mtdRollup.data?.team_metrics;
  const visitModel = visitModelFromMetrics(rollup.data?.team_metrics, visitsWindow);
  const people = useMemo(() => rosterFromCoverage(coverage.data?.items), [coverage.data?.items]);
  const counts = useMemo(() => rosterCounts(people), [people]);
  const pendingApprovals = todayMetrics?.pending_approvals;
  const idle = todayMetrics?.no_punch_in;
  const exceptions = pendingApprovals != null && idle != null ? pendingApprovals + idle : null;
  const scatter: ManagerScatterPoint[] = mtdRollup.data?.scatter ?? [];
  const scatterPoints = scatter.filter(
    (point): point is PlottedScatterPoint =>
      point.adherence_pct != null && point.conversion_pct != null,
  );

  if (todayRollup.isPending || (todayRollup.isError && !todayRollup.data)) {
    return (
      <KpiQueryFallback
        empty={false}
        isError={todayRollup.isError}
        isPending={todayRollup.isPending}
        onRetry={() => {
          void todayRollup.refetch();
          void mtdRollup.refetch();
        }}
      />
    );
  }

  const outletsOnboarded = mtdMetrics?.outlets_onboarded_count;
  const leadsCaptured = mtdMetrics?.leads_captured_count;

  return (
    <div className={styles.dashboardBody}>
      <ScopeRow
        date={formatKpiDate(businessDate)}
        label={todayMetrics?.team_size != null ? `Your tree · ${todayMetrics.team_size} people` : (profile.displayName || "Your tree")}
      />
      <SectionHeader label="Needs attention" />
      <div className={styles.card}>
        <div className={styles.triageGrid}>
          <div className={styles.triageTile}>
            <span className={`${styles.triageValue} ${pendingApprovals ? styles.warn : ""}`}>{pendingApprovals ?? "—"}</span>
            <span className={styles.triageLabel}>Approvals waiting</span>
          </div>
          <div className={styles.triageTile}>
            <span className={styles.triageValue}>{exceptions ?? "—"}</span>
            <span className={styles.triageLabel}>Exceptions</span>
          </div>
          <div className={styles.triageTile}>
            <span className={`${styles.triageValue} ${idle ? styles.bad : ""}`}>{idle ?? "—"}</span>
            <span className={styles.triageLabel}>No punch-in yet</span>
          </div>
        </div>
      </div>

      <SectionHeader label="Team today" />
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3>Who is out there</h3>
          <span className={styles.cardMeta}>
            {todayMetrics?.on_duty != null && todayMetrics.team_size != null
              ? `${todayMetrics.on_duty} of ${todayMetrics.team_size} on duty`
              : null}
          </span>
        </div>
        {people.length ? (
          <>
            <div className={styles.rosterGrid}>
              {people.map((person) => {
                const tone = rosterTone(person.status);
                const timelineHref = `/mgmt/team-day?id=${encodeURIComponent(person.id)}&name=${encodeURIComponent(person.name)}&date=${encodeURIComponent(businessDate)}`;
                return (
                  <button
                    type="button"
                    className={styles.rosterChip}
                    key={person.id}
                    onClick={() => router.push(timelineHref)}
                  >
                    <span className={styles.avatar} style={{ background: tone.bg, color: tone.ink }}>
                      {person.initials}
                      <span className={styles.statusPip} style={{ background: tone.pip }} />
                    </span>
                    <span className={styles.avatarName} title={person.name}>{person.name}</span>
                  </button>
                );
              })}
            </div>
            <div className={styles.spineLegend}>
              <span className={styles.spineLegendItem}><span className={`${styles.dot} ${styles.dotRound}`} style={{ background: "var(--success)" }} />Visiting <b>{counts.visiting}</b></span>
              <span className={styles.spineLegendItem}><span className={`${styles.dot} ${styles.dotRound}`} style={{ background: "var(--accent-active)" }} />No visit yet <b>{counts.waiting}</b></span>
              <span className={styles.spineLegendItem}><span className={`${styles.dot} ${styles.dotRound}`} style={{ background: "var(--info)" }} />On leave <b>{counts.leave}</b></span>
              <span className={styles.spineLegendItem}><span className={`${styles.dot} ${styles.dotRound}`} style={{ background: "var(--ink-2)" }} />Punched out <b>{counts.none}</b></span>
              <span className={styles.spineLegendItem}><span className={`${styles.dot} ${styles.dotRound}`} style={{ background: "var(--ink-4)" }} />No punch-in <b>{counts.punch}</b></span>
            </div>
          </>
        ) : (
          <ChartUnavailable title="No team rows" message="Team coverage did not return people for today." />
        )}
      </div>

      <VisitCard
        layout="compact"
        loading={visitsWindow === "mtd" && mtdRollup.isPending}
        model={visitModel}
        title={visitsWindow === "today" ? "Visits today" : "Visits MTD"}
        window={visitsWindow}
        onWindowChange={setVisitsWindow}
      />

      <SectionHeader label="Where to spend your week" />
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3>Coverage vs conversion</h3>
          <span className={styles.cardMeta}>Each dot is a rep · MTD</span>
        </div>
        {mtdRollup.isPending ? (
          <Skeleton height={248} radius={8} />
        ) : scatterPoints.length ? (
          <CoverageScatterChart points={scatterPoints} />
        ) : (
          <ChartUnavailable
            title="Scatter unavailable"
            message="No per-rep productivity and conversion points for this month."
          />
        )}
      </div>

      <TeamPerformanceNav />


      <SectionHeader label="Team reach" />
      <div className={styles.grid2}>
        <MetricTile
          label="New outlets onboarded"
          muted={outletsOnboarded == null}
          value={outletsOnboarded != null ? toInNumber(outletsOnboarded) : "—"}
        />
        <MetricTile
          label="New leads captured"
          muted={leadsCaptured == null}
          value={leadsCaptured != null ? toInNumber(leadsCaptured) : "—"}
        />
      </div>
    </div>
  );
}

function ManufacturerMovementChart({ movement }: { movement: AdminMovementRow[] }) {
  const SVG_WIDTH = 311;
  const SVG_HEIGHT = 14 + movement.length * 30 + 24;
  const CENTER_X = 178.5;
  const TEN_PCT_WIDTH = 221.75 - CENTER_X;

  const clampedMovement = movement.map((row) => ({
    ...row,
    clampedPct: Math.max(-10, Math.min(10, row.mom_pct ?? 0)),
  }));

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        width={SVG_WIDTH}
        height={SVG_HEIGHT}
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        style={{ overflow: "visible", minWidth: "100%" }}
      >
        {/* Grid lines */}
        <g stroke="var(--n-200)" strokeWidth="1" strokeDasharray="3 3">
          <line x1="135.25" y1="6" x2="135.25" y2={SVG_HEIGHT - 24} />
          <line x1="221.75" y1="6" x2="221.75" y2={SVG_HEIGHT - 24} />
        </g>
        <line x1={CENTER_X} y1="6" x2={CENTER_X} y2={SVG_HEIGHT - 24} stroke="var(--n-400)" strokeWidth="1" />

        {/* Bars */}
        {clampedMovement.map((row, index) => {
          const y = 13 + index * 30;
          const barWidth = (Math.abs(row.clampedPct) / 10) * TEN_PCT_WIDTH;
          const isPositive = row.clampedPct >= 0;
          const barX = isPositive ? CENTER_X : CENTER_X - barWidth;
          const barColor = isPositive ? "var(--success)" : "var(--error)";

          return (
            <g key={row.manufacturer_id}>
              <rect
                x={barX}
                y={y}
                width={barWidth}
                height="14"
                rx="2"
                fill={barColor}
              />
            </g>
          );
        })}

        {/* Labels and values */}
        <g fontFamily="Lato" textAnchor="end" style={{ fontVariantNumeric: "tabular-nums" }}>
          {clampedMovement.map((row, index) => {
            const y = 13 + index * 30;
            return (
              <g key={`label-${row.manufacturer_id}`}>
                <text
                  x="86"
                  y={y + 5}
                  fontSize="12"
                  fontWeight="700"
                  fill="var(--ink)"
                >
                  {row.label}
                </text>
                <text
                  x="86"
                  y={y + 18}
                  fontSize="10.5"
                  fill="var(--ink-3)"
                >
                  {moneyFromPaise(row.mtd_paise)}
                </text>
              </g>
            );
          })}
        </g>

        {/* Growth percentages on right */}
        <g fontFamily="Lato" fontSize="13" fontWeight="700" textAnchor="end" style={{ fontVariantNumeric: "tabular-nums" }}>
          {clampedMovement.map((row, index) => {
            const y = 13 + index * 30;
            const isPositive = row.clampedPct >= 0;
            const color = isPositive ? "var(--success)" : "var(--error)";
            const sign = isPositive && row.mom_pct !== 0 ? "+" : "";
            return (
              <text
                key={`pct-${row.manufacturer_id}`}
                x={SVG_WIDTH}
                y={y + 12}
                fill={color}
              >
                {row.mom_pct != null ? `${sign}${row.mom_pct}%` : "—"}
              </text>
            );
          })}
        </g>

        {/* Bottom axis labels */}
        <g fontFamily="Lato" fontSize="9.5" fill="var(--ink-3)" textAnchor="middle" style={{ fontVariantNumeric: "tabular-nums" }}>
          <text x="135.25" y={SVG_HEIGHT - 8}>−10%</text>
          <text x={CENTER_X} y={SVG_HEIGHT - 8}>0</text>
          <text x="221.75" y={SVG_HEIGHT - 8}>+10%</text>
        </g>
      </svg>
    </div>
  );
}

function AdminDashboardContent() {
  const profile = useSessionProfile();
  const manufacturers = useTargetManufacturers();
  const [visitsWindow, setVisitsWindow] = useState<VisitWindow>("today");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [designationCode, setDesignationCode] = useState<string | null>(null);
  const [employeeQuery, setEmployeeQuery] = useState("");
  const rows = useMemo(() => manufacturerRows(manufacturers.data?.manufacturers, undefined), [manufacturers.data?.manufacturers]);
  const resolvedId = selectedId ?? rows[0]?.id ?? "all";
  const todayRollup = useAdminDashboardKpis("today");
  const mtdRollup = useAdminDashboardKpis("mtd", {
    manufacturerId: resolvedId,
    designationCode,
    enabled: !manufacturers.isPending,
  });
  const rollup = visitsWindow === "today" ? todayRollup : mtdRollup;

  const selected = rows.find((row) => row.id === resolvedId);
  const businessDate = todayRollup.data?.business_date ?? mtdRollup.data?.business_date ?? "";
  const todayMetrics = todayRollup.data?.org_metrics;
  const visitModel = visitModelFromMetrics(rollup.data?.org_metrics, visitsWindow);
  const orgHeadcount = todayMetrics?.active_employees ?? null;
  const onDuty = todayMetrics?.on_duty;
  const onLeave = todayMetrics?.on_leave;
  const idle = todayMetrics?.no_punch_in;
  const pendingApprovals = todayMetrics?.pending_approvals;
  const employeeProgress = useMemo<ManagerLeagueRow[]>(
    () => mtdRollup.data?.employee_progress ?? [],
    [mtdRollup.data?.employee_progress],
  );
  const designationScope = mtdRollup.data?.designation_scope;
  const designationOptions = (designationScope?.available ?? []).map((code) => ({
    value: code,
    label: designationLabel(code),
  }));
  const activeDesignation = designationCode ?? designationScope?.active ?? "";
  const filteredProgress = useMemo(() => {
    const query = employeeQuery.trim().toLowerCase();
    return query ? employeeProgress.filter((row) => row.name.toLowerCase().includes(query)) : employeeProgress;
  }, [employeeProgress, employeeQuery]);
  const movement: AdminMovementRow[] = mtdRollup.data?.manufacturer_movement ?? [];
  const summary = mtdRollup.data?.targets_summary;

  if (todayRollup.isPending || (todayRollup.isError && !todayRollup.data)) {
    return (
      <KpiQueryFallback
        empty={false}
        isError={todayRollup.isError}
        isPending={todayRollup.isPending}
        onRetry={() => {
          void todayRollup.refetch();
          void mtdRollup.refetch();
        }}
      />
    );
  }

  const onDutyPct = onDuty != null && orgHeadcount ? Math.round((onDuty / orgHeadcount) * 100) : null;
  const healthTargetTitle = !summary
    ? "Target health unavailable"
    : summary.total_amount_lines === 0
      ? "No target set this month"
      : `${summary.on_track} amount lines on track of ${summary.total_amount_lines}`;

  return (
    <div className={styles.dashboardBody}>
      <ScopeRow
        date={formatKpiDate(businessDate)}
        label={orgHeadcount !== null ? `Organization · ${orgHeadcount} people` : (profile.displayName || "Organization")}
      />

      <SectionHeader label="Organization today" />
      <div className={styles.grid3}>
        <MetricTile
          borderColor="var(--success)"
          label="On duty"
          sub={onDutyPct != null ? `${onDutyPct}% of ${orgHeadcount}` : undefined}
          value={onDuty != null ? String(onDuty) : "—"}
        />
        <MetricTile
          borderColor="var(--info)"
          label="On leave"
          sub="leave days today"
          value={onLeave != null ? String(onLeave) : "—"}
        />
        <MetricTile
          borderColor="var(--accent-active)"
          label="No punch-in"
          sub="informational"
          value={idle != null ? String(idle) : "—"}
        />
      </div>

      <div className={styles.card} style={{ gap: 10 }}>
        <div className={styles.cardHeader}>
          <h3>Health and data quality</h3>
        </div>
        <HealthRow
          icon="Warning"
          tone="warn"
          title={idle != null ? `${idle} people without a punch-in` : "Punch-in exceptions unavailable"}
          detail="Number of employees who have not punched in today."
        />
        <HealthRow
          icon="InfoFilled"
          tone="warn"
          title={pendingApprovals != null ? `${pendingApprovals} approvals waiting` : "Approval queue unavailable"}
          detail="Open items waiting for a decision."
        />
        <HealthRow
          icon="Dashboard"
          tone="muted"
          title={healthTargetTitle}
          detail={
            !summary
              ? "Sales targets could not be loaded."
              : summary.total_amount_lines === 0
              ? "Amount-basis manufacturer targets measure this month."
              : "On-track lines are at or above the elapsed-month pace."
          }
        />
      </div>

      <VisitCard
        loading={visitsWindow === "mtd" && mtdRollup.isPending}
        model={visitModel}
        title={visitsWindow === "today" ? "Visits today" : "Visits MTD"}
        window={visitsWindow}
        onWindowChange={setVisitsWindow}
      />

      <SectionHeader label="Growth" />
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3>Manufacturer movement</h3>
          <span className={styles.cardMeta}>
            {businessDate
              ? `${formatMonthShort(businessDate)} vs ${previousMonthLabel(businessDate, "short")}`
              : "vs last month"}
          </span>
        </div>
        {mtdRollup.isPending ? (
          <Skeleton height={160} radius={8} />
        ) : movement.length ? (
          <ManufacturerMovementChart movement={movement} />
        ) : (
          <ChartUnavailable title="Movement unavailable" message="No manufacturer order value this month." />
        )}
      </div>

      <SectionHeader label="Sales performance" />
      <div className={styles.card} style={{ gap: 8 }}>
        <ManufacturerScoper embedded rows={rows} selectedId={resolvedId} onSelect={setSelectedId} />
        <div className={styles.cardDivider} />
        <div className={styles.cardHeader}>
          <h3>By employee</h3>
        </div>
        <div className={styles.employeeFilterRow}>
          {designationOptions.length > 0 && (
            <Select
              label="Level"
              options={designationOptions}
              value={activeDesignation}
              onChange={setDesignationCode}
            />
          )}
          <TextField
            label="Search"
            placeholder="Search by name"
            value={employeeQuery}
            onChange={(event) => setEmployeeQuery((event.target as HTMLInputElement).value)}
            startAdornment={<Icon name="SearchOutlined" size={20} color="var(--ink-4)" />}
          />
        </div>
        {mtdRollup.isPending ? (
          <Skeleton height={280} radius={8} />
        ) : (
          <EmployeeProgressRows
            league={filteredProgress}
            emptyTitle={employeeQuery ? "No match" : "No employees"}
            emptyMessage={
              employeeQuery
                ? `No one named "${employeeQuery}" at this level.`
                : "No one holds this level yet."
            }
          />
        )}
      </div>
    </div>
  );
}

const ATTENTION_HREF: Record<AttentionKind, string> = {
  failed_downstream: "/sp/orders?status=submission_failed",
  stopped_ordering: "/sp/orders",
  untouched: "/sp/beats",
};

const ATTENTION_ICON: Record<AttentionKind, { icon: "CheckCircle" | "Schedule" | "Warning"; tone: "bad" | "soft" | "warn" }> = {
  failed_downstream: { icon: "Warning", tone: "bad" },
  stopped_ordering: { icon: "CheckCircle", tone: "soft" },
  untouched: { icon: "Schedule", tone: "warn" },
};

const REQUEST_PREVIEW_LIMIT = 3;

function requestIcon(subjectType: string) {
  if (subjectType === "dp_order") return "ShoppingCartOutlined";
  if (subjectType === "leave") return "Calendar";
  if (subjectType === "outlet_verification") return "LocationPin";
  return "RewardsOutlined";
}

export function SalespersonRequestsSection() {
  const router = useRouter();
  const requests = useMyRequests();
  const items = flattenApprovals(requests.data).slice(0, REQUEST_PREVIEW_LIMIT);

  return (
    <div className={`${styles.dashboardBody} ${styles.dashboardBodyFlush}`}>
      <SectionHeader
        action={(
          <button
            className={styles.sectionAction}
            type="button"
            onClick={() => router.push("/sp/more/requests")}
          >
            View all
          </button>
        )}
        label="Requests"
      />
      <div className={`${styles.card} ${styles.requestCard}`}>
        {requests.isPending ? (
          <div className={styles.requestBody}>
            <Skeleton height={48} radius={8} />
            <Skeleton height={48} radius={8} />
            <Skeleton height={48} radius={8} />
          </div>
        ) : requests.isError && !items.length ? (
          <p className={styles.requestEmpty}>Requests could not be loaded.</p>
        ) : items.length === 0 ? (
          <p className={styles.requestEmpty}>No requests yet. Beat plans, DP orders and leave you submit will appear here.</p>
        ) : (
          items.map((request) => {
            const chip = requestChip(request.status);
            const href = requestSubjectHref(request);
            const row = (
              <>
                <span className={`${styles.exceptionIcon} ${styles.exceptionIconSoft}`}>
                  <Icon name={requestIcon(request.subject_type)} size={18} color="var(--primary)" />
                </span>
                <span className={styles.exceptionText}>
                  <b>{requestDisplayTitle(request)}</b>
                  <span>{submittedRelativeLabel(request.submitted_at) || request.subtitle}</span>
                </span>
                <span className={styles.requestChip}>
                  <StatusChip status={chip.status} label={chip.label} type="outlined" />
                </span>
              </>
            );
            return href ? (
              <button
                className={styles.exceptionRow}
                key={request.id}
                type="button"
                onClick={() => router.push(href)}
              >
                {row}
              </button>
            ) : (
              <div className={styles.exceptionRow} key={request.id}>
                {row}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export function SalespersonAttentionSection() {
  const router = useRouter();
  const attention = useSpAttention();
  const items: NonNullable<SpAttentionResponse["items"]> = attention.data?.items ?? [];

  if (attention.isPending) {
    return (
      <div className={`${styles.dashboardBody} ${styles.dashboardBodyFlush}`}>
        <Skeleton height={168} radius={12} />
      </div>
    );
  }
  if (attention.isError || !items.length) {
    return null;
  }

  return (
    <div className={`${styles.dashboardBody} ${styles.dashboardBodyFlush}`}>
    <div className={`${styles.card} ${styles.attentionCard}`}>
      <h3 className={styles.attentionTitle}>Worth your attention</h3>
      {items.map((item) => {
        const visual = ATTENTION_ICON[item.kind];
        return (
          <button
            className={styles.exceptionRow}
            key={item.kind}
            type="button"
            onClick={() => router.push(ATTENTION_HREF[item.kind])}
          >
            <span
              className={`${styles.exceptionIcon} ${
                visual.tone === "bad"
                  ? styles.exceptionIconBad
                  : visual.tone === "soft"
                    ? styles.exceptionIconSoft
                    : styles.exceptionIconWarn
              }`}
            >
              <Icon
                name={visual.icon}
                size={18}
                color={visual.tone === "bad" ? "var(--error)" : "var(--accent-active)"}
              />
            </span>
            <span className={styles.exceptionText}>
              <b>{item.title}</b>
              <span>{item.subtitle}</span>
            </span>
            <span className={styles.exceptionCta}>{item.action}</span>
          </button>
        );
      })}
    </div>
    </div>
  );
}

function HealthRow({
  detail,
  icon,
  title,
  tone,
}: {
  detail: string;
  icon: "Dashboard" | "InfoFilled" | "Warning";
  title: string;
  tone: "muted" | "warn";
}) {
  return (
    <div className={styles.exceptionRow}>
      <span className={`${styles.exceptionIcon} ${tone === "warn" ? styles.exceptionIconWarn : styles.exceptionIconMuted}`}>
        <Icon name={icon} size={18} color={tone === "warn" ? "var(--accent-active)" : "var(--ink-3)"} />
      </span>
      <span className={styles.exceptionText}>
        <b>{title}</b>
        <span>{detail}</span>
      </span>
    </div>
  );
}

export function SalespersonTargetsDashboard() {
  const profile = useSessionProfile();
  const manufacturers = useTargetManufacturers();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const targets = useEmployeeTargets(profile.employeeId ? {
    employeeId: profile.employeeId,
    periodMonth: periodMonthFromBusinessDate(istBusinessDate()),
    targetType: "sales",
  } : null);
  const rows = useMemo(
    () => manufacturerRows(manufacturers.data?.manufacturers, targets.data?.targets),
    [manufacturers.data?.manufacturers, targets.data?.targets],
  );
  const resolvedId = selectedId ?? rows.find((row) => row.hasTarget)?.id ?? "all";
  const selected = rows.find((row) => row.id === resolvedId);
  const rosterPending = manufacturers.isPending || targets.isPending;
  const kpis = useSpTargetsKpis({
    manufacturerId: resolvedId,
    enabled: !manufacturers.isPending && !targets.isLoading,
  });
  const businessDate = kpis.data?.business_date ?? "";
  const targetRows: DashboardTargetLine[] = kpis.data?.targets ?? [];
  const targetLine = targetRows.find((line) => line.manufacturer_id === resolvedId) ?? null;

  if (kpis.isPending || (kpis.isError && !kpis.data)) {
    return (
      <KpiQueryFallback
        empty={false}
        isError={kpis.isError}
        isPending={kpis.isPending}
        onRetry={() => { void kpis.refetch(); }}
      />
    );
  }

  return (
    <div className={`${styles.dashboardBody} ${styles.dashboardBodyFlush} ${styles.targetsBody}`}>
      <ScopeRow date={formatKpiDate(businessDate)} label={profile.displayName || "Sales person"} />
      <TargetHero
        daysLeft={workingDaysLeft(businessDate)}
        eyebrow={`${formatMonthLabel(businessDate)} targets`}
        rows={rows}
      />
      <SectionHeader label="Sales performance" />
      {rosterPending && !rows.length ? (
        <>
          <Skeleton height={72} radius={12} />
          <Skeleton height={220} radius={12} />
        </>
      ) : (
        <>
          <div className={styles.scoperSelect}>
            <ManufacturerScoper assignedOnly rows={rows} selectedId={resolvedId} onSelect={setSelectedId} />
          </div>
          <SalesPerformanceCard
            businessDate={businessDate}
            momPct={kpis.data?.mom?.mom_pct ?? null}
            progress={monthDayProgress(businessDate)}
            selected={selected}
            selectedId={resolvedId}
            targetLine={targetLine}
          />
        </>
      )}
      <SectionHeader label="Other targets" />
      {kpis.data.count_targets.map((row) => <CountTargetCard key={row.target_type} row={row} />)}
    </div>
  );
}

function CountTargetCard({ row }: { row: CountTarget }) {
  const router = useRouter();
  const card = COUNT_TARGET_CARDS[row.target_type];
  return (
    <div className={`${styles.card} ${styles.targetProgressCard}`}>
      <div className={styles.cardHeader}>
        <h3>{card.title}</h3>
        <span className={styles.metricTag}>{card.tag}</span>
      </div>
      <div className={styles.bigHead}>
        <span className={`${styles.bigValue} ${styles.num}`}>
          {row.achieved !== null ? toInNumber(row.achieved) : "—"}
        </span>
        <span className={`${styles.bigOf} ${styles.num}`}>
          {row.target_value === null ? "No target set" : `of ${toInNumber(row.target_value)}`}
        </span>
        {row.pct !== null ? (
          <span className={`${styles.bigPct} ${styles.bigPctAccent} ${styles.num}`}>{row.pct}%</span>
        ) : null}
      </div>
      {row.pct !== null ? (
        <div className={styles.paceTrack}>
          <div className={styles.paceBar}>
            <span className={styles.paceFill} style={{ width: `${clampPct(row.pct)}%` }} />
          </div>
        </div>
      ) : null}
      <Button
        variant="outlined"
        color="primary"
        label={card.cta}
        onClick={() => router.push(card.href)}
        style={{ width: "100%" }}
      />
    </div>
  );
}

export function ManagerKpiHomeDashboardScreen() {
  return (
    <ManagementScreen view="dashboard">
      <div className={styles.mgmtBody}>
        <ManagerDashboardContent />
      </div>
    </ManagementScreen>
  );
}

type EmployeeProgressBar = {
  measure: "amount" | "volume" | null;
  taken: number;
  takenLabel: string;
  target: number | null;
  targetLabel: string;
};

function employeeProgressBar(row: ManagerLeagueRow): EmployeeProgressBar {
  const qty = row.taken_qty ?? 0;
  const uom = row.uom_label?.trim() ?? "";
  const showQty = row.target_basis === "volume" && uom === "Ton";
  const showAmount = row.target_basis === "amount";
  const measure: EmployeeProgressBar["measure"] = showQty ? "volume" : (showAmount ? "amount" : null);
  const target = row.target_value != null && row.target_value > 0 ? row.target_value : null;
  const qtyLabel = (value: number) => (uom ? `${toInNumber(value)} ${uom}` : toInNumber(value));
  return {
    measure,
    taken: showQty ? qty : (showAmount ? row.net_value_paise : 0),
    takenLabel: showQty ? qtyLabel(qty) : (showAmount ? moneyFromPaise(row.net_value_paise) : "—"),
    target,
    targetLabel: target == null ? "" : (showQty ? qtyLabel(target) : showAmount ? moneyFromPaise(target) : toInNumber(target)),
  };
}

function EmployeeProgressRows({
  league,
  emptyTitle = "No employees",
  emptyMessage = "No one holds this level yet.",
}: {
  league: ManagerLeagueRow[];
  emptyTitle?: string;
  emptyMessage?: string;
}) {
  if (!league.length) {
    return <ChartUnavailable title={emptyTitle} message={emptyMessage} />;
  }

  const entries = league.map((row) => ({ row, bar: employeeProgressBar(row) }));
  const barsFor = (measure: EmployeeProgressBar["measure"]) =>
    entries.filter(({ bar }) => bar.measure === measure).map(({ bar }) => bar);
  const qtyBars = barsFor("volume");
  const moneyBars = barsFor("amount");
  const qtyScale = progressScale(qtyBars);
  const moneyScale = progressScale(moneyBars);
  const qtyBaseline = progressColorBaseline(qtyBars);
  const moneyBaseline = progressColorBaseline(moneyBars);
  // Rows arrive ordered by hierarchy level then name; label each level once so the
  // ordering is readable when the filter is on "All levels".
  const grouped = new Set(entries.map(({ row }) => row.designation_code)).size > 1;

  return (
    <div className={styles.employeeProgressList}>
      {entries.map(({ row, bar }, index) => {
        const scale = bar.measure === "volume" ? qtyScale : bar.measure === "amount" ? moneyScale : 1;
        const baseline = bar.measure === "volume" ? qtyBaseline : bar.measure === "amount" ? moneyBaseline : 1;
        const code = row.designation_code ?? "";
        const groupLabel = grouped && code && code !== (entries[index - 1]?.row.designation_code ?? "")
          ? designationLabel(code)
          : null;
        const colorPct = progressColorPct(bar, row.pct ?? null, baseline);
        const fillColor = leagueBarFill(colorPct);
        return (
          <Fragment key={row.employee_id}>
            {groupLabel ? <p className={styles.employeeProgressGroup}>{groupLabel}</p> : null}
            <div className={styles.employeeProgressRow}>
              <span className={styles.employeeProgressAvatar}>{initialsFromName(row.name)}</span>
              <div className={styles.employeeProgressMain}>
                <div className={styles.employeeProgressTop}>
                  <span className={styles.employeeProgressName}>{shortDisplayName(row.name)}</span>
                  <span className={`${styles.employeeProgressValue} ${styles.num}`}>{bar.takenLabel}</span>
                </div>
                <div className={styles.employeeProgressBarRow}>
                  <span className={styles.employeeProgressTrack}>
                    <span
                      className={styles.employeeProgressFill}
                      style={{ background: fillColor, width: `${bar.measure ? Math.min(100, (bar.taken / scale) * 100) : 0}%` }}
                    />
                    {bar.target != null ? (
                      <span
                        className={styles.employeeProgressTarget}
                        style={{ left: `${Math.min(100, (bar.target / scale) * 100)}%` }}
                        title={`Target ${bar.targetLabel}`}
                      />
                    ) : null}
                  </span>
                  <span
                    className={`${styles.employeeProgressPct} ${styles.num} ${row.pct == null ? styles.employeeProgressPctMuted : ""}`}
                  >
                    {row.pct == null ? "—" : `${row.pct}%`}
                  </span>
                </div>
              </div>
            </div>
          </Fragment>
        );
      })}
      {entries.some(({ bar }) => bar.target != null) ? (
        <p className={styles.employeeProgressLegend}>
          <span className={styles.employeeProgressLegendTick} aria-hidden="true" />
          Tick marks the month target
        </p>
      ) : null}
    </div>
  );
}

function ManagerTeamPerformanceContent() {
  const manufacturers = useTargetManufacturers();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [designationCode, setDesignationCode] = useState<string | null>(null);
  const [employeeQuery, setEmployeeQuery] = useState("");
  const rows = useMemo(() => manufacturerRows(manufacturers.data?.manufacturers, undefined), [manufacturers.data?.manufacturers]);
  const resolvedId = selectedId ?? rows[0]?.id ?? "all";
  const kpis = useManagerDashboardKpis("mtd", {
    manufacturerId: resolvedId,
    designationCode,
    enabled: !manufacturers.isPending,
  });
  const businessDate = kpis.data?.business_date ?? "";
  const league = useMemo<ManagerLeagueRow[]>(() => kpis.data?.league ?? [], [kpis.data?.league]);
  const designationScope = kpis.data?.designation_scope;
  const designationOptions = (designationScope?.available ?? []).map((code) => ({
    value: code,
    label: designationLabel(code),
  }));
  const activeDesignation = designationCode ?? designationScope?.active ?? "";
  const filteredProgress = useMemo(() => {
    const query = employeeQuery.trim().toLowerCase();
    return query ? league.filter((row) => row.name.toLowerCase().includes(query)) : league;
  }, [league, employeeQuery]);

  if (kpis.isPending || (kpis.isError && !kpis.data)) {
    return (
      <KpiQueryFallback
        empty={false}
        isError={kpis.isError}
        isPending={kpis.isPending}
        onRetry={() => { void kpis.refetch(); }}
      />
    );
  }

  return (
    <div className={styles.dashboardBody}>
      <ScopeRow date={formatKpiDate(businessDate)} label="Your tree" />
      <SectionHeader label="Sales performance" />
      <div className={styles.card} style={{ gap: 8 }}>
        <ManufacturerScoper embedded rows={rows} selectedId={resolvedId} onSelect={setSelectedId} />
        <div className={styles.cardDivider} />
        <div className={styles.cardHeader}>
          <h3>By employee</h3>
        </div>
        <div className={styles.employeeFilterRow}>
          {designationOptions.length > 0 && (
            <Select
              label="Level"
              options={designationOptions}
              value={activeDesignation}
              onChange={setDesignationCode}
            />
          )}
          <TextField
            label="Search"
            placeholder="Search by name"
            value={employeeQuery}
            onChange={(event) => setEmployeeQuery((event.target as HTMLInputElement).value)}
            startAdornment={<Icon name="SearchOutlined" size={20} color="var(--ink-4)" />}
          />
        </div>
        {kpis.isPlaceholderData ? (
          <Skeleton height={280} radius={8} />
        ) : (
          <EmployeeProgressRows
            league={filteredProgress}
            emptyTitle={employeeQuery ? "No match" : "No employees"}
            emptyMessage={
              employeeQuery
                ? `No one named "${employeeQuery}" at this level.`
                : "No one holds this level yet."
            }
          />
        )}
      </div>
    </div>
  );
}

export function ManagerTeamPerformanceScreen() {
  return (
    <ManagementScreen view="team-performance">
      <div className={styles.mgmtBody}>
        <ManagerTeamPerformanceContent />
      </div>
    </ManagementScreen>
  );
}

export function AdminKpiHomeDashboardScreen() {
  return (
    <ManagementScreen view="dashboard">
      <div className={styles.mgmtBody}>
        <AdminDashboardContent />
      </div>
    </ManagementScreen>
  );
}
