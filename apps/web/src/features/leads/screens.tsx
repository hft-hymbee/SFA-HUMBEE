"use client";

import { Button, IconButton, StandardChip, TextField } from "humbee-design-system";
import { useRouter } from "next/navigation";
import { useState, type ChangeEvent, type ReactNode } from "react";
import { ulid } from "ulid";
import { createIdempotencyKey } from "@/src/shared/api";
import { useConnectivity } from "@/src/shared/capabilities";
import { SpCard, SpInlineAlert, SpScreen, SpSectionLabel, SpStickyFooter } from "@/src/features/shell/components";
import {
  buildCaptureLeadBody,
  createEmptyLeadDraft,
  validateLeadDraft,
  withManufacturerName,
  type LeadFormDraft,
} from "./form-state";
import { useCaptureLead } from "./hooks";
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

  const addManufacturerName = () => updateDraft({
    manufacturerNames: withManufacturerName(draft.manufacturerNames, draft.manufacturerNameInput),
    manufacturerNameInput: "",
  });
  const removeManufacturerName = (name: string) => updateDraft({
    manufacturerNames: draft.manufacturerNames.filter((existing) => existing !== name),
  });

  const submitLead = () => {
    if (Object.values(errors).some(Boolean) || capture.isPending || !writesEnabled) {
      setShowErrors(true);
      return;
    }
    capture.mutate(
      { body: buildCaptureLeadBody(draft, leadId), idempotencyKey },
      { onSuccess: () => router.replace("/sp/more") },
    );
  };

  return (
    <SpScreen title="Capture lead" back offline={!writesEnabled}>
      <div className="sp-content">
        <LeadSection label="Manufacturers">
          <form
            className={styles.manufacturerForm}
            onSubmit={(event) => {
              event.preventDefault();
              addManufacturerName();
            }}
          >
            <TextField
              label="Manufacturer names"
              placeholder="Type a name and tap +"
              required
              fullWidth
              value={draft.manufacturerNameInput}
              error={shouldShow("manufacturerNames")}
              helperText={shouldShow("manufacturerNames") ? errors.manufacturerNames : "Brands not yet on Humbee."}
              inputProps={{ autoCapitalize: "words", enterKeyHint: "done" }}
              endAdornment={
                <IconButton
                  iconName="Add"
                  color="primary"
                  disabled={!draft.manufacturerNameInput.trim()}
                  onClick={addManufacturerName}
                  style={{ marginBlock: "calc(-1 * (var(--space-sm) + var(--space-xs) / 4))" }}
                />
              }
              onChange={(event) => updateDraft({ manufacturerNameInput: inputValue(event) })}
            />
            {draft.manufacturerNames.length > 0 ? (
              <div className={styles.chips}>
                {draft.manufacturerNames.map((name) => (
                  <StandardChip
                    key={name}
                    label={name}
                    selected
                    showDelete
                    capitalise={false}
                    onChange={() => removeManufacturerName(name)}
                  />
                ))}
              </div>
            ) : null}
          </form>
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

        <LeadSection label="Company">
          <TextField
            label="Company name"
            placeholder="Registered company name"
            required
            fullWidth
            value={draft.companyName}
            error={shouldShow("companyName")}
            helperText={shouldShow("companyName") ? errors.companyName : undefined}
            inputProps={{ autoCapitalize: "words", autoComplete: "organization" }}
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
