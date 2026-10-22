"use client";

import type { OutletInsightManufacturersResponse } from "@humbee/api-contract";
import { BottomSheet, EmptyState, ErrorState, Icon } from "humbee-design-system";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { SpScreen } from "@/src/features/shell/components";
import { SpListSkeleton } from "@/src/features/shell/loading";
import { ApiClientError } from "@/src/shared/api";
import { hardwareBackEventName } from "@/src/shared/capabilities/hardware-back";
import {
  useOutletInsightManufacturers,
  useOutletInsightProfiler,
  useOutletInsightSection,
  type OutletInsightSectionName,
} from "./service";
import styles from "./insights.module.css";

type InsightTab = "performance" | "benefits" | "rewards" | "profiler";
type PolicyTone = "ok" | "bad" | "warn";
type RuleKind = "sales" | "allocation" | "onward" | "plain";

type InsightGodown = {
  esiId: string;
  sap: string;
  role: string;
  active: boolean;
};

type InsightManufacturer = {
  id: string;
  name: string;
  godowns: InsightGodown[];
};

type LabeledValue = {
  label: string;
  value: string;
};

type MonthCardModel = {
  month: string;
  columns: LabeledValue[];
};

type MonthGroup = {
  title: string;
  compactLabel: boolean;
  cards: MonthCardModel[];
};

type PerformanceView = {
  period: string | null;
  sales: LabeledValue[];
  inventory: LabeledValue[];
  network: Array<{ title: string; columns: LabeledValue[] }>;
  months: MonthGroup[];
};

type PeriodItem = {
  label: string;
  value: string;
};

type RuleRow = {
  label: string;
  value: string;
  kind: RuleKind;
};

type ClubView = {
  imageUrl: string | null;
  title: string | null;
  caption: string | null;
  periods: PeriodItem[];
  rules: RuleRow[];
};

type PolicyView = {
  key: string;
  name: string | null;
  tagline: string | null;
  status: string | null;
  tone: PolicyTone | null;
  amount: string | null;
  message: string | null;
  imageUrl: string | null;
};

type SocialView = {
  label: string;
  club: ClubView | null;
  policiesLabel: string | null;
  policies: PolicyView[];
};

type RewardStat = {
  label: string;
  value: string;
  imageUrl: string | null;
};

type RewardCardModel = {
  label: string;
  count: string | null;
  stats: RewardStat[];
};

const insightSheetStyle: CSSProperties = {
  marginInline: "auto",
  maxWidth: 480,
  width: "100%",
};

const TABS: Array<{ id: InsightTab; label: string; icon: string }> = [
  { id: "performance", label: "Performance", icon: "Dashboard" },
  { id: "benefits", label: "Benefits", icon: "InventoryOutlined" },
  { id: "rewards", label: "Rewards", icon: "RewardsOutlined" },
  { id: "profiler", label: "Profiler", icon: "ProfileOutlined" },
];

const INVENTORY_LABELS = ["available", "unverified"];
const UNAFFECTED = "Your visit and order flow are unaffected.";
const SECTION_EMPTY = "Humbee did not return displayable fields for this section.";
const istStamp = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Kolkata",
});

function formatInsightAsOf(value: string): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return istStamp.format(date);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function displayText(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return null;
}

function httpsUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "https:") return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

function normLabel(value: string): string {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}

function readLabeledRows(value: unknown): LabeledValue[] {
  if (!Array.isArray(value)) return [];
  const rows: LabeledValue[] = [];
  for (const item of value) {
    const record = asRecord(item);
    if (!record) continue;
    const label = displayText(record.label);
    const rowValue = displayText(record.value);
    if (!label || !rowValue) continue;
    rows.push({ label, value: rowValue });
  }
  return rows;
}

function pickLabels(rows: LabeledValue[], names: string[]): LabeledValue[] {
  const picked: LabeledValue[] = [];
  for (const name of names) {
    const match = rows.find((row) => normLabel(row.label) === name);
    if (match) picked.push(match);
  }
  return picked;
}

function readMonthCards(value: unknown): MonthCardModel[] {
  if (!Array.isArray(value)) return [];
  const cards: MonthCardModel[] = [];
  for (const item of value) {
    const record = asRecord(item);
    if (!record) continue;
    const month = displayText(record.month);
    const columns = readLabeledRows(record.info);
    if (!month || !columns.length) continue;
    cards.push({ month, columns });
  }
  return cards;
}

