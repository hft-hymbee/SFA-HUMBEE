"use client";

import { Button, EmptyState, ErrorState, FAB, TextField } from "humbee-design-system";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, type ChangeEvent, type ReactNode } from "react";
import { ulid } from "ulid";
import { createIdempotencyKey } from "@/src/shared/api";
import { useConnectivity } from "@/src/shared/capabilities";
import { useDebouncedSearchQuery } from "@/src/shared/state";
import { SpCard, SpInlineAlert, SpScreen, SpSectionLabel, SpStickyFooter } from "@/src/features/shell/components";
import { SpPageSkeleton } from "@/src/features/shell/loading";
import { LeadDetailBody } from "./detail-parts";
import {
  DEFAULT_LEAD_FILTERS,
  hasActiveLeadFilters,
  leadFiltersFromSearchParams,
  leadFiltersToSearchParams,
  type LeadFilters,
} from "./filters";
import {
  buildCaptureLeadBody,
  createEmptyLeadDraft,
  validateLeadDraft,
  type LeadFormDraft,
} from "./form-state";
import { isLeadId, isNotFound } from "./lead-id";
import { useActorId, useCaptureLead, useLead, useLeads } from "./hooks";
import { LeadFilterBar, LeadListBody } from "./list-parts";
import styles from "./leads.module.css";

function LeadSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <SpSectionLabel>{label}</SpSectionLabel>
      <SpCard>
        <div className="sp-stack">{children}</div>
      </SpCard>
    </div>
  );
}

export function CaptureLeadScreen() {
  const router = useRouter();
  const { writesEnabled } = useConnectivity();
  const [draft, setDraft] = useState<LeadFormDraft>(createEmptyLeadDraft);
  const [leadId] = useState(ulid);
  const [idempotencyKey] = useState(createIdempotencyKey);
  const [showErrors, setShowErrors] = useState(false);
  const capture = useCaptureLead();

  const errors = validateLeadDraft(draft);
  const shouldShow = (field: keyof typeof errors) => showErrors && Boolean(errors[field]);
  const updateDraft = (patch: Partial<LeadFormDraft>) => setDraft((current) => ({ ...current, ...patch }));
  const inputValue = (event: ChangeEvent) => (event.target as HTMLInputElement).value;

  const submitLead = () => {
    if (Object.values(errors).some(Boolean) || capture.isPending || !writesEnabled) {
      setShowErrors(true);
      return;
    }
    capture.mutate(
      { body: buildCaptureLeadBody(draft, leadId), idempotencyKey },
      { onSuccess: () => router.replace("/sp/leads") },
    );
  };

  return (
    <SpScreen title="Capture lead" back offline={!writesEnabled}>
      <div className="sp-content">
        <LeadSection label="Manufacturer">
          <TextField
            label="Manufacturer name"
            placeholder="Registered company name"
            required
            fullWidth
            value={draft.companyName}
            error={shouldShow("companyName")}
            helperText={shouldShow("companyName") ? errors.companyName : "A manufacturer not yet on Humbee."}
            inputProps={{ autoCapitalize: "words", autoComplete: "organization", maxLength: 120 }}
            onChange={(event) => updateDraft({ companyName: inputValue(event) })}
          />
          <TextField
            label="Annual turnover (₹ cr)"
            placeholder="Approx. turnover, e.g. 25"
            fullWidth
            value={draft.annualTurnoverCr}
            error={shouldShow("annualTurnoverCr")}
            helperText={shouldShow("annualTurnoverCr") ? errors.annualTurnoverCr : undefined}
            inputProps={{ inputMode: "decimal" }}
            onChange={(event) => updateDraft({ annualTurnoverCr: inputValue(event) })}
          />
          <TextField
            label="Head office location"
            placeholder="City or area"
            fullWidth
            value={draft.headOfficeLocation}
            inputProps={{ autoCapitalize: "words" }}
            onChange={(event) => updateDraft({ headOfficeLocation: inputValue(event) })}
          />
        </LeadSection>

        <LeadSection label="Contact">
          <TextField
            label="Name"
            placeholder="Contact person's full name"
            required
            fullWidth
            value={draft.name}
            error={shouldShow("name")}
            helperText={shouldShow("name") ? errors.name : undefined}
            inputProps={{ autoCapitalize: "words", autoComplete: "name" }}
            onChange={(event) => updateDraft({ name: inputValue(event) })}
          />
          <TextField
            label="Designation"
            placeholder="e.g. Purchase Manager"
            fullWidth
            value={draft.designation}
            error={shouldShow("designation")}
            helperText={shouldShow("designation") ? errors.designation : undefined}
            inputProps={{ autoCapitalize: "words" }}
            onChange={(event) => updateDraft({ designation: inputValue(event) })}
          />
          <TextField
            label="Mobile number"
            placeholder="10-digit mobile number"
            required
            fullWidth
            value={draft.mobile}
            error={shouldShow("mobile")}
            helperText={shouldShow("mobile") ? errors.mobile : undefined}
            inputProps={{ inputMode: "tel", maxLength: 10, pattern: "[0-9]*", autoComplete: "tel-national" }}
            onChange={(event) => updateDraft({ mobile: inputValue(event).replace(/\D/g, "").slice(0, 10) })}
          />
          <TextField
            label="Email"
            placeholder="name@company.com"
            required
            fullWidth
            value={draft.email}
            error={shouldShow("email")}
            helperText={shouldShow("email") ? errors.email : undefined}
            inputProps={{ inputMode: "email", type: "email", autoCapitalize: "none", autoCorrect: "off", autoComplete: "email" }}
            onChange={(event) => updateDraft({ email: inputValue(event) })}
          />
        </LeadSection>

        <LeadSection label="Notes">
          <TextField
            label="Message"
            placeholder="Anything the team should know"
            multiline
            rows={3}
            fullWidth
            value={draft.message}
            onChange={(event) => updateDraft({ message: inputValue(event) })}
          />
        </LeadSection>

        {capture.isError ? <SpInlineAlert tone="error">{capture.error.message}</SpInlineAlert> : null}
      </div>
      <SpStickyFooter>
        <Button
          variant="filled"
          color="primary"
          label={!writesEnabled ? "Connect to submit" : capture.isPending ? "Submitting…" : "Submit lead"}
          disabled={!writesEnabled || capture.isPending}
          onClick={submitLead}
          style={{ width: "100%" }}
        />
      </SpStickyFooter>
    </SpScreen>
  );
}

