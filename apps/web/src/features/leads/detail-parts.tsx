"use client";

import { Button, Icon, PaperElevation, StatusChip, type StatusChipProps } from "humbee-design-system";
import type { CSSProperties, ReactNode } from "react";
import { leadDateTime, leadRoleLabel, leadTurnover } from "./format";
import { LeadInitials } from "./list-parts";
import type { LeadDetailOut } from "./service";
import styles from "./leads.module.css";

const NOT_PROVIDED = "Not provided";

const STATUS: Record<LeadDetailOut["status"], { chip: NonNullable<StatusChipProps["status"]>; label: string }> = {
  captured: { chip: "pending", label: "Captured" },
  in_review: { chip: "partially-completed", label: "In review" },
  qualified: { chip: "approved", label: "Qualified" },
  rejected: { chip: "cancelled", label: "Rejected" },
};

/** PaperElevation re-skinned with the app's warm surface tokens. */
const CARD_STYLE: CSSProperties = {
  background: "var(--hb-surface-raised, var(--surface-card))",
  borderRadius: "var(--radius-md)",
  boxShadow: "var(--hb-shadow-raised)",
};

function Card({ children }: { children: ReactNode }) {
  return (
    <PaperElevation padding={16} style={CARD_STYLE}>
      {children}
    </PaperElevation>
  );
}

function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section>
      <h3 className={styles.sectionLabel}>{label}</h3>
      <Card>{children}</Card>
    </section>
  );
}

function blank(value: string | null | undefined): value is null | undefined | "" {
  return value == null || value.trim() === "";
}

function Row({ label, value, sub }: { label: string; value: string | null | undefined; sub?: string | null }) {
  const empty = blank(value);
  return (
    <div className={styles.kv}>
      <dt>{label}</dt>
      <dd className={empty ? styles.empty : undefined}>
        {empty ? NOT_PROVIDED : value}
        {!empty && sub ? <span className={styles.kvSub}>{sub}</span> : null}
      </dd>
    </div>
  );
}

function openHref(href: string) {
  window.location.href = href;
}

export function LeadDetailBody({
  lead,
  viewerIsCapturer,
}: {
  lead: LeadDetailOut;
  viewerIsCapturer: boolean;
}) {
  const status = STATUS[lead.status] ?? { chip: "default" as const, label: lead.status };
  const capturedAt = leadDateTime(lead.captured_at);
  const capturer = lead.captured_by;
  const capturerSub = viewerIsCapturer
    ? capturer.employee_code
    : [capturer.employee_code, leadRoleLabel(capturer.role_code)].filter(Boolean).join(" · ") || null;

  return (
    <div className={styles.detail}>
      <Card>
        <div className={styles.heroTop}>
          <LeadInitials name={lead.company_name} large />
          <div className={styles.heroText}>
            <h2 className={styles.heroTitle}>{lead.company_name}</h2>
            <p className={styles.heroMeta}>Captured {capturedAt}</p>
          </div>
        </div>
        <div className={styles.heroStatus}>
          <StatusChip status={status.chip} label={status.label} type="outlined" />
        </div>
        <div className={styles.heroActions}>
          <Button
            variant="filled"
            color="primary"
            label="Call"
            leftIcon={<Icon name="Call" size={20} color="currentColor" />}
            disabled={blank(lead.mobile)}
            onClick={() => openHref(`tel:${lead.mobile}`)}
            style={{ width: "100%" }}
          />
          <Button
            variant="outlined"
            color="primary"
            label="Email"
            disabled={blank(lead.email)}
            onClick={() => openHref(`mailto:${lead.email}`)}
            style={{ width: "100%" }}
          />
        </div>
      </Card>

      <Section label="Manufacturer">
        <dl className={styles.kvList}>
          <Row label="Manufacturer name" value={lead.company_name} />
          <Row label="Annual turnover" value={leadTurnover(lead.annual_turnover_cr)} />
          <Row label="Head office" value={lead.head_office_location} />
        </dl>
      </Section>

      <Section label="Contact">
        <dl className={styles.kvList}>
          <Row label="Name" value={lead.name} />
          <Row label="Designation" value={lead.designation} />
          <Row label="Mobile" value={lead.mobile} />
          <Row label="Email" value={lead.email} />
        </dl>
      </Section>

      <Section label="Message">
        {blank(lead.message) ? (
          <p className={`${styles.message} ${styles.empty}`}>No message added.</p>
        ) : (
          <p className={styles.message}>{lead.message}</p>
        )}
      </Section>

      <Section label="Captured by">
        <dl className={styles.kvList}>
          <Row
            label="Employee"
            value={viewerIsCapturer ? "You" : capturer.name}
            sub={capturerSub}
          />
          {!viewerIsCapturer && !blank(capturer.reports_to_name) ? (
            <Row label="Reports to" value={capturer.reports_to_name} />
          ) : null}
          <Row label="Date & time" value={capturedAt} />
        </dl>
      </Section>
    </div>
  );
}