function readMonthGroup(node: unknown, fallback: string, compactLabel: boolean): MonthGroup | null {
  const record = asRecord(node);
  if (!record) return null;
  const cards = readMonthCards(record.data);
  if (!cards.length) return null;
  return {
    title: displayText(record.label) ?? fallback,
    compactLabel,
    cards,
  };
}

function readPerformance(data: unknown): PerformanceView {
  const root = asRecord(data);
  const salesNode = asRecord(root?.total_sales);
  const period = displayText(asRecord(salesNode?.period)?.value);
  const info = readLabeledRows(salesNode?.info);
  const network: PerformanceView["network"] = [];
  if (Array.isArray(root?.network_stats)) {
    for (const item of root.network_stats) {
      const record = asRecord(item);
      if (!record) continue;
      const title = displayText(record.label);
      const columns = readLabeledRows(record.info);
      if (!title || !columns.length) continue;
      network.push({ title, columns });
    }
  }
  const months = [
    readMonthGroup(root?.month_wise_sales, "Total month-wise sales", false),
    readMonthGroup(root?.month_wise_inventory_allocation, "Total month-wise inventory allocation", true),
  ].filter((group): group is MonthGroup => group !== null);
  return {
    period,
    sales: info.filter((row) => !INVENTORY_LABELS.includes(normLabel(row.label))),
    inventory: pickLabels(info, INVENTORY_LABELS),
    network,
    months,
  };
}

function performanceHasContent(view: PerformanceView): boolean {
  return view.sales.length > 0 || view.inventory.length > 0 || view.network.length > 0 || view.months.length > 0;
}

function ruleKind(label: string): RuleKind {
  const normalized = normLabel(label).replaceAll("%", " percent ");
  if (normalized.includes("onward") && normalized.includes("alloc")) return "onward";
  if (normalized.includes("sales") && normalized.includes("need")) return "sales";
  if (normalized.includes("alloc") && normalized.includes("percent")) return "allocation";
  return "plain";
}

function readRules(value: unknown): RuleRow[] {
  if (!Array.isArray(value)) return [];
  const rows: RuleRow[] = [];
  for (const item of value) {
    const record = asRecord(item);
    if (!record) continue;
    const label = displayText(record.label);
    const ruleValue = displayText(record.value);
    if (!label || !ruleValue) continue;
    rows.push({ label, value: ruleValue, kind: ruleKind(label) });
  }
  return rows;
}

function readPeriods(value: unknown): PeriodItem[] {
  if (!Array.isArray(value)) return [];
  const items: PeriodItem[] = [];
  for (const item of value) {
    const record = asRecord(item);
    if (!record) continue;
    const label = displayText(record.label);
    const periodValue = displayText(record.value);
    if (!label || !periodValue) continue;
    items.push({ label, value: periodValue });
  }
  return items;
}

function readClub(value: unknown): ClubView | null {
  const record = asRecord(value);
  if (!record) return null;
  const club: ClubView = {
    imageUrl: httpsUrl(record.img_url),
    title: displayText(record.label),
    caption: displayText(record.level),
    periods: readPeriods(record.period),
    rules: readRules(record.info),
  };
  if (!club.imageUrl && !club.title && !club.periods.length && !club.rules.length) return null;
  return club;
}

function policyTone(status: string): PolicyTone {
  const normalized = status.trim().toLowerCase();
  if (normalized === "active") return "ok";
  if (normalized === "locked") return "bad";
  return "warn";
}

function policyFigure(value: unknown): string | null {
  const text = displayText(value);
  if (!text) return null;
  const stripped = text.replace(/^Amount:\s*/i, "").trim();
  if (!stripped || stripped === "-" || stripped === "—" || stripped === "–") return null;
  return stripped;
}

function readPolicies(value: unknown): PolicyView[] {
  if (!Array.isArray(value)) return [];
  const policies: PolicyView[] = [];
  for (const [index, item] of value.entries()) {
    const record = asRecord(item);
    if (!record) continue;
    const name = displayText(record.label);
    const tagline = displayText(record.tagline);
    const status = displayText(record.status);
    const amount = policyFigure(record.amount);
    const message = displayText(record.message);
    const imageUrl = httpsUrl(record.img_url);
    if (!name && !tagline && !status && !amount && !message && !imageUrl) continue;
    policies.push({
      key: `${name ?? "policy"}:${index}`,
      name,
      tagline,
      status,
      tone: status ? policyTone(status) : null,
      amount,
      message,
      imageUrl,
    });
  }
  return policies;
}

