"use client";

import {
  Button,
  EmptyState,
  ErrorState,
  Icon,
  Select,
  TextField,
} from "humbee-design-system";
import type { ManufacturerRoleOut, SubmitCandidateBody } from "@humbee/api-contract";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";
import { ulid } from "ulid";
import {
  createIdempotencyKey,
  ApiClientError,
} from "@/src/shared/api";
import { createBrowserCapabilities, getCurrentLocationLabel, useConnectivity } from "@/src/shared/capabilities";
import { SpCard, SpInlineAlert, SpProcessProgress, SpScreen, SpSectionLabel, SpStatusRow, SpStickyFooter } from "@/src/features/shell/components";
import {
  useFirmAddressDistricts,
  useFirmAddressOptions,
  useFirmAddressStates,
  useIndustries,
  useManufacturerRoles,
  useOutletOnboardingMutations,
} from "@/src/features/outlets/service";

type BuyerType = "VCP" | "Influencer";
type IdMode = "GST" | "PAN";
type StepId = 0 | 1 | 2 | 3;

const OWNER_MOBILE_INPUT_ID = "sp-owner-mobile-input";
type SuggestionOption = {
  value: string;
  label: string;
};

interface LocationFix {
  latitude: number;
  longitude: number;
  label: string;
  capturedAt: string;
}

interface ManufacturerRoleRow {
  kind: "manufacturer";
  manufacturerId: string;
  roleId: string;
  manufacturerSearch: string;
}

interface IndustryRoleRow {
  kind: "industry";
  primaryIndustryId: string;
  secondaryIndustryId: string;
  roleName: string;
}

type RoleRow = ManufacturerRoleRow | IndustryRoleRow;

interface IndustrySecondaryOption {
  secondary_industry_id: string;
  secondary_industry: string;
}

interface IndustryPrimaryOption {
  primary_industry_id: string;
  primary_industry_name: string;
  secondaries: IndustrySecondaryOption[];
}

interface OnboardDraft {
  buyerType: BuyerType | "";
  name: string;
  mobile: string;
  otpCode: string;
  challengeId: string;
  ownerVerified: boolean;
  verifiedUntil: string;
  dob: string;
  idMode: IdMode;
  gst: string;
  pan: string;
  documentLookedUp: boolean;
  firm: string;
  address1: string;
  address2: string;
  address3: string;
  stateId: string;
  districtId: string;
  pincode: string;
  locationId: string;
  roleRows: RoleRow[];
  location: LocationFix | null;
}

const emptyManufacturerRow = (): ManufacturerRoleRow => ({
  kind: "manufacturer",
  manufacturerId: "",
  roleId: "",
  manufacturerSearch: "",
});

const emptyIndustryRow = (): IndustryRoleRow => ({
  kind: "industry",
  primaryIndustryId: "",
  secondaryIndustryId: "",
  roleName: "",
});

const emptyRoleRow = (): RoleRow => emptyManufacturerRow();

function isManufacturerRow(row: RoleRow): row is ManufacturerRoleRow {
  return row.kind === "manufacturer";
}

function isIndustryRow(row: RoleRow): row is IndustryRoleRow {
  return row.kind === "industry";
}

const MOBILE_RE = /^[6-9]\d{9}$/;
const GST_RE = /^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$/;
const PAN_RE = /^[A-Z]{5}\d{4}[A-Z]$/;
const MIN_OWNER_AGE_YEARS = 14;

function todayAtMidnight(): Date {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today;
}

