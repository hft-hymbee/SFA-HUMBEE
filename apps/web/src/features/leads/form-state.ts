import type { CaptureLeadBody } from "@humbee/api-contract";

export interface LeadFormDraft {
  name: string;
  designation: string;
  mobile: string;
  email: string;
  companyName: string;
  annualTurnoverCr: string;
  headOfficeLocation: string;
  message: string;
}

export interface LeadFormErrors {
  name?: string;
  mobile?: string;
  email?: string;
  designation?: string;
  companyName?: string;
  annualTurnoverCr?: string;
}

const MOBILE_PATTERN = /^\+91\d{10}$/;
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const MAX_NAME_LENGTH = 120;

export function createEmptyLeadDraft(): LeadFormDraft {
  return {
    annualTurnoverCr: "",
    companyName: "",
    designation: "",
    email: "",
    headOfficeLocation: "",
    message: "",
    mobile: "",
    name: "",
  };
}

export function normaliseMobile(value: string): string {
  const digits = value.replace(/\D/g, "").slice(-10);
  return digits.length === 10 ? `+91${digits}` : value.trim();
}

export function parsePositiveTurnover(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return parsed > 0 ? parsed : null;
}

export function validateLeadDraft(draft: LeadFormDraft): LeadFormErrors {
  const errors: LeadFormErrors = {};
  if (draft.name.trim().length < 2) {
    errors.name = "Enter the lead's full name.";
  }
  if (draft.designation.trim().length > MAX_NAME_LENGTH) {
    errors.designation = `Keep the designation under ${MAX_NAME_LENGTH} characters.`;
  }
  if (!MOBILE_PATTERN.test(normaliseMobile(draft.mobile))) {
    errors.mobile = "Enter a valid 10-digit mobile number.";
  }
  if (!EMAIL_PATTERN.test(draft.email.trim())) {
    errors.email = "Enter a valid email address.";
  }
  const companyName = draft.companyName.trim();
  if (companyName.length < 2) {
    errors.companyName = "Enter the manufacturer's name.";
  } else if (companyName.length > MAX_NAME_LENGTH) {
    errors.companyName = `Keep the name under ${MAX_NAME_LENGTH} characters.`;
  }
  if (draft.annualTurnoverCr.trim() && parsePositiveTurnover(draft.annualTurnoverCr) === null) {
    errors.annualTurnoverCr = "Enter a turnover greater than zero.";
  }
  return errors;
}

export function buildCaptureLeadBody(draft: LeadFormDraft, id: string): CaptureLeadBody {
  const companyName = draft.companyName.trim();
  return {
    id,
    annual_turnover_cr: parsePositiveTurnover(draft.annualTurnoverCr),
    company_name: companyName,
    designation: draft.designation.trim() || null,
    email: draft.email.trim(),
    head_office_location: draft.headOfficeLocation.trim() || null,
    message: draft.message.trim() || null,
    mobile: normaliseMobile(draft.mobile),
    name: draft.name.trim(),
  };
}