function readSocial(node: unknown): SocialView | null {
  const record = asRecord(node);
  if (!record) return null;
  const info = asRecord(record.info);
  const club = readClub(info?.club_card);
  const policiesNode = asRecord(info?.current_policies);
  const policies = readPolicies(policiesNode?.policies);
  if (!club && !policies.length) return null;
  return {
    label: displayText(record.label) ?? "Social Security Benefits",
    club,
    policiesLabel: policies.length ? displayText(policiesNode?.label) : null,
    policies,
  };
}

function rewardHead(record: Record<string, unknown>): { label: string; count: string | null } | null {
  const raw = displayText(record.label);
  if (!raw) return null;
  const [, label, count] = /^(.*\S)\s*:\s*(\S.*)$/.exec(raw) ?? [];
  return label && count ? { label, count } : { label: raw, count: null };
}

function readRewardStats(value: unknown): RewardStat[] {
  if (!Array.isArray(value)) return [];
  const stats: RewardStat[] = [];
  for (const item of value) {
    const record = asRecord(item);
    if (!record) continue;
    const label = displayText(record.label);
    const statValue = displayText(record.value);
    if (!label || !statValue) continue;
    stats.push({
      label,
      value: statValue,
      imageUrl: httpsUrl(record.img),
    });
  }
  return stats;
}

function readRewards(data: unknown): RewardCardModel[] {
  const root = asRecord(data);
  if (!Array.isArray(root?.summary)) return [];
  const cards: RewardCardModel[] = [];
  for (const item of root.summary) {
    const record = asRecord(item);
    if (!record) continue;
    const head = rewardHead(record);
    if (!head) continue;
    cards.push({ label: head.label, count: head.count, stats: readRewardStats(record.stats) });
  }
  return cards;
}

function formatSapCode(sap: string): string {
  if (!sap) return "";
  return /^sap\b/i.test(sap) ? sap : `SAP ${sap}`;
}

function godownTitle(godown: InsightGodown): string {
  return godown.sap || godown.role;
}

function parseEsiCode(esiCode: string): { sap: string; role: string } {
  const raw = esiCode.trim();
  const splitAt = raw.indexOf(" - ");
  if (splitAt >= 0) {
    return { sap: raw.slice(0, splitAt).trim(), role: raw.slice(splitAt + 3).trim() };
  }
  return { sap: "", role: raw };
}

function manufacturersFromInsight(
  response: OutletInsightManufacturersResponse | undefined,
): InsightManufacturer[] {
  return (response?.manufacturers ?? []).map((manufacturer) => ({
    id: manufacturer.manufacturer_id,
    name: manufacturer.manufacturer_name,
    godowns: manufacturer.external_system_records.flatMap((esi) => {
      const esiId = esi.esi_id.trim();
      if (!esiId) return [];
      const parsed = parseEsiCode(esi.esi_code);
      return [{
        esiId,
        sap: formatSapCode(parsed.sap),
        role: parsed.role,
        active: esi.active,
      }];
    }),
  }));
}

function registrationCountLabel(count: number): string {
  return count === 1 ? "1 registration" : `${count} registrations`;
}

function insightErrorCopy(error: unknown): { title: string; message: string } {
  if (error instanceof ApiClientError && error.code === "insights_esi_unresolved") {
    return {
      title: "No registration",
      message: `This outlet has no registration with the selected manufacturer. ${UNAFFECTED}`,
    };
  }
  return {
    title: "Insights unavailable",
    message: `The outlet insight service didn't respond. ${UNAFFECTED}`,
  };
}

function HttpsImage({ src, className }: { src: string; className?: string }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  if (failedSrc === src) return null;
  return <img alt="" className={className} src={src} onError={() => setFailedSrc(src)} />;
}

function Freshness({ asOf }: { asOf?: string | null }) {
  if (!asOf) return null;
  const formatted = formatInsightAsOf(asOf);
  if (!formatted) return null;
  return (
    <div className={styles.notes}>
      <p>{`As of ${formatted}.`}</p>
    </div>
  );
}