function isDobValid(dob: string): boolean {
  if (!dob) return true;
  const parsed = new Date(`${dob}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return false;
  const today = todayAtMidnight();
  if (parsed.getTime() > today.getTime()) return false;
  let age = today.getFullYear() - parsed.getFullYear();
  const hadBirthdayThisYear = today.getMonth() > parsed.getMonth()
    || (today.getMonth() === parsed.getMonth() && today.getDate() >= parsed.getDate());
  if (!hadBirthdayThisYear) age -= 1;
  return age >= MIN_OWNER_AGE_YEARS;
}

function maxDobValue(): string {
  const cutoff = todayAtMidnight();
  cutoff.setFullYear(cutoff.getFullYear() - MIN_OWNER_AGE_YEARS);
  return cutoff.toISOString().slice(0, 10);
}

const initialDraft: OnboardDraft = {
  buyerType: "",
  name: "",
  mobile: "",
  otpCode: "",
  challengeId: "",
  ownerVerified: false,
  verifiedUntil: "",
  dob: "",
  idMode: "GST",
  gst: "",
  pan: "",
  documentLookedUp: false,
  firm: "",
  address1: "",
  address2: "",
  address3: "",
  stateId: "",
  districtId: "",
  pincode: "",
  locationId: "",
  roleRows: [emptyManufacturerRow()],
  location: null,
};

function normalizeMobile(value: string) {
  return value.replace(/\D/g, "").slice(0, 10);
}

function normalizeOtp(value: string) {
  return value.replace(/\D/g, "").slice(0, 8);
}

function normalizePincode(value: string) {
  return value.replace(/\D/g, "").slice(0, 6);
}

function normalizeUpper(value: string, max: number) {
  return value.toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, max);
}

function inputValue(event: ChangeEvent) {
  return (event.currentTarget as HTMLInputElement).value;
}

function requiredMark(label: string) {
  return `${label}*`;
}

function errorMessage(error: unknown, fallback = "Something went wrong. Try again.") {
  return error instanceof ApiClientError ? error.message : fallback;
}

function humanLabel(value: string | null | undefined) {
  const label = (value ?? "").replace(/_/g, " ").trim().toLowerCase();
  return label ? `${label.charAt(0).toUpperCase()}${label.slice(1)}` : "";
}

function selectedDocument(draft: OnboardDraft) {
  return draft.idMode === "GST" ? draft.gst : draft.pan;
}

function documentValid(draft: OnboardDraft) {
  return draft.idMode === "GST" ? GST_RE.test(draft.gst) : PAN_RE.test(draft.pan);
}

function ChipGroup({
  disabled = false,
  options,
  selected,
  onToggle,
}: {
  disabled?: boolean;
  options: string[];
  selected: (value: string) => boolean;
  onToggle: (value: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-sm)" }}>
      {options.map((option) => (
        <button
          className="sp-filter-chip"
          data-active={selected(option)}
          disabled={disabled}
          key={option}
          onClick={() => {
            if (!disabled) onToggle(option);
          }}
          type="button"
        >
          {option}
        </button>
      ))}
    </div>
  );
}

function BuyerTypeOption({
  active,
  description,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  description: string;
  icon: string;
  label: BuyerType;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={active}
      className="sp-buyer-type-card"
      data-active={active}
      onClick={onClick}
      type="button"
    >
      <span className="sp-buyer-type-card__icon">
        <Icon name={icon} size={22} color="currentColor" />
      </span>
      <span className="sp-buyer-type-card__copy">
        <strong>{label}</strong>
        <span>{description}</span>
      </span>
    </button>
  );
}

function SuggestionField({
  disabled = false,
  error = false,
  helperText,
  label,
  onQueryChange,
  onSelect,
  options,
  placeholder,
  query,
}: {
  disabled?: boolean;
  error?: boolean;
  helperText?: string;
  label: string;
  onQueryChange: (value: string) => void;
  onSelect: (option: SuggestionOption) => void;
  options: SuggestionOption[];
  placeholder: string;
  query: string;
}) {
  const [open, setOpen] = useState(false);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visibleOptions = options
    .filter((option) => (
      !normalizedQuery
      || option.label.toLocaleLowerCase().includes(normalizedQuery)
      || option.value.toLocaleLowerCase().includes(normalizedQuery)
    ))
    .slice(0, 20);

  return (
    <div
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
      onFocusCapture={() => {
        if (!disabled) setOpen(true);
      }}
      style={{ position: "relative" }}
    >
      <TextField
        disabled={disabled}
        error={error}
        helperText={helperText}
        label={label}
        onChange={(event) => {
          onQueryChange(inputValue(event));
          setOpen(true);
        }}
        placeholder={placeholder}
        startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
        value={query}
      />
      {open && !disabled ? (
        <div
          style={{
            background: "var(--surface-card)",
            border: "solid var(--color-neutral-300)",
            borderRadius: "var(--radius-md)",
            borderWidth: "thin",
            boxShadow: "var(--hb-shadow-raised)",
            left: 0,
            maxHeight: "calc(var(--space-2xl) * 5)",
            overflowY: "auto",
            position: "absolute",
            right: 0,
            top: "calc(100% + var(--space-2xs))",
            zIndex: 30,
          }}
        >
          {visibleOptions.length ? visibleOptions.map((option) => (
            <button
              key={option.value}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onSelect(option);
                setOpen(false);
              }}
              style={{
                background: "transparent",
                border: 0,
                color: "var(--color-text-primary)",
                cursor: "pointer",
                display: "block",
                font: "inherit",
                padding: "var(--space-sm) var(--space-md)",
                textAlign: "left",
                width: "100%",
              }}
              type="button"
            >
              {option.label}
            </button>
          )) : (
            <div className="sp-meta" style={{ padding: "var(--space-sm) var(--space-md)" }}>No suggestions found</div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function LinkButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: "transparent",
        border: 0,
        color: "var(--color-primary)",
        cursor: "pointer",
        font: "inherit",
        justifySelf: "start",
        padding: 0,
        textDecoration: "underline",
      }}
      type="button"
    >
      {children}
    </button>
  );
}

export default function Page() {
  const router = useRouter();
  const capabilities = useMemo(() => createBrowserCapabilities(), []);
  const { isOnline, writesEnabled } = useConnectivity();
  const [draft, setDraft] = useState<OnboardDraft>(initialDraft);
  const [currentStep, setCurrentStep] = useState<StepId>(0);
  const [showErrors, setShowErrors] = useState(false);
  const [locationState, setLocationState] = useState<"idle" | "capturing" | "error">("idle");
  const [submitKey, setSubmitKey] = useState(createIdempotencyKey);
  const [otpRequestKey, setOtpRequestKey] = useState(createIdempotencyKey);
  const [otpVerifyKey, setOtpVerifyKey] = useState(createIdempotencyKey);
  const [candidateId, setCandidateId] = useState(ulid);
  const [submittedCandidateId, setSubmittedCandidateId] = useState("");
  const [stateSearch, setStateSearch] = useState("");
  const [districtSearch, setDistrictSearch] = useState("");
  const [pincodeSearch, setPincodeSearch] = useState("");
  const [locationSearch, setLocationSearch] = useState("");
  const [industriesRequested, setIndustriesRequested] = useState(false);

  const statesQuery = useFirmAddressStates();
  const districtsQuery = useFirmAddressDistricts(draft.stateId);
  const optionsQuery = useFirmAddressOptions({
    districtId: draft.districtId,
    pincode: draft.pincode.length === 6 ? draft.pincode : undefined,
    locationId: draft.locationId || undefined,
  });
  const isVcp = draft.buyerType === "VCP";
  const rolesQuery = useManufacturerRoles();
  const industriesQuery = useIndustries(industriesRequested);
  const mutations = useOutletOnboardingMutations();

  const manufacturers = rolesQuery.data?.manufacturers ?? [];
  const industries = (
    (industriesQuery.data as { industries?: IndustryPrimaryOption[] } | undefined)?.industries ?? []
  );
  const roleOptionsFor = (manufacturerId: string): ManufacturerRoleOut[] => {
    const manufacturer = manufacturers.find((item) => item.manufacturer_id === manufacturerId);
    if (!manufacturer) return [];
    return isVcp ? manufacturer.vcp_roles : manufacturer.influencer_roles;
  };
  const manufacturersWithRoles = manufacturers.filter(
    (manufacturer) => roleOptionsFor(manufacturer.manufacturer_id).length > 0,
  );
  const stateOptions = statesQuery.data?.states ?? [];
  const districtOptions = districtsQuery.data?.districts ?? [];
  const locationOptions = optionsQuery.data?.locations ?? [];
  const pincodeOptions = optionsQuery.data?.pincodes ?? [];
  const stateSuggestions = stateOptions.map((state) => ({ label: state.state_name, value: state.state_id }));
  const districtSuggestions = districtOptions.map((district) => ({ label: district.district_name, value: district.district_id }));
  const pincodeSuggestions = pincodeOptions.map((pincode) => ({ label: pincode, value: pincode }));
  const locationSuggestions = locationOptions.map((location) => ({ label: location.location_name, value: location.location_id }));
  const selectedStateName = stateOptions.find((state) => state.state_id === draft.stateId)?.state_name ?? (stateSearch.trim() || draft.stateId);
  const selectedDistrictName = districtOptions.find((district) => district.district_id === draft.districtId)?.district_name ?? (districtSearch.trim() || draft.districtId);
  const selectedLocationName = locationOptions.find((location) => location.location_id === draft.locationId)?.location_name ?? draft.locationId;
  const usedManufacturerIds = new Set(
    draft.roleRows.filter(isManufacturerRow).map((row) => row.manufacturerId).filter(Boolean),
  );
  const usedSecondaryIndustryIds = new Set(
    draft.roleRows.filter(isIndustryRow).map((row) => row.secondaryIndustryId).filter(Boolean),
  );
  const allSecondaryIndustries = industries.flatMap((primary) => primary.secondaries);
  const hasUnusedManufacturer = usedManufacturerIds.size < manufacturersWithRoles.length;
  const hasUnusedIndustry = industriesRequested
    ? usedSecondaryIndustryIds.size < allSecondaryIndustries.length
    : true;
  const canAddAssociation = hasUnusedManufacturer || hasUnusedIndustry;

  const typeDone = Boolean(draft.buyerType);
  const userStepDone = Boolean(draft.name.trim()) && MOBILE_RE.test(draft.mobile) && draft.ownerVerified && isDobValid(draft.dob);
  const identityDone = documentValid(draft);
  const documentStepDone = !isVcp || (identityDone && draft.documentLookedUp);
  const firmNameDone = !isVcp || Boolean(draft.firm.trim());
  const addressDone = Boolean(draft.address1.trim() && draft.address2.trim() && draft.stateId && draft.districtId && draft.pincode.length === 6 && draft.locationId);
  const completeRoleRows = draft.roleRows.filter((row) => (
    isManufacturerRow(row)
      ? Boolean(row.manufacturerId && row.roleId)
      : Boolean(row.primaryIndustryId && row.secondaryIndustryId && row.roleName.trim())
  ));
  const completeManufacturerRows = completeRoleRows.filter(isManufacturerRow);
  const completeIndustryRows = completeRoleRows.filter(isIndustryRow);
  const rolesDone = completeRoleRows.length > 0;
  const locationDone = !isVcp || Boolean(draft.location);
  const detailsStepDone = documentStepDone && firmNameDone && addressDone && rolesDone && locationDone;
  const formComplete = typeDone && userStepDone && detailsStepDone;
  const primaryActionDisabled = currentStep === 0
    ? !typeDone
    : currentStep === 1
      ? !userStepDone
      : currentStep === 2
        ? !detailsStepDone || !writesEnabled
        : !formComplete || !writesEnabled || mutations.submitCandidate.isPending;
  const stepLabels = ["Buyer type", "User details", isVcp ? "Firm details" : "Address details", "Review"];
  const phoneE164 = `+91${draft.mobile}`;

  const updateDraft = (patch: Partial<OnboardDraft>) => setDraft((current) => ({ ...current, ...patch }));
  const shouldShow = (invalid: boolean) => showErrors && invalid;
  const canOpenStep = (step: StepId) => step === 0 || (step === 1 && typeDone) || (step === 2 && typeDone && userStepDone) || (step === 3 && formComplete);
  const openStep = (step: StepId) => {
    if (canOpenStep(step)) setCurrentStep(step);
  };
  const resetForNewIntent = () => {
    setDraft(initialDraft);
    setCurrentStep(0);
    setShowErrors(false);
    setIndustriesRequested(false);
    setSubmitKey(createIdempotencyKey());
    setOtpRequestKey(createIdempotencyKey());
    setOtpVerifyKey(createIdempotencyKey());
    setCandidateId(ulid());
    setSubmittedCandidateId("");
    setStateSearch("");
    setDistrictSearch("");
    setPincodeSearch("");
    setLocationSearch("");
  };
  const resetDocument = (mode: IdMode) => {
    updateDraft({ idMode: mode, gst: "", pan: "", documentLookedUp: false, firm: "", address1: "", address2: "", address3: "", stateId: "", districtId: "", pincode: "", locationId: "", roleRows: [emptyRoleRow()] });
    setIndustriesRequested(false);
    setStateSearch("");
    setDistrictSearch("");
    setPincodeSearch("");
    setLocationSearch("");
  };
  const resetLookupResult = (patch: Partial<OnboardDraft>) => {
    mutations.lookupDocument.reset();
    updateDraft({ ...patch, documentLookedUp: false, firm: "", address1: "", address2: "", address3: "", stateId: "", districtId: "", pincode: "", locationId: "", roleRows: [emptyRoleRow()] });
    setIndustriesRequested(false);
    setStateSearch("");
    setDistrictSearch("");
    setPincodeSearch("");
    setLocationSearch("");
  };
  const selectState = (option: SuggestionOption) => {
    updateDraft({ stateId: option.value, districtId: "", pincode: "", locationId: "" });
    setStateSearch(option.label);
    setDistrictSearch("");
    setPincodeSearch("");
    setLocationSearch("");
  };
  const selectDistrict = (option: SuggestionOption) => {
    updateDraft({ districtId: option.value, pincode: "", locationId: "" });
    setDistrictSearch(option.label);
    setPincodeSearch("");
    setLocationSearch("");
  };
  const selectPincode = (option: SuggestionOption) => {
    updateDraft({ pincode: option.value, locationId: "" });
    setPincodeSearch(option.label);
    setLocationSearch("");
  };
  const selectLocation = (option: SuggestionOption) => {
    updateDraft({ locationId: option.value });
    setLocationSearch(option.label);
  };
  const updateRoleRow = (index: number, updater: (row: RoleRow) => RoleRow) => {
    updateDraft({
      roleRows: draft.roleRows.map((row, rowIndex) => (rowIndex === index ? updater(row) : row)),
    });
  };

  const secondaryOptionsForRow = (
    index: number,
    primaryIndustryId: string,
    currentSecondaryIndustryId: string,
  ): IndustrySecondaryOption[] => {
    const primary = industries.find((item) => item.primary_industry_id === primaryIndustryId);
    if (!primary) return [];
    const usedByOtherRows = new Set(
      draft.roleRows
        .filter(isIndustryRow)
        .filter((_, rowIndex) => rowIndex !== index)
        .map((row) => row.secondaryIndustryId)
        .filter(Boolean),
    );
    return primary.secondaries.filter((secondary) => (
      secondary.secondary_industry_id === currentSecondaryIndustryId
      || !usedByOtherRows.has(secondary.secondary_industry_id)
    ));
  };

  const selectManufacturerForRow = (index: number, option: SuggestionOption) => {
    updateRoleRow(index, () => ({
      kind: "manufacturer",
      manufacturerId: option.value,
      roleId: "",
      manufacturerSearch: option.label,
    }));
  };

  const switchRowToIndustry = (index: number) => {
    setIndustriesRequested(true);
    updateRoleRow(index, () => emptyIndustryRow());
  };

  const switchRowToManufacturer = (index: number) => {
    updateRoleRow(index, () => emptyManufacturerRow());
  };

  const selectPrimaryIndustryForRow = (index: number, primaryIndustryId: string) => {
    updateRoleRow(index, (row) => {
      if (!isIndustryRow(row)) return row;
      const options = secondaryOptionsForRow(index, primaryIndustryId, row.secondaryIndustryId);
      const hasCurrentSecondary = options.some(
        (secondary) => secondary.secondary_industry_id === row.secondaryIndustryId,
      );
      const secondaryIndustryId = hasCurrentSecondary
        ? row.secondaryIndustryId
        : options.length === 1
          ? (options[0]?.secondary_industry_id ?? "")
          : "";
      return { ...row, primaryIndustryId, secondaryIndustryId };
    });
  };

  const selectSecondaryIndustryForRow = (index: number, secondaryIndustryId: string) => {
    updateRoleRow(index, (row) => {
      if (!isIndustryRow(row)) return row;
      return { ...row, secondaryIndustryId };
    });
  };

  const updateIndustryRoleName = (index: number, value: string) => {
    updateRoleRow(index, (row) => {
      if (!isIndustryRow(row)) return row;
      return { ...row, roleName: value.slice(0, 100) };
    });
  };

  const addRoleRow = () => {
    if (hasUnusedManufacturer) {
      updateDraft({ roleRows: [...draft.roleRows, emptyManufacturerRow()] });
      return;
    }
    setIndustriesRequested(true);
    updateDraft({ roleRows: [...draft.roleRows, emptyIndustryRow()] });
  };
  const removeRoleRow = (index: number) => {
    if (draft.roleRows.length <= 1) return;
    updateDraft({ roleRows: draft.roleRows.filter((_, rowIndex) => rowIndex !== index) });
  };
  const goNext = () => {
    if (currentStep === 0 && typeDone) {
      setShowErrors(false);
      setCurrentStep(1);
      return;
    }
    if (currentStep === 1 && userStepDone) {
      setShowErrors(false);
      setCurrentStep(2);
      return;
    }
    if (currentStep === 2 && detailsStepDone) {
      setShowErrors(false);
      setCurrentStep(3);
      return;
    }
    setShowErrors(true);
  };
  const goBack = () => {
    setCurrentStep((step) => (step > 0 ? ((step - 1) as StepId) : step));
  };
  const resetMobileAfterDuplicate = () => {
    updateDraft({
      mobile: "",
      ownerVerified: false,
      challengeId: "",
      verifiedUntil: "",
      otpCode: "",
    });
    setOtpRequestKey(createIdempotencyKey());
    setOtpVerifyKey(createIdempotencyKey());
    mutations.requestOtp.reset();
    mutations.verifyOtp.reset();
    requestAnimationFrame(() => {
      document.getElementById(OWNER_MOBILE_INPUT_ID)?.focus();
    });
  };

  const changeMobile = (value: string) => {
    const next = normalizeMobile(value);
    if (next === draft.mobile) return;
    const restartOtp = draft.ownerVerified || Boolean(draft.challengeId);
    updateDraft({
      mobile: next,
      ownerVerified: false,
      challengeId: "",
      verifiedUntil: "",
      otpCode: "",
    });
    if (restartOtp) {
      setOtpRequestKey(createIdempotencyKey());
      setOtpVerifyKey(createIdempotencyKey());
      mutations.requestOtp.reset();
      mutations.verifyOtp.reset();
    }
  };

  const requestOtp = () => {
    if (!MOBILE_RE.test(draft.mobile) || mutations.requestOtp.isPending) return;
    mutations.requestOtp.mutate({ phoneE164, idempotencyKey: otpRequestKey }, {
      onSuccess: (result) => {
        updateDraft({
          challengeId: result.challenge_id,
          ownerVerified: false,
          verifiedUntil: "",
          otpCode: "",
        });
        setOtpVerifyKey(createIdempotencyKey());
      },
    });
  };
  const requestOtpErrorCode = mutations.requestOtp.error instanceof ApiClientError
    ? mutations.requestOtp.error.code
    : "";
  const isDuplicateOtpError = requestOtpErrorCode === "owner_already_on_humbee"
    || requestOtpErrorCode === "candidate_already_captured";

  const verifyOtp = () => {
    if (!draft.challengeId || !draft.otpCode || mutations.verifyOtp.isPending) return;
    mutations.verifyOtp.mutate({
      challengeId: draft.challengeId,
      code: draft.otpCode,
      idempotencyKey: otpVerifyKey,
    }, {
      onSuccess: (result) => {
        updateDraft({
          ownerVerified: result.verified,
          verifiedUntil: result.verified_until,
        });
        if (result.verified) setShowErrors(false);
      },
    });
  };

  const lookupDocument = (input: { gstin?: string; pan?: string }) => {
    mutations.lookupDocument.mutate(input, {
      onSuccess: (result) => {
        updateDraft({
          firm: result.firm_name ?? draft.firm,
          gst: result.gstin ?? draft.gst,
          pan: result.pan ?? draft.pan,
          documentLookedUp: true,
          address1: result.address_line_1 ?? draft.address1,
          address2: result.address_line_2 ?? draft.address2,
          stateId: result.state_id ?? draft.stateId,
          districtId: result.district_id ?? draft.districtId,
          pincode: result.pincode ?? draft.pincode,
          locationId: "",
        });
        setStateSearch(result.state_name ?? stateSearch);
        setDistrictSearch(result.district_name ?? districtSearch);
        setPincodeSearch(result.pincode ?? pincodeSearch);
        setLocationSearch("");
        setShowErrors(false);
      },
    });
  };

  const lookupErrorCode = mutations.lookupDocument.error instanceof ApiClientError
    ? mutations.lookupDocument.error.code
    : "";
  const isDuplicateFirm = lookupErrorCode === "firm_already_exists";
  const duplicateFirmMessage = isDuplicateFirm ? errorMessage(mutations.lookupDocument.error) : undefined;

  const captureLocation = async () => {
    setLocationState("capturing");
    try {
      const location = await capabilities.getCurrentLocation();
      const label = await getCurrentLocationLabel(location).catch(() => selectedLocationName || "Captured shop location");
      updateDraft({
        location: {
          latitude: location.latitude,
          longitude: location.longitude,
          label,
          capturedAt: new Date(location.capturedAt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
        },
      });
      setLocationState("idle");
    } catch {
      setLocationState("error");
    }
  };

  const buildCandidateBody = (): SubmitCandidateBody => {
    const companyAddress = {
      address_line_1: draft.address1.trim(),
      address_line_2: draft.address2.trim(),
      address_line_3: draft.address3.trim() || null,
    };
    const companyGstin = draft.gst.trim() || null;
    const pancardNo = draft.pan.trim() || null;
    const primaryIndustryNameById = new Map(
      industries.map((primary) => [primary.primary_industry_id, primary.primary_industry_name]),
    );
    const secondaryIndustryNameById = new Map(
      allSecondaryIndustries.map((secondary) => [
        secondary.secondary_industry_id,
        humanLabel(secondary.secondary_industry) || secondary.secondary_industry,
      ]),
    );
    return {
      id: candidateId,
      challenge_id: draft.challengeId,
      phone_number: phoneE164,
      company_name: isVcp ? draft.firm.trim() : null,
      fullname: draft.name.trim(),
      company_gstin: companyGstin,
      pancard_no: pancardNo,
      date_of_birth: draft.dob || null,
      latitude: draft.location?.latitude ?? null,
      longitude: draft.location?.longitude ?? null,
      registered_address: {
        company_address: companyAddress,
        state_id: draft.stateId,
        state_name: selectedStateName,
        district_id: draft.districtId,
        district_name: selectedDistrictName,
      },
      operational_address: {
        company_address: companyAddress,
        state_id: draft.stateId,
        state_name: selectedStateName,
        district_id: draft.districtId,
        district_name: selectedDistrictName,
        location_id: draft.locationId,
        pincode: draft.pincode,
      },
      roles: completeManufacturerRows.map((row) => ({
        manufacturer_id: row.manufacturerId,
        firm_role_id: row.roleId,
      })),
      industries: completeIndustryRows.map((row) => ({
        primary_industry_id: row.primaryIndustryId,
        primary_industry_name:
          primaryIndustryNameById.get(row.primaryIndustryId) ?? row.primaryIndustryId,
        secondary_industry_id: row.secondaryIndustryId,
        secondary_industry:
          secondaryIndustryNameById.get(row.secondaryIndustryId) ?? row.secondaryIndustryId,
        role_name: row.roleName.trim(),
      })),
    } as SubmitCandidateBody;
  };

  const submitCandidate = () => {
    if (!formComplete || mutations.submitCandidate.isPending) {
      setShowErrors(true);
      return;
    }
    mutations.submitCandidate.mutate({ body: buildCandidateBody(), idempotencyKey: submitKey }, {
      onSuccess: (candidate) => {
        setSubmittedCandidateId(candidate.id);
      },
    });
  };

  if (statesQuery.isError && rolesQuery.isError) {
    return (
      <SpScreen title="Onboard Buyer" back offline={!isOnline}>
        <ErrorState
          title="Onboarding unavailable"
          message="Address and manufacturer-role options could not be loaded."
          onRetry={() => {
            void statesQuery.refetch();
            void rolesQuery.refetch();
          }}
        />
      </SpScreen>
    );
  }

  return (
    <SpScreen title="Onboard Buyer" back offline={!isOnline}>
      <div className="sp-content">
        <SpInlineAlert>
          New outlets are submitted for manager approval.
        </SpInlineAlert>

        <SpProcessProgress
          steps={stepLabels}
          activeStep={currentStep}
          showCurrentLabel={true}
          onStepSelect={(step) => openStep(step as StepId)}
          canSelectStep={(step) => canOpenStep(step as StepId)}
        />

        {submittedCandidateId ? (
          <SpCard>
            <div className="sp-stack">
              <div className="sp-row" style={{ alignItems: "flex-start", justifyContent: "flex-start" }}>
                <Icon name="CheckCircle" size={24} color="var(--color-success)" />
                <div>
                  <h2 className="sp-title" style={{ margin: 0 }}>Sent for approval</h2>
                  <p className="sp-copy" style={{ marginTop: "var(--space-xs)" }}>
                    Your manager will review this onboarding request before the firm is created in Humbee.
                  </p>
                </div>
              </div>
              <div
                style={{
                  background: "var(--color-warning-surface)",
                  border: "solid var(--color-warning)",
                  borderRadius: "var(--radius-md)",
                  borderWidth: "thin",
                  display: "grid",
                  gap: "var(--space-xs)",
                  padding: "var(--space-sm)",
                }}
              >
                <div>
                  <span className="sp-meta">Approval status</span>
                  <strong style={{ color: "var(--color-warning)", display: "block", marginTop: "var(--space-2xs)" }}>
                    Pending manager approval
                  </strong>
                </div>
                <div>
                  <span className="sp-meta">Candidate ID</span>
                  <code className="sp-meta" style={{ color: "var(--color-text-primary)", display: "block", marginTop: "var(--space-2xs)", overflowWrap: "anywhere" }}>
                    {submittedCandidateId}
                  </code>
                </div>
              </div>
              <div className="sp-grid" style={{ gridTemplateColumns: "1fr" }}>
                <Button color="primary" label="View my requests" onClick={() => router.push("/sp/more/requests")} style={{ width: "100%" }} variant="filled" />
                <Button color="neutral" label="Onboard another" onClick={resetForNewIntent} style={{ width: "100%" }} variant="outlined" />
              </div>
            </div>
          </SpCard>
        ) : null}

        {!submittedCandidateId && currentStep === 0 ? (
          <SpCard>
            <div className="sp-stack">
              <SpSectionLabel>Select buyer type</SpSectionLabel>
              <p className="sp-copy">Choose the role family that will be sent to the manufacturer-role picker.</p>
              <div className="sp-buyer-type-grid">
                <BuyerTypeOption
                  active={draft.buyerType === "VCP"}
                  description="Firm or shop that trades through a manufacturer role."
                  icon="InventoryOutlined"
                  label="VCP"
                  onClick={() => {
                    setIndustriesRequested(false);
                    updateDraft({ buyerType: "VCP", roleRows: [emptyRoleRow()] });
                  }}
                />
                <BuyerTypeOption
                  active={draft.buyerType === "Influencer"}
                  description="Individual buyer profile with influencer roles."
                  icon="PersonRounded"
                  label="Influencer"
                  onClick={() => {
                    setIndustriesRequested(false);
                    updateDraft({ buyerType: "Influencer", roleRows: [emptyRoleRow()] });
                  }}
                />
              </div>
              {shouldShow(!typeDone) ? <SpInlineAlert tone="error">Select VCP or Influencer to continue.</SpInlineAlert> : null}
            </div>
          </SpCard>
        ) : null}

        {!submittedCandidateId && currentStep === 1 ? (
          <SpCard>
            <div className="sp-stack">
              <SpSectionLabel>User details</SpSectionLabel>
              <TextField
                error={shouldShow(!draft.name.trim())}
                helperText={shouldShow(!draft.name.trim()) ? "Enter the name." : undefined}
                label={requiredMark("Name")}
                onChange={(event) => updateDraft({ name: inputValue(event) })}
                placeholder="Enter full name"
                value={draft.name}
              />
              <TextField
                error={shouldShow(!MOBILE_RE.test(draft.mobile))}
                helperText={draft.ownerVerified ? "Mobile number verified." : shouldShow(!MOBILE_RE.test(draft.mobile)) ? "Enter a valid 10-digit Indian mobile number." : ""}
                inputProps={{ id: OWNER_MOBILE_INPUT_ID }}
                label={requiredMark("Mobile number")}
                onChange={(event) => changeMobile(inputValue(event))}
                placeholder="Enter mobile number"
                startAdornment={<span className="sp-copy">+91</span>}
                endAdornment={draft.ownerVerified ? <Icon name="CheckCircle" size={20} color="var(--color-success)" /> : undefined}
                value={draft.mobile}
              />
              {!draft.ownerVerified ?
              <Button
                color="primary"
                disabled={!writesEnabled || !MOBILE_RE.test(draft.mobile) || mutations.requestOtp.isPending}
                label={draft.challengeId ? "Resend OTP" : "Send OTP"}
                loading={mutations.requestOtp.isPending}
                onClick={requestOtp}
                variant="outlined"
              />
              : null}
              {mutations.requestOtp.isError ? (
                <SpInlineAlert tone="error">
                  {isDuplicateOtpError ? (
                    <>
                      {requestOtpErrorCode === "owner_already_on_humbee"
                        ? "This number already has a Humbee account."
                        : "This owner number is already being onboarded."}
                      {" "}
                      <button
                        onClick={resetMobileAfterDuplicate}
                        style={{
                          background: "transparent",
                          border: 0,
                          color: "inherit",
                          cursor: "pointer",
                          font: "inherit",
                          padding: 0,
                          textDecoration: "underline",
                        }}
                        type="button"
                      >
                        Change number
                      </button>
                    </>
                  ) : (
                    errorMessage(mutations.requestOtp.error, "OTP could not be sent.")
                  )}
                </SpInlineAlert>
              ) : null}
              {draft.challengeId && !draft.ownerVerified ? (
                <>
                  <TextField
                    error={shouldShow(!draft.otpCode)}
                    helperText={shouldShow(!draft.otpCode) ? "Enter the OTP sent to the mobile number." : undefined}
                    label={requiredMark("OTP")}
                    onChange={(event) => updateDraft({ otpCode: normalizeOtp(inputValue(event)) })}
                    placeholder="Enter OTP"
                    value={draft.otpCode}
                  />
                  {!draft.ownerVerified ?
                  <Button
                    color="primary"
                    disabled={!writesEnabled || !draft.otpCode || mutations.verifyOtp.isPending}
                    label="Verify OTP"
                    loading={mutations.verifyOtp.isPending}
                    onClick={verifyOtp}
                    variant="filled"
                  />
                  : null}
                  {mutations.verifyOtp.isError ? <SpInlineAlert tone="error">{errorMessage(mutations.verifyOtp.error, "OTP could not be verified.")}</SpInlineAlert> : null}
                </>
              ) : null}
              {!writesEnabled ? <SpInlineAlert tone="warning">Connect to the internet before requesting or verifying OTP.</SpInlineAlert> : null}

              <label className="sp-field-label" style={{ margin: 0 }}>
                Date of birth
                <input
                  max={maxDobValue()}
                  onChange={(event) => updateDraft({ dob: event.currentTarget.value })}
                  style={{
                    background: "var(--surface-card)",
                    border: `solid ${shouldShow(!isDobValid(draft.dob)) ? "var(--color-error)" : "var(--color-border)"}`,
                    borderRadius: "var(--radius-md)",
                    borderWidth: "thin",
                    color: "var(--color-text-primary)",
                    display: "block",
                    font: "inherit",
                    marginTop: "var(--space-xs)",
                    minHeight: "var(--space-xl)",
                    padding: "var(--space-sm) var(--space-md)",
                    width: "100%",
                  }}
                  type="date"
                  value={draft.dob}
                />
              </label>
              {shouldShow(!isDobValid(draft.dob)) ? (
                <SpInlineAlert tone="error">{`Owner must be at least ${MIN_OWNER_AGE_YEARS} years old.`}</SpInlineAlert>
              ) : null}
            </div>
          </SpCard>
        ) : null}

        {!submittedCandidateId && currentStep === 2 ? (
          <>
            {isVcp ? (
              <SpCard>
                <div className="sp-stack">
                  <SpSectionLabel>Business information</SpSectionLabel>
                  <p className="sp-copy">Enter GSTIN or PAN and the firm details fill in automatically.</p>
                  <ChipGroup
                    options={["GST", "PAN"]}
                    selected={(value) => draft.idMode === value}
                    onToggle={(value) => resetDocument(value as IdMode)}
                  />
                  {draft.idMode === "GST" ? (
                    <TextField
                      error={isDuplicateFirm || shouldShow(!GST_RE.test(draft.gst))}
                      helperText={duplicateFirmMessage ?? (shouldShow(!GST_RE.test(draft.gst)) ? "Enter a valid 15-character GSTIN." : undefined)}
                      label={requiredMark("GSTIN")}
                      onChange={(event) => {
                        const gst = normalizeUpper(inputValue(event), 15);
                        resetLookupResult({ gst });
                        if (writesEnabled && GST_RE.test(gst)) lookupDocument({ gstin: gst });
                      }}
                      placeholder="Enter GSTIN"
                      value={draft.gst}
                    />
                  ) : (
                    <TextField
                      error={isDuplicateFirm || shouldShow(!PAN_RE.test(draft.pan))}
                      helperText={duplicateFirmMessage ?? (shouldShow(!PAN_RE.test(draft.pan)) ? "Enter a valid 10-character PAN." : undefined)}
                      label={requiredMark("PAN")}
                      onChange={(event) => {
                        const pan = normalizeUpper(inputValue(event), 10);
                        resetLookupResult({ pan });
                        if (writesEnabled && PAN_RE.test(pan)) lookupDocument({ pan });
                      }}
                      placeholder="Enter PAN"
                      value={draft.pan}
                    />
                  )}
                  <Button
                    color="primary"
                    disabled={!writesEnabled || !identityDone || mutations.lookupDocument.isPending || draft.documentLookedUp || isDuplicateFirm}
                    label={draft.documentLookedUp ? "Document loaded" : "Look up document"}
                    loading={mutations.lookupDocument.isPending}
                    onClick={() => lookupDocument(draft.idMode === "GST" ? { gstin: draft.gst } : { pan: draft.pan })}
                    variant="filled"
                  />
                  {mutations.lookupDocument.isError && !isDuplicateFirm ? <SpInlineAlert tone="error">{errorMessage(mutations.lookupDocument.error, "Document details could not be loaded. Check the document and try again.")}</SpInlineAlert> : null}
                  {!writesEnabled ? <SpInlineAlert tone="warning">Connect to the internet before document lookup.</SpInlineAlert> : null}
                  <TextField
                    disabled={!draft.documentLookedUp}
                    error={shouldShow(draft.documentLookedUp && !draft.firm.trim())}
                    helperText={!draft.documentLookedUp ? "Look up the document first." : shouldShow(!draft.firm.trim()) ? "Enter the firm name." : undefined}
                    label={requiredMark("Firm name")}
                    onChange={(event) => updateDraft({ firm: inputValue(event) })}
                    placeholder="Enter firm name"
                    value={draft.firm}
                  />
                </div>
              </SpCard>
            ) : null}

            <SpCard style={{ overflow: "visible" }}>
              <div className="sp-stack">
                <SpSectionLabel>{isVcp ? "Firm address" : "Influencer address"}</SpSectionLabel>
                <TextField
                  error={shouldShow(!draft.address1.trim())}
                  helperText={shouldShow(!draft.address1.trim()) ? "Enter address line 1." : undefined}
                  label={requiredMark("Address line 1")}
                  onChange={(event) => updateDraft({ address1: inputValue(event) })}
                  placeholder="Shop / building no."
                  value={draft.address1}
                />
                <TextField
                  error={shouldShow(!draft.address2.trim())}
                  helperText={shouldShow(!draft.address2.trim()) ? "Enter address line 2." : undefined}
                  label={requiredMark("Address line 2")}
                  onChange={(event) => updateDraft({ address2: inputValue(event) })}
                  placeholder="Street / locality"
                  value={draft.address2}
                />
                <TextField
                  label="Address line 3"
                  onChange={(event) => updateDraft({ address3: inputValue(event) })}
                  placeholder="Landmark"
                  value={draft.address3}
                />
                {statesQuery.isError ? <SpInlineAlert tone="error">Address states could not be loaded. Retry from this screen.</SpInlineAlert> : null}
                <SuggestionField
                  disabled={statesQuery.isPending}
                  error={shouldShow(!draft.stateId)}
                  helperText={shouldShow(!draft.stateId) ? "Select a state from suggestions." : undefined}
                  label={requiredMark("State")}
                  onQueryChange={(value) => {
                    setStateSearch(value);
                    updateDraft({ stateId: "", districtId: "", pincode: "", locationId: "" });
                    setDistrictSearch("");
                    setPincodeSearch("");
                  }}
                  onSelect={selectState}
                  options={stateSuggestions}
                  placeholder="Search state"
                  query={stateSearch}
                />
                <SuggestionField
                  disabled={!draft.stateId}
                  error={shouldShow(!draft.districtId && Boolean(draft.stateId))}
                  helperText={shouldShow(!draft.districtId && Boolean(draft.stateId)) ? "Select a district from suggestions." : !draft.stateId ? "Select a state first" : undefined}
                  label={requiredMark("District")}
                  onQueryChange={(value) => {
                    setDistrictSearch(value);
                    updateDraft({ districtId: "", pincode: "", locationId: "" });
                    setPincodeSearch("");
                  }}
                  onSelect={selectDistrict}
                  options={districtSuggestions}
                  placeholder={draft.stateId ? "Search district" : "Select a state first"}
                  query={districtSearch}
                />
                {districtsQuery.isError ? <SpInlineAlert tone="error">Districts could not be loaded for this state.</SpInlineAlert> : null}
                <SuggestionField
                  disabled={!draft.districtId}
                  error={shouldShow(draft.pincode.length !== 6 && Boolean(draft.districtId))}
                  helperText={shouldShow(draft.pincode.length !== 6 && Boolean(draft.districtId)) ? "Enter a valid 6-digit pincode." : !draft.districtId ? "Select a district first" : ""}
                  label={requiredMark("Pincode")}
                  onQueryChange={(value) => {
                    const pincode = normalizePincode(value);
                    setPincodeSearch(pincode);
                    updateDraft({ pincode, locationId: "" });
                    setLocationSearch("");
                  }}
                  onSelect={selectPincode}
                  options={pincodeSuggestions}
                  placeholder={draft.districtId ? "Search or enter pincode" : "Select a district first"}
                  query={pincodeSearch}
                />
                <SuggestionField
                  disabled={!draft.districtId}
                  error={shouldShow(!draft.locationId && Boolean(draft.districtId))}
                  helperText={shouldShow(!draft.locationId && Boolean(draft.districtId)) ? "Select a city." : !draft.districtId ? "Select a district first" : undefined}
                  label={requiredMark("City")}
                  onQueryChange={(value) => {
                    setLocationSearch(value);
                    updateDraft({ locationId: "" });
                  }}
                  onSelect={selectLocation}
                  options={locationSuggestions}
                  placeholder={draft.districtId ? "Search city" : "Select a district first"}
                  query={locationSearch}
                />
                {optionsQuery.isError ? <SpInlineAlert tone="warning">City and pincode options could not be loaded. Retry after checking the district and pincode.</SpInlineAlert> : null}
                {draft.districtId && !optionsQuery.isPending && !locationOptions.length ? (
                  <EmptyState icon="LocationPin" title="No cities returned" message="Try a different pincode, or clear the pincode and reload district options." />
                ) : null}

                <SpSectionLabel>{isVcp ? "Manufacturers and VCP roles" : "Manufacturers and influencer roles"}</SpSectionLabel>
                {rolesQuery.isError ? <SpInlineAlert tone="error">Manufacturer roles could not be loaded.</SpInlineAlert> : null}
                {industriesRequested && industriesQuery.isError ? <SpInlineAlert tone="error">Industries could not be loaded.</SpInlineAlert> : null}
                {draft.roleRows.map((row, index) => {
                  return (
                    <div
                      key={index}
                      style={{
                        background: "var(--surface-card)",
                        border: "solid var(--color-neutral-300)",
                        borderRadius: "var(--radius-md)",
                        borderWidth: "thin",
                        display: "grid",
                        gap: "var(--space-sm)",
                        padding: "var(--space-sm)",
                        position: "relative",
                      }}
                    >
                      <span className="sp-meta" style={{ textTransform: "uppercase" }}>Association {index + 1}</span>
                      {draft.roleRows.length > 1 ? (
                        <Button
                          color="neutral"
                          label="Remove"
                          onClick={() => removeRoleRow(index)}
                          size="small"
                          style={{ position: "absolute", right: "var(--space-sm)", top: "var(--space-sm)" }}
                          variant="text"
                        />
                      ) : null}
                      {isManufacturerRow(row) ? (
                        <>
                          <SuggestionField
                            disabled={rolesQuery.isPending}
                            error={shouldShow(!row.manufacturerId)}
                            helperText={rolesQuery.isPending ? "Loading manufacturers..." : shouldShow(!row.manufacturerId) ? "Select a manufacturer." : undefined}
                            label={requiredMark("Manufacturer")}
                            onQueryChange={(value) => updateRoleRow(index, () => ({
                              kind: "manufacturer",
                              manufacturerId: "",
                              roleId: "",
                              manufacturerSearch: value,
                            }))}
                            onSelect={(option) => selectManufacturerForRow(index, option)}
                            options={manufacturersWithRoles
                              .filter((manufacturer) => (
                                !usedManufacturerIds.has(manufacturer.manufacturer_id)
                                || manufacturer.manufacturer_id === row.manufacturerId
                              ))
                              .map((manufacturer) => ({ label: manufacturer.name, value: manufacturer.manufacturer_id }))}
                            placeholder={rolesQuery.isPending ? "Loading..." : "Search manufacturer"}
                            query={row.manufacturerSearch}
                          />
                          <Select
                            disabled={!row.manufacturerId}
                            error={shouldShow(!row.roleId)}
                            fullWidth
                            helperText={shouldShow(!row.roleId) ? "Select a role." : !row.manufacturerId ? "Select a manufacturer first" : undefined}
                            label={requiredMark(isVcp ? "VCP role" : "Influencer role")}
                            onChange={(value) => updateRoleRow(index, (currentRow) => (
                              isManufacturerRow(currentRow) ? { ...currentRow, roleId: value } : currentRow
                            ))}
                            options={roleOptionsFor(row.manufacturerId).map((role) => ({ label: role.role_name, value: role.role_id }))}
                            placeholder="Role"
                            value={row.roleId}
                          />
                          <LinkButton onClick={() => switchRowToIndustry(index)}>
                            Manufacturer not on Humbee? Choose industry
                          </LinkButton>
                        </>
                      ) : (
                        <>
                          <Select
                            error={shouldShow(!row.primaryIndustryId)}
                            fullWidth
                            helperText={shouldShow(!row.primaryIndustryId) ? "Select a primary industry." : undefined}
                            label={requiredMark("Primary industry")}
                            onChange={(value) => selectPrimaryIndustryForRow(index, value)}
                            options={industries.map((industry) => ({
                              label: industry.primary_industry_name,
                              value: industry.primary_industry_id,
                            }))}
                            placeholder={industriesQuery.isPending ? "Loading..." : "Primary industry"}
                            value={row.primaryIndustryId}
                          />
                          <Select
                            disabled={!row.primaryIndustryId}
                            error={shouldShow(!row.secondaryIndustryId)}
                            fullWidth
                            helperText={shouldShow(!row.secondaryIndustryId) ? "Select a secondary industry." : !row.primaryIndustryId ? "Select a primary industry first" : undefined}
                            label={requiredMark("Secondary industry")}
                            onChange={(value) => selectSecondaryIndustryForRow(index, value)}
                            options={secondaryOptionsForRow(
                              index,
                              row.primaryIndustryId,
                              row.secondaryIndustryId,
                            ).map((industry) => ({
                              label: humanLabel(industry.secondary_industry) || industry.secondary_industry,
                              value: industry.secondary_industry_id,
                            }))}
                            placeholder="Secondary industry"
                            value={row.secondaryIndustryId}
                          />
                          <TextField
                            error={shouldShow(!row.roleName.trim())}
                            helperText={shouldShow(!row.roleName.trim()) ? "Enter your role for this industry." : undefined}
                            label={requiredMark("Your role")}
                            onChange={(event) => updateIndustryRoleName(index, inputValue(event))}
                            placeholder="Enter your role"
                            value={row.roleName}
                          />
                          <LinkButton onClick={() => switchRowToManufacturer(index)}>
                            Search manufacturers instead
                          </LinkButton>
                        </>
                      )}
                    </div>
                  );
                })}
                {canAddAssociation ? (
                  <Button
                    color="primary"
                    label="+ Add association"
                    onClick={addRoleRow}
                    variant="text"
                  />
                ) : null}

                {isVcp ? (
                  <>
                    <SpSectionLabel>Shop location</SpSectionLabel>
                    <div className="sp-stack">
                      <div
                        style={{
                          background: draft.location ? "var(--color-success-surface)" : "var(--surface-card)",
                          border: `1px solid ${draft.location ? "var(--color-success)" : "var(--color-neutral-300)"}`,
                          borderRadius: "var(--radius-md)",
                          padding: "var(--space-sm)",
                        }}
                      >
                        <div className="sp-row" style={{ alignItems: "center", gap: "var(--space-xs)" }}>
                          <div className="sp-row" style={{ flex: 1, gap: "var(--space-xs)", justifyContent: "flex-start" }}>
                            <Icon name="LocationMarker" size={18} color={draft.location ? "var(--color-success)" : "var(--color-primary)"} />
                            <div>
                              <strong className="sp-body-strong--sm">{locationState === "capturing" ? "Capturing location..." : draft.location ? "Location captured" : "Shop location not captured"}</strong>
                              <p className="sp-meta" style={{ margin: "var(--space-2xs) 0 0" }}>
                                {draft.location ? `${draft.location.label} · ${draft.location.capturedAt}` : "Stand at the shop entrance before capturing."}
                              </p>
                            </div>
                          </div>
                          <Button
                            color="primary"
                            label={draft.location ? "Re-capture" : "Capture"}
                            loading={locationState === "capturing"}
                            onClick={() => void captureLocation()}
                            size="small"
                            variant="text"
                          />
                        </div>
                      </div>
                      {locationState === "error" ? <SpInlineAlert tone="error">Location permission failed or timed out. Retry after enabling GPS permission.</SpInlineAlert> : null}
                    </div>
                  </>
                ) : null}
            </div>
          </SpCard>
          </>
        ) : null}

        {!submittedCandidateId && currentStep === 3 ? (
          <section>
            <div className="sp-row" style={{ justifyContent: "flex-start", marginBottom: "var(--space-md)" }}>
              <span className="sp-section-label" style={{ margin: 0 }}>Review</span>
            </div>
            <SpCard>
              <div className="sp-stack">
                <SpStatusRow label="Buyer type" value={draft.buyerType} />
                <SpStatusRow label="Name" value={draft.name || "-"} />
                <SpStatusRow label="Mobile number" value={draft.mobile ? `+91 ${draft.mobile}` : "-"} />
                <SpStatusRow label="Phone verification" value={draft.ownerVerified ? "Verified" : "Not verified"} tone={draft.ownerVerified ? "var(--color-success)" : "var(--color-error)"} />
                {draft.dob ? <SpStatusRow label="Date of birth" value={draft.dob} /> : null}
                {isVcp ? <SpStatusRow label={draft.idMode} value={selectedDocument(draft) || "-"} /> : null}
                {isVcp ? <SpStatusRow label="Firm name" value={draft.firm || "-"} /> : null}
                <SpStatusRow
                  label="Address"
                  value={[
                    [draft.address1, draft.address2, draft.address3].filter(Boolean).join(", "),
                    [selectedLocationName, selectedDistrictName].filter(Boolean).join(", "),
                    [selectedStateName, draft.pincode].filter(Boolean).join(" "),
                  ].filter(Boolean).join(" · ") || "-"}
                />
                {completeRoleRows.map((row, index) => {
                  if (isManufacturerRow(row)) {
                    const manufacturer = manufacturers.find((item) => item.manufacturer_id === row.manufacturerId);
                    const role = roleOptionsFor(row.manufacturerId).find((item) => item.role_id === row.roleId);
                    return (
                      <SpStatusRow
                        key={`${row.kind}-${row.manufacturerId}-${row.roleId}-${index}`}
                        label={`Association ${index + 1}`}
                        value={[manufacturer?.name, role?.role_name].filter(Boolean).join(" - ") || "-"}
                      />
                    );
                  }
                  const primary = industries.find(
                    (industry) => industry.primary_industry_id === row.primaryIndustryId,
                  );
                  const secondary = primary?.secondaries.find(
                    (industry) => industry.secondary_industry_id === row.secondaryIndustryId,
                  );
                  return (
                    <SpStatusRow
                      key={`${row.kind}-${row.primaryIndustryId}-${row.secondaryIndustryId}-${index}`}
                      label={`Association ${index + 1}`}
                      value={[
                        [
                          primary?.primary_industry_name ?? row.primaryIndustryId,
                          secondary
                            ? (humanLabel(secondary.secondary_industry) || secondary.secondary_industry)
                            : row.secondaryIndustryId,
                        ].join(" > "),
                        row.roleName.trim(),
                      ].filter(Boolean).join(" - ") || "-"}
                    />
                  );
                })}
                {isVcp ? <SpStatusRow label="GPS" value={draft.location?.label ?? "-"} /> : null}
              </div>
            </SpCard>
            {mutations.submitCandidate.isError ? (
              <div style={{ marginTop: "var(--space-md)" }}>
                <SpInlineAlert tone="error">{errorMessage(mutations.submitCandidate.error, "Onboarding request could not be submitted.")}</SpInlineAlert>
              </div>
            ) : null}
            {!writesEnabled ? (
              <div style={{ marginTop: "var(--space-md)" }}>
                <SpInlineAlert tone="warning">Connect to the internet before submitting this request.</SpInlineAlert>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>

      {!submittedCandidateId ? (
        <SpStickyFooter>
          <div className="sp-row">
            {currentStep > 0 ? (
              <Button
                color="neutral"
                label="Back"
                onClick={goBack}
                style={{ flex: 1 }}
                variant="outlined"
              />
            ) : null}
            <Button
              color="primary"
              disabled={primaryActionDisabled}
              label={currentStep === 3 ? "Send for approval" : "Next"}
              loading={currentStep === 3 && mutations.submitCandidate.isPending}
              onClick={currentStep === 3 ? submitCandidate : goNext}
              style={{ flex: 1 }}
              variant="filled"
            />
          </div>
        </SpStickyFooter>
      ) : null}
    </SpScreen>
  );
}