const MY_LEADS_PATH = "/sp/leads";

/** SO filters never carry an employee: an SO only ever sees their own leads. */
function soFilters(filters: LeadFilters): LeadFilters {
  return { ...filters, employeeId: "" };
}

export function MyLeadsScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isOnline } = useConnectivity();
  // Local state is the source of truth; the URL mirrors it so filters survive opening a lead.
  const [filters, setFilters] = useState<LeadFilters>(
    () => soFilters(leadFiltersFromSearchParams(new URLSearchParams(searchParams.toString()))),
  );
  const debouncedQ = useDebouncedSearchQuery(filters.q);
  const applied = useMemo(() => ({ ...filters, q: debouncedQ }), [filters, debouncedQ]);
  const leads = useLeads(applied);
  const filtersActive = hasActiveLeadFilters(applied);

  useEffect(() => {
    const query = leadFiltersToSearchParams(applied).toString();
    if (query === window.location.search.replace(/^\?/, "")) return;
    router.replace(query ? `${MY_LEADS_PATH}?${query}` : MY_LEADS_PATH, { scroll: false });
  }, [applied, router]);

  const clearFilters = () => setFilters(DEFAULT_LEAD_FILTERS);
  const captureLead = () => router.push("/sp/leads/new");
  const total = leads.data?.pages[0]?.total ?? 0;
  const showFab = leads.isSuccess && (total > 0 || filtersActive);

  return (
    <SpScreen title="My leads" back offline={!isOnline}>
      <div className="sp-content">
        <LeadFilterBar filters={filters} onChange={(next) => setFilters(soFilters(next))} />
        <LeadListBody
          query={leads}
          showCapturer={false}
          onOpen={(id) => router.push(`/sp/leads/detail?id=${encodeURIComponent(id)}`)}
          emptyState={(
            <EmptyState
              icon="PersonRounded"
              title="No leads yet"
              message="Leads you capture for new manufacturers will show up here."
              actionLabel="Capture a lead"
              onAction={captureLead}
            />
          )}
          onClearFilters={clearFilters}
          filtersActive={filtersActive}
        />
        {showFab ? <div className={styles.fabSpacer} aria-hidden="true" /> : null}
      </div>
      {showFab ? (
        <FAB iconName="Add" label="Capture lead" onClick={captureLead} style={{ bottom: "var(--space-md)" }} />
      ) : null}
    </SpScreen>
  );
}

export function LeadDetailScreen({ leadId }: { leadId: string }) {
  const router = useRouter();
  const { isOnline } = useConnectivity();
  const viewerId = useActorId();
  const lead = useLead(leadId);
  const title = "Lead details";

  if (!isLeadId(leadId) || (lead.isError && isNotFound(lead.error))) {
    return (
      <SpScreen title={title} back offline={!isOnline}>
        <EmptyState
          icon="Warning"
          title="Lead not found"
          message="This lead doesn't exist or isn't in your scope."
          actionLabel="Back to leads"
          onAction={() => router.replace(MY_LEADS_PATH)}
        />
      </SpScreen>
    );
  }

  if (lead.isPending) {
    return (
      <SpScreen title={title} back offline={!isOnline}>
        <SpPageSkeleton rows={4} />
      </SpScreen>
    );
  }

  if (lead.isError) {
    return (
      <SpScreen title={title} back offline={!isOnline}>
        <ErrorState
          title="Couldn't load this lead"
          message="Check your connection and try again."
          retryLabel="Try again"
          onRetry={() => void lead.refetch()}
        />
      </SpScreen>
    );
  }

  return (
    <SpScreen title={title} back offline={!isOnline}>
      <div className="sp-content">
        <LeadDetailBody lead={lead.data} viewerIsCapturer={lead.data.captured_by.id === viewerId} />
      </div>
    </SpScreen>
  );
}