function Columns({
  columns,
  center = false,
  small = false,
  compactLabel = false,
}: {
  columns: LabeledValue[];
  center?: boolean;
  small?: boolean;
  compactLabel?: boolean;
}) {
  return (
    <div className={styles.cols}>
      {columns.map((column, index) => (
        <Fragment key={`${column.label}:${index}`}>
          {index > 0 ? <div className={styles.vdiv} /> : null}
          <div className={center ? `${styles.col} ${styles.colCenter}` : styles.col}>
            <div className={compactLabel ? `${styles.colLabel} ${styles.colLabelXs}` : styles.colLabel}>{column.label}</div>
            <div className={small ? `${styles.colValue} ${styles.colValueSm}` : styles.colValue}>{column.value}</div>
          </div>
        </Fragment>
      ))}
    </div>
  );
}

function KpiCard({ title, period, columns }: { title: string; period: string | null; columns: LabeledValue[] }) {
  if (!columns.length) return null;
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <div className={styles.cardTitle}>{title}</div>
        {period ? <div className={styles.period}><b>Period:</b><span>{period}</span></div> : null}
      </div>
      <Columns columns={columns} center />
    </section>
  );
}

function MonthSection({ group }: { group: MonthGroup }) {
  return (
    <div className={styles.group}>
      <div className={styles.sectionTitle}>{group.title}</div>
      {group.cards.map((card, index) => (
        <section className={styles.card} key={`${card.month}:${index}`}>
          <div className={styles.cardTitle}>{card.month}</div>
          <Columns columns={card.columns} small compactLabel={group.compactLabel} />
        </section>
      ))}
    </div>
  );
}

function PerformanceSection({ data, asOf }: { data: unknown; asOf?: string | null }) {
  const view = useMemo(() => readPerformance(data), [data]);
  if (!performanceHasContent(view)) {
    return (
      <>
        <EmptyState icon="Dashboard" title="No performance data" message={SECTION_EMPTY} />
        <Freshness asOf={asOf} />
      </>
    );
  }
  return (
    <>
      <KpiCard title="Total Sales" period={view.period} columns={view.sales} />
      <KpiCard title="Inventory" period={view.period} columns={view.inventory} />
      {view.network.map((card, index) => (
        <KpiCard key={`${card.title}:${index}`} title={card.title} period={null} columns={card.columns} />
      ))}
      {view.months.map((group, index) => <MonthSection key={`${group.title}:${index}`} group={group} />)}
      <Freshness asOf={asOf} />
    </>
  );
}

function RuleList({ rules }: { rules: RuleRow[] }) {
  return rules.map((rule, index) => {
    if (rule.kind === "allocation") {
      return (
        <div className={styles.adv} key={`${rule.label}:${index}`}>
          <p>{rule.label}</p>
          <p className={styles.advValue}>{rule.value}</p>
        </div>
      );
    }
    const onward = rule.kind === "onward";
    return (
      <div className={styles.ruleRow} key={`${rule.label}:${index}`}>
        <div className={styles.ruleLead}>
          {rule.kind === "sales" || onward ? (
            <Icon name="InfoFilled" size={onward ? 16 : 24} color="var(--color-text-secondary)" />
          ) : null}
          {onward ? <b className={styles.onwardLabel}>{rule.label}</b> : <span>{rule.label}</span>}
        </div>
        <span className={styles.ruleValue}>{rule.value}</span>
      </div>
    );
  });
}

function ClubCard({ club }: { club: ClubView }) {
  return (
    <section className={styles.card}>
      {club.imageUrl || club.title ? (
        <div className={styles.clubTop}>
          {club.imageUrl ? <HttpsImage className={styles.clubMedal} src={club.imageUrl} /> : null}
          {club.title ? (
            <div className={styles.clubLevel}>
              <b>{club.title}</b>
              {club.caption ? <span>{club.caption}</span> : null}
            </div>
          ) : null}
        </div>
      ) : null}
      {club.periods.length ? (
        <div className={styles.clubDates}>
          {club.periods.map((item, index) => (
            <div key={`${item.label}:${index}`}>
              <b>{item.label}</b>
              <span>{item.value}</span>
            </div>
          ))}
        </div>
      ) : null}
      <RuleList rules={club.rules} />
    </section>
  );
}

