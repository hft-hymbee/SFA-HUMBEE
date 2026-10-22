"use client";

import {
  Button,
  EmptyState,
  ErrorState,
  SkeletonRow,
  StatusChip,
} from "humbee-design-system";
import type { CandidateDetailResponse, DetailBlock, TimelineStep } from "@humbee/api-contract";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useApprovalDetail, useApprovalTimeline } from "@/src/features/approvals/hooks";
import { useConnectivity } from "@/src/shared/capabilities";
import {
  SpCard,
  SpScreen,
  SpSectionLabel,
  SpStatusRow,
  StatusHistory,
  type StatusHistoryStep,
} from "@/src/features/shell/components";
import { SpInlineSkeleton, SpListSkeleton } from "@/src/features/shell/loading";
import { useOutletCandidate } from "./service";

type StatusTone = "pending" | "approved" | "partially-completed" | "cancelled" | "not-verified" | "verified" | "default";

const timelineActionLabels: Record<string, string> = {
  submitted: "Submitted",
  routed: "Routed",
  escalated: "Escalated",
  edited: "Edited",
  approved: "Approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  awaiting_decision: "Awaiting decision",
};

function humanLabel(value: string | null | undefined) {
  const label = (value ?? "").replace(/_/g, " ").trim().toLowerCase();
  return label ? `${label.charAt(0).toUpperCase()}${label.slice(1)}` : "-";
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

function statusTone(status: string | null | undefined): StatusTone {
  const normalized = (status ?? "").toLowerCase();
  if (["approved", "auto_approved"].includes(normalized)) return "approved";
  if (["submitted", "registered", "completed", "active"].includes(normalized)) return "verified";
  if (normalized === "approved_with_edits") return "partially-completed";
  if (["rejected", "withdrawn", "expired", "cancelled"].includes(normalized)) return "cancelled";
  if (["submission_failed", "failed", "terminal_failure"].includes(normalized)) return "not-verified";
  if (["pending", "pending_approval", "queued", "running", "draft"].includes(normalized)) return "pending";
  return "default";
}

function statusMessage(candidate: CandidateDetailResponse, approvalStatus: string | undefined) {
  if (candidate.status === "submitted") return "Approved and submitted to Humbee.";
  if (candidate.status === "submission_failed") {
    return candidate.submission_error
      ? `Humbee onboarding failed: ${candidate.submission_error}`
      : "Humbee onboarding failed.";
  }
  if (approvalStatus === "rejected") return "Rejected by manager.";
  if (approvalStatus === "withdrawn") return "Withdrawn.";
  return "Waiting for manager approval.";
}

function timelineState(state: string): StatusHistoryStep["state"] {
  if (state === "done" || state === "edited" || state === "rejected" || state === "current") return state;
  return "pending";
}

function timelineActionLabel(action: string) {
  return timelineActionLabels[action] ?? humanLabel(action);
}

function timelineDetail(note: string | null | undefined) {
  return note?.trim() || undefined;
}

function timelineSteps(items: TimelineStep[]): StatusHistoryStep[] {
  return items.map((step) => ({
    label: timelineActionLabel(step.action),
    detail: timelineDetail(step.note),
    time: formatDateTime(step.occurred_at),
    state: timelineState(step.state),
  }));
}

function addressText(address: CandidateDetailResponse["operational_address"] | CandidateDetailResponse["registered_address"]) {
  const lines = address.company_address;
  return [
    lines.address_line_1,
    lines.address_line_2,
    lines.address_line_3,
    `State ${address.state_id}`,
    `District ${address.district_id}`,
    "location_id" in address ? `Location ${address.location_id}` : null,
    "pincode" in address ? address.pincode : null,
  ].filter(Boolean).join(", ");
}

function documentLabel(candidate: CandidateDetailResponse) {
  if (candidate.company_gstin) return candidate.company_gstin;
  if (candidate.pancard_no) return candidate.pancard_no;
  return "-";
}

function approvalBlockByLabel(blocks: DetailBlock[], label: string) {
  return blocks.find((block) => block.label.toLowerCase() === label.toLowerCase());
}

function approvalText(value: unknown) {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

function approvalRoleText(line: unknown) {
  if (!line || typeof line !== "object" || Array.isArray(line)) return approvalText(line);
  const item = line as Record<string, unknown>;
  const manufacturer = approvalText(item.manufacturer ?? item.manufacturer_name);
  const role = approvalText(item.label ?? item.role ?? item.role_name);
  const status = approvalText(item.status);
  return [manufacturer, role, status].filter(Boolean).join(" · ") || null;
}

function approvalRoleTexts(blocks: DetailBlock[]) {
  const roles = approvalBlockByLabel(blocks, "Roles requested");
  const lines = Array.isArray(roles?.payload.lines) ? roles.payload.lines : [];
  return lines.map(approvalRoleText);
}

function approvalIndustryText(line: unknown) {
  if (!line || typeof line !== "object" || Array.isArray(line)) return approvalText(line);
  const item = line as Record<string, unknown>;
  const primary = approvalText(item.primary ?? item.primary_industry ?? item.primary_industry_name);
  const secondary = approvalText(item.secondary ?? item.secondary_industry);
  const role = approvalText(item.role ?? item.role_name ?? item.label);
  return [[primary, secondary].filter(Boolean).join(" > "), role].filter(Boolean).join(" - ") || null;
}

function approvalIndustryTexts(blocks: DetailBlock[]) {
  const industries = approvalBlockByLabel(blocks, "Industries requested");
  const lines = Array.isArray(industries?.payload.lines) ? industries.payload.lines : [];
  return lines.map(approvalIndustryText);
}

export function OutletOnboardingDetailScreen({ candidateId }: { candidateId: string }) {
  const router = useRouter();
  const { isOnline } = useConnectivity();
  const candidate = useOutletCandidate(candidateId);
  const approvalId = candidate.data?.approval_request_id ?? "";
  const approval = useApprovalDetail(approvalId);
  const timeline = useApprovalTimeline(approvalId);

  if (!candidateId) {
    return (
      <SpScreen title="Onboarding request" back>
        <EmptyState
          icon="InventoryOutlined"
          title="No onboarding selected"
          message="Open an outlet onboarding request from My requests."
          actionLabel="My requests"
          onAction={() => router.replace("/sp/more/requests")}
        />
      </SpScreen>
    );
  }

  if (candidate.isPending) {
    return (
      <SpScreen title="Onboarding request" back offline={!isOnline}>
        <div className="sp-content">
          <SkeletonRow />
          <SkeletonRow />
          <SkeletonRow />
        </div>
      </SpScreen>
    );
  }

  if (candidate.isError || !candidate.data) {
    return (
      <SpScreen title="Onboarding request" back offline={!isOnline}>
        <ErrorState
          title="Onboarding unavailable"
          message="This outlet onboarding request could not be loaded."
          onRetry={() => { void candidate.refetch(); }}
        />
      </SpScreen>
    );
  }

  const detail = candidate.data;
  const detailIndustries = detail.industries;
  const approvalStatus = approval.data?.request.status;
  const approvalPending = approval.isPending && Boolean(approvalId);
  const roleCount = detail.roles.length;
  const industryCount = detailIndustries.length;
  const approvalRoles = approvalRoleTexts(approval.data?.blocks ?? []);
  const approvalIndustries = approvalIndustryTexts(approval.data?.blocks ?? []);
  const steps = timelineSteps(timeline.data?.items ?? approval.data?.timeline ?? []);

  return (
    <SpScreen title="Onboarding request" back offline={!isOnline}>
      <div className="sp-content">
        <SpCard>
          <div className="sp-stack">
            <div className="sp-row" style={{ alignItems: "flex-start", justifyContent: "space-between" }}>
              <div>
                <h2 className="sp-title" style={{ margin: 0 }}>{detail.display_name}</h2>
                <p className="sp-copy" style={{ marginTop: "var(--space-xs)" }}>
                  {documentLabel(detail)} · {roleCount + industryCount} association{roleCount + industryCount === 1 ? "" : "s"} · {detail.operational_address.pincode}
                </p>
              </div>
              {approvalPending ? (
                <SpInlineSkeleton width={92} height={24} />
              ) : (
                <StatusChip
                  status={statusTone(approvalStatus ?? detail.status)}
                  label={humanLabel(approvalStatus ?? detail.status)}
                  type="filled"
                />
              )}
            </div>
            <SpStatusRow label="Approval" value={approvalPending ? <SpInlineSkeleton width={132} height={14} /> : humanLabel(approvalStatus ?? detail.status)} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
            <SpStatusRow label="Humbee status" value={humanLabel(detail.status)} tone={detail.status === "submission_failed" ? "var(--color-error)" : undefined} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
            <SpStatusRow label="Submitted" value={formatDateTime(detail.created_at)} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
            {detail.humbee_company_id ? <SpStatusRow label="Humbee ID" value={detail.humbee_company_id} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" /> : null}
            {detail.submission_error ? <SpStatusRow label="Failure" value={detail.submission_error} tone="var(--color-error)" labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" /> : null}
            <p className="sp-copy" style={{ margin: 0 }}>{statusMessage(detail, approvalStatus)}</p>
          </div>
        </SpCard>

        <div>
          <SpSectionLabel>Owner and document</SpSectionLabel>
          <SpCard>
            <div className="sp-stack">
              <SpStatusRow label="Owner phone" value={detail.owner_phone_e164} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
              <SpStatusRow label={detail.company_gstin ? "GSTIN" : "PAN"} value={documentLabel(detail)} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
              <SpStatusRow label="Candidate ID" value={detail.id} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
            </div>
          </SpCard>
        </div>

        <div>
          <SpSectionLabel>Address details</SpSectionLabel>
          <SpCard>
            <div className="sp-stack">
              <SpStatusRow label="Registered" value={addressText(detail.registered_address)} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
              <SpStatusRow label="Operational" value={addressText(detail.operational_address)} labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />
            </div>
          </SpCard>
        </div>

        <div>
          <SpSectionLabel>Manufacturer roles</SpSectionLabel>
          <SpCard>
            <div className="sp-stack">
              {detail.roles.length ? detail.roles.map((role, index) => (
                <SpStatusRow
                  key={`${role.manufacturer_id}-${role.firm_role_id}-${index}`}
                  label={`Role ${index + 1}`}
                  value={approvalRoles[index] ?? `${role.manufacturer_id} · ${role.firm_role_id}`}
                  labelClassName="sp-meta"
                  columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)"
                />
              )) : <SpStatusRow label="Roles" value="No manufacturer roles requested." labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />}
            </div>
          </SpCard>
        </div>

        <div>
          <SpSectionLabel>Industries</SpSectionLabel>
          <SpCard>
            <div className="sp-stack">
              {detailIndustries.length ? detailIndustries.map((industry, index) => (
                <SpStatusRow
                  key={`${industry.primary_industry_id}-${industry.secondary_industry_id}-${index}`}
                  label={`Industry ${index + 1}`}
                  value={approvalIndustries[index] ?? `${industry.primary_industry_name} > ${industry.secondary_industry} - ${industry.role_name}`}
                  labelClassName="sp-meta"
                  columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)"
                />
              )) : <SpStatusRow label="Industries" value="No industry associations requested." labelClassName="sp-meta" columns="calc((var(--space-2xl) * 2) + var(--space-sm)) minmax(0, 1fr)" />}
            </div>
          </SpCard>
        </div>

        {timeline.isPending && approvalId ? (
          <div>
            <SpSectionLabel>Status history</SpSectionLabel>
            <SpCard padded={false}>
              <SpListSkeleton rows={2} />
            </SpCard>
          </div>
        ) : steps.length ? (
          <StatusHistory steps={steps} historyKey={approvalId} />
        ) : null}

        <Button
          color="primary"
          label="Back to my requests"
          onClick={() => router.push("/sp/more/requests")}
          style={{ width: "100%" }}
          variant="outlined"
        />
      </div>
    </SpScreen>
  );
}