function PolicyCard({ policy }: { policy: PolicyView }) {
  const badgeClass = policy.tone === "ok"
    ? styles.badgeOk
    : policy.tone === "bad"
      ? styles.badgeBad
      : styles.badgeWarn;
  return (
    <section className={styles.policy}>
      {policy.imageUrl || policy.name || policy.tagline || policy.status ? (
        <div className={styles.policyTop}>
          {policy.imageUrl ? <HttpsImage className={styles.policyIcon} src={policy.imageUrl} /> : null}
          {policy.name || policy.tagline ? (
            <div className={styles.policyName}>
              {policy.name ? <b>{policy.name}</b> : null}
              {policy.tagline ? <span>{policy.tagline}</span> : null}
            </div>
          ) : <span className={styles.policyName} />}
          {policy.status ? <div className={`${styles.badge} ${badgeClass}`}>{policy.status}</div> : null}
        </div>
      ) : null}
      {policy.amount ? (
        <div className={styles.policyFoot}>
          <div className={styles.amt}>
            Amount
            <b>{policy.amount}</b>
          </div>
        </div>
      ) : null}
      {policy.message ? <p className={styles.policyReason}>{policy.message}</p> : null}
    </section>
  );
}

function BenefitsSection({ data, asOf }: { data: unknown; asOf?: string | null }) {
  const social = useMemo(() => readSocial(asRecord(data)?.social_security_benefits), [data]);
  if (!social) {
    return (
      <>
        <EmptyState icon="InventoryOutlined" title="No benefits data" message={SECTION_EMPTY} />
        <Freshness asOf={asOf} />
      </>
    );
  }
  return (
    <>
      {social.club ? <ClubCard club={social.club} /> : null}
      {social.policiesLabel ? (
        <div className={styles.policiesHead}><b>{social.policiesLabel}</b></div>
      ) : null}
      {social.policies.map((policy) => <PolicyCard key={policy.key} policy={policy} />)}
      <Freshness asOf={asOf} />
    </>
  );
}

function RewardsSection({ data, asOf }: { data: unknown; asOf?: string | null }) {
  const cards = useMemo(() => readRewards(data), [data]);
  if (!cards.length) {
    return (
      <>
        <EmptyState icon="RewardsOutlined" title="No rewards data" message={SECTION_EMPTY} />
        <Freshness asOf={asOf} />
      </>
    );
  }
  return (
    <>
      {cards.map((card, index) => (
        <section className={`${styles.card} ${styles.cardTight}`} key={`${card.label}:${index}`}>
          {card.label || card.count ? (
            <div className={styles.rewardHead}>
              {card.label ? <b>{card.label}</b> : null}
              {card.count ? <span>{card.count}</span> : null}
            </div>
          ) : null}
          {card.stats.length ? (
            <div className={styles.cols}>
              {card.stats.map((stat, statIndex) => (
                <Fragment key={`${stat.label}:${statIndex}`}>
                  {statIndex > 0 ? <div className={styles.vdiv} /> : null}
                  <div className={styles.rewardCol}>
                    {stat.imageUrl ? <HttpsImage className={styles.rewardImage} src={stat.imageUrl} /> : null}
                    <div className={styles.colLabel}>{stat.label}</div>
                    <div className={styles.colValue}>{stat.value}</div>
                  </div>
                </Fragment>
              ))}
            </div>
          ) : null}
        </section>
      ))}
      <Freshness asOf={asOf} />
    </>
  );
}

function ProfilerBrowser({
  onClose,
  children,
}: {
  onClose: () => void;
  children: ReactNode;
}) {
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className={styles.profilerOverlay} role="dialog" aria-modal="true" aria-label="Outlet profiler">
      {children}
      <button
        ref={closeButtonRef}
        type="button"
        className={styles.browserClose}
        aria-label="Close outlet profiler"
        onClick={onClose}
      >
        <Icon name="Close" size={22} color="currentColor" />
      </button>
    </div>,
    document.body,
  );
}

function SectionFrame({
  isPending,
  isError,
  error,
  onRetry,
  children,
}: {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  children: ReactNode;
}) {
  if (isPending) return <SpListSkeleton rows={4} />;
  if (isError) {
    const copy = insightErrorCopy(error);
    return <ErrorState title={copy.title} message={copy.message} onRetry={onRetry} />;
  }
  return children;
}

function InsightSectionPane({
  outletId,
  manufacturerId,
  outletEsiId,
  active,
  section,
}: {
  outletId: string;
  manufacturerId: string;
  outletEsiId: string;
  active: boolean;
  section: OutletInsightSectionName;
}) {
  const awaitingSap = !outletEsiId;
  const query = useOutletInsightSection(outletId, manufacturerId, outletEsiId, section, active);

  if (awaitingSap) {
    return (
      <EmptyState
        icon="InventoryOutlined"
        title="Select a role"
        message="Choose a role to load this section."
      />
    );
  }

  return (
    <SectionFrame
      isPending={query.isPending}
      isError={query.isError}
      error={query.error}
      onRetry={() => { void query.refetch(); }}
    >
      {section === "performance" ? (
        <PerformanceSection data={query.data?.data} asOf={query.data?.as_of} />
      ) : null}
      {section === "benefits" ? (
        <BenefitsSection data={query.data?.data} asOf={query.data?.as_of} />
      ) : null}
      {section === "rewards" ? (
        <RewardsSection data={query.data?.data} asOf={query.data?.as_of} />
      ) : null}
    </SectionFrame>
  );
}

function ProfilerPane({
  outletId,
  manufacturerId,
  outletEsiId,
  onClose,
}: {
  outletId: string;
  manufacturerId: string;
  outletEsiId: string;
  onClose: () => void;
}) {
  const query = useOutletInsightProfiler(outletId, manufacturerId, outletEsiId, true);
  const frameUrl = httpsUrl(query.data?.url);

  let page: ReactNode;
  if (query.isPending) {
    page = (
      <div className={styles.browserFallback}>
        <SpListSkeleton rows={3} />
      </div>
    );
  } else if (query.isError || !frameUrl) {
    const copy = insightErrorCopy(query.error);
    page = (
      <div className={styles.browserFallback}>
        <ErrorState title={copy.title} message={copy.message} onRetry={() => { void query.refetch(); }} />
      </div>
    );
  } else {
    page = (
      <iframe
        className={styles.profilerFrame}
        title="Outlet profiler"
        src={frameUrl}
        sandbox="allow-scripts allow-same-origin allow-forms"
        referrerPolicy="no-referrer"
      />
    );
  }

  return <ProfilerBrowser onClose={onClose}>{page}</ProfilerBrowser>;
}

function InsightTabStrip({
  tab,
  profilerVisible,
  profilerDisabled,
  profilerTabRef,
  onSelect,
}: {
  tab: InsightTab;
  profilerVisible: boolean;
  profilerDisabled: boolean;
  profilerTabRef: { current: HTMLButtonElement | null };
  onSelect: (id: InsightTab) => void;
}) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const [edges, setEdges] = useState({ left: false, right: false });

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const sync = () => {
      const left = el.scrollLeft > 1;
      const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
      setEdges((current) => (current.left === left && current.right === right ? current : { left, right }));
    };
    sync();
    el.addEventListener("scroll", sync, { passive: true });
    const observer = new ResizeObserver(sync);
    observer.observe(el);
    return () => {
      el.removeEventListener("scroll", sync);
      observer.disconnect();
    };
  }, []);

  const nudge = (direction: -1 | 1) => {
    scrollerRef.current?.scrollBy({ left: direction * 140, behavior: "smooth" });
  };

  return (
    <nav className={styles.tabstrip} aria-label="Outlet insights">
      <button
        type="button"
        className={styles.tabArrow}
        aria-label="Show previous tabs"
        disabled={!edges.left}
        onClick={() => nudge(-1)}
      >
        <Icon name="KeyboardArrowLeft" size={24} color="currentColor" />
      </button>
      <div className={styles.tabScroll} ref={scrollerRef}>
        {TABS.map((item) => {
          const isProfiler = item.id === "profiler";
          const selected = isProfiler ? profilerVisible : (!profilerVisible && tab === item.id);
          return (
            <button
              key={item.id}
              ref={isProfiler ? profilerTabRef : undefined}
              type="button"
              className={styles.tab}
              data-active={selected}
              aria-current={selected ? "page" : undefined}
              disabled={isProfiler && profilerDisabled}
              onClick={() => onSelect(item.id)}
            >
              <Icon name={item.icon} size={24} color="currentColor" />
              {item.label}
            </button>
          );
        })}
      </div>
      <button
        type="button"
        className={styles.tabArrow}
        aria-label="Show next tabs"
        disabled={!edges.right}
        onClick={() => nudge(1)}
      >
        <Icon name="KeyboardArrowRight" size={24} color="currentColor" />
      </button>
    </nav>
  );
}

export function OutletInsightsScreen({
  outletId,
  outletName,
}: {
  outletId: string;
  outletName: string;
}) {
  const manufacturersQuery = useOutletInsightManufacturers(outletId);
  const manufacturers = useMemo(
    () => manufacturersFromInsight(manufacturersQuery.data),
    [manufacturersQuery.data],
  );
  const [manufacturerId, setManufacturerId] = useState("");
  const [sapId, setSapId] = useState("");
  const [tab, setTab] = useState<InsightTab>("performance");
  const [profilerOpen, setProfilerOpen] = useState(false);
  const [sheet, setSheet] = useState<"manufacturer" | "sap" | null>(null);
  const profilerTabRef = useRef<HTMLButtonElement | null>(null);

  const selectedId = manufacturers.some((item) => item.id === manufacturerId)
    ? manufacturerId
    : (manufacturers[0]?.id ?? "");
  const manufacturer = manufacturers.find((item) => item.id === selectedId);
  const activeGodown = manufacturer?.godowns.find((item) => item.active);
  const fallbackGodown = activeGodown ?? manufacturer?.godowns[0];
  const selectedSapId = manufacturer?.godowns.some((item) => item.esiId === sapId)
    ? sapId
    : (fallbackGodown?.esiId ?? "");
  const godown = manufacturer?.godowns.find((item) => item.esiId === selectedSapId);
  const noEsi = Boolean(manufacturer && manufacturer.godowns.length === 0);
  const picksDisabled = manufacturersQuery.isPending || manufacturersQuery.isError || !manufacturers.length;
  const profilerDisabled = picksDisabled;
  const profilerVisible = profilerOpen && !profilerDisabled;
  const sapLabel = godown
    ? `${godownTitle(godown)}${godown.active ? "" : " · Inactive"}`
    : noEsi
      ? "No roles"
      : "Select role";

  const closeProfiler = useCallback(() => {
    setProfilerOpen(false);
    profilerTabRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!sheet && !profilerVisible) return;
    const onHardwareBack = (event: Event) => {
      event.preventDefault();
      if (profilerVisible) {
        closeProfiler();
        return;
      }
      setSheet(null);
    };
    window.addEventListener(hardwareBackEventName, onHardwareBack);
    return () => window.removeEventListener(hardwareBackEventName, onHardwareBack);
  }, [closeProfiler, profilerVisible, sheet]);

  return (
    <SpScreen
      title={outletName || "Outlet insights"}
      back
      appBarVariant="insights"
      toolbar={(
        <div className={styles.toolbar}>
          <div className={styles.scope}>
            <div className={styles.scopeRow}>
              <button
                type="button"
                className={styles.select}
                disabled={picksDisabled}
                aria-haspopup="dialog"
                aria-expanded={sheet === "manufacturer"}
                onClick={() => setSheet("manufacturer")}
              >
                <span className={`${styles.selectLabel}${manufacturer ? "" : ` ${styles.selectPlaceholder}`}`}>
                  {manufacturer?.name || "Manufacturer"}
                </span>
                <Icon name="KeyboardArrowDown" size={22} color="var(--color-text-secondary)" />
              </button>
              {godown?.role ? <span className={styles.roleChip} title={godown.role}>{godown.role}</span> : null}
            </div>
            <div className={styles.scopeRow}>
              <button
                type="button"
                className={styles.select}
                disabled={picksDisabled}
                aria-haspopup="dialog"
                aria-expanded={sheet === "sap"}
                onClick={() => setSheet("sap")}
              >
                <span className={`${styles.selectLabel}${godown ? "" : ` ${styles.selectPlaceholder}`}`}>
                  {sapLabel}
                </span>
                <Icon name="KeyboardArrowDown" size={22} color="var(--color-text-secondary)" />
              </button>
            </div>
          </div>
          <InsightTabStrip
            tab={tab}
            profilerVisible={profilerVisible}
            profilerDisabled={profilerDisabled}
            profilerTabRef={profilerTabRef}
            onSelect={(id) => {
              if (id === "profiler") {
                setProfilerOpen(true);
                return;
              }
              setProfilerOpen(false);
              setTab(id);
            }}
          />
        </div>
      )}
    >
      <div className={styles.body}>
        {manufacturersQuery.isPending ? (
          <SpListSkeleton rows={4} />
        ) : manufacturersQuery.isError ? (
          <ErrorState
            title="Manufacturers unavailable"
            message="Manufacturer options could not be loaded for this outlet."
            onRetry={() => { void manufacturersQuery.refetch(); }}
          />
        ) : !manufacturers.length ? (
          <EmptyState
            icon="InventoryOutlined"
            title="No manufacturers"
            message="This outlet has no manufacturers linked yet."
          />
        ) : noEsi ? (
          <ErrorState
            title="No registration"
            message={UNAFFECTED}
          />
        ) : (
          <>
            <div className={styles.pane} hidden={tab !== "performance"}>
              <InsightSectionPane
                outletId={outletId}
                manufacturerId={selectedId}
                outletEsiId={selectedSapId}
                section="performance"
                active={tab === "performance"}
              />
            </div>
            <div className={styles.pane} hidden={tab !== "benefits"}>
              <InsightSectionPane
                outletId={outletId}
                manufacturerId={selectedId}
                outletEsiId={selectedSapId}
                section="benefits"
                active={tab === "benefits"}
              />
            </div>
            <div className={styles.pane} hidden={tab !== "rewards"}>
              <InsightSectionPane
                outletId={outletId}
                manufacturerId={selectedId}
                outletEsiId={selectedSapId}
                section="rewards"
                active={tab === "rewards"}
              />
            </div>
          </>
        )}
      </div>

      {profilerVisible ? (
        <ProfilerPane
          key={`${selectedId}:${selectedSapId}`}
          outletId={outletId}
          manufacturerId={selectedId}
          outletEsiId={selectedSapId}
          onClose={closeProfiler}
        />
      ) : null}

      <BottomSheet
        open={sheet === "manufacturer"}
        title="Manufacturer"
        onClose={() => setSheet(null)}
        style={insightSheetStyle}
      >
        <p className={styles.sheetNote}>
          Changing manufacturer resets the role. Insights are scoped to one manufacturer and one role.
        </p>
        {manufacturers.map((item) => (
          <button
            key={item.id}
            type="button"
            className={styles.opt}
            data-selected={item.id === selectedId}
            onClick={() => {
              if (item.id !== selectedId) {
                setManufacturerId(item.id);
                setSapId("");
              }
              setSheet(null);
            }}
          >
            <span className={styles.radio} />
            <span className={styles.optCopy}>
              <b>{item.name}</b>
              <span className={styles.optSecondary}>{registrationCountLabel(item.godowns.length)}</span>
            </span>
          </button>
        ))}
      </BottomSheet>

      <BottomSheet
        open={sheet === "sap"}
        title="Role"
        onClose={() => setSheet(null)}
        style={insightSheetStyle}
      >
        <p className={styles.sheetNote}>
          Every tab reads data for the selected role.
        </p>
        {manufacturer?.godowns.length ? manufacturer.godowns.map((item) => (
          <button
            key={item.esiId}
            type="button"
            className={styles.opt}
            data-selected={item.esiId === selectedSapId}
            onClick={() => {
              setSapId(item.esiId);
              setSheet(null);
            }}
          >
            <span className={styles.radio} />
            <span className={styles.optCopy}>
              <b>{godownTitle(item)}</b>
              {(item.sap && item.role) || !item.active ? (
                <span className={styles.optMeta}>
                  {item.sap && item.role ? <span className={styles.optSecondary}>{item.role}</span> : null}
                  {item.active ? null : <span className={styles.inactiveChip}>Inactive</span>}
                </span>
              ) : null}
            </span>
          </button>
        )) : (
          <p className={styles.sheetNote}>This manufacturer has no roles linked.</p>
        )}
      </BottomSheet>
    </SpScreen>
  );
}
