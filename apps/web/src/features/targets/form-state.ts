import { ulid } from "ulid";
import type {
  CreateTargetBody,
  ManufacturerOut,
  OutletCategoryScope,
  TargetBasis,
  TargetLineBody,
  TargetOut,
  TargetType,
  UpdateTargetBody,
} from "./service";
import { manufacturerBasis, manufacturerUnitLabel } from "./service";

export interface SalesLineDraft {
  manufacturerId: string;
  manufacturerLabel: string;
  basis: TargetBasis;
  unitLabel: string;
  value: string;
  selected: boolean;
}

export interface TargetFormDraft {
  employeeId: string;
  periodMonth: string;
  targetType: TargetType;
  outletTargetValue: string;
  leadTargetValue: string;
  outletCategoryScope: OutletCategoryScope;
  salesLines: SalesLineDraft[];
}

export interface TargetFormErrors {
  employeeId?: string;
  periodMonth?: string;
  targetValue?: string;
  salesLines?: string;
}

export interface SalesTargetTotals {
  amountPaise: number | null;
  volumeUnits: number | null;
  selectedCount: number;
  totalCount: number;
}

export const TARGET_TYPE_OPTIONS: Array<{ label: string; value: TargetType; description: string }> = [
  {
    description: "Amount or volume, per manufacturer.",
    label: "Sales target",
    value: "sales",
  },
  {
    description: "Count of verified new outlets, MTD.",
    label: "New outlets onboarded",
    value: "outlets",
  },
  {
    description: "Leads to capture in the month.",
    label: "Leads",
    value: "leads",
  },
];

export const OUTLET_CATEGORY_OPTIONS: Array<{ label: string; value: OutletCategoryScope }> = [
  { label: "Any category", value: "any" },
  { label: "Grocery / kirana", value: "grocery" },
  { label: "Wholesale", value: "wholesale" },
  { label: "Chemist", value: "chemist" },
];

export function isTargetType(value: string | null | undefined): value is TargetType {
  return value === "sales" || value === "outlets" || value === "leads";
}

export function createEmptyTargetDraft(
  employeeId: string,
  periodMonth: string,
  manufacturers: ManufacturerOut[] = [],
): TargetFormDraft {
  return {
    employeeId,
    leadTargetValue: "",
    outletCategoryScope: "any",
    outletTargetValue: "",
    periodMonth,
    salesLines: manufacturers.map(manufacturerToLineDraft),
    targetType: "sales",
  };
}

export function targetToDraft(target: TargetOut, manufacturers: ManufacturerOut[] = []): TargetFormDraft {
  const draft = createEmptyTargetDraft(target.employee_id, target.period_month, manufacturers);
  return overlayTargetOntoDraft(draft, target, manufacturers);
}

export function overlayTargetOntoDraft(
  draft: TargetFormDraft,
  target: TargetOut,
  manufacturers: ManufacturerOut[] = [],
): TargetFormDraft {
  if (target.target_type === "sales") {
    return {
      ...draft,
      salesLines: salesLinesFromTarget(target, manufacturers),
    };
  }
  if (target.target_type === "outlets") {
    return {
      ...draft,
      outletCategoryScope: target.outlet_category_scope ?? "any",
      outletTargetValue: target.target_value === null ? "" : String(target.target_value),
    };
  }
  return {
    ...draft,
    leadTargetValue: target.target_value === null ? "" : String(target.target_value),
  };
}

export function draftFromTargets(
  employeeId: string,
  periodMonth: string,
  targetType: TargetType,
  targets: TargetOut[],
  manufacturers: ManufacturerOut[],
): TargetFormDraft {
  let draft = {
    ...createEmptyTargetDraft(employeeId, periodMonth, manufacturers),
    targetType,
  };
  for (const target of targets) {
    draft = overlayTargetOntoDraft(draft, target, manufacturers);
  }
  return draft;
}

export function syncSalesLinesWithManufacturers(
  draft: TargetFormDraft,
  manufacturers: ManufacturerOut[],
): TargetFormDraft {
  const existing = new Map(draft.salesLines.map((line) => [line.manufacturerId, line]));
  return {
    ...draft,
    salesLines: manufacturers.map((manufacturer) =>
      existing.get(manufacturer.manufacturer_id) ?? manufacturerToLineDraft(manufacturer),
    ),
  };
}

export function validateTargetDraft(draft: TargetFormDraft): TargetFormErrors {
  const errors: TargetFormErrors = {};
  if (!draft.employeeId.trim()) {
    errors.employeeId = "Select a person.";
  }
  if (!draft.periodMonth.trim()) {
    errors.periodMonth = "Select a period.";
  }

  if (draft.targetType === "sales") {
    const selected = selectedSalesLines(draft);
    if (!selected.length) {
      errors.salesLines = "Select at least one manufacturer.";
    } else {
      const invalid = selected.find((line) => parsePositiveInteger(line.value) === null);
      if (invalid) {
        errors.salesLines = `Enter a target for ${invalid.manufacturerLabel}.`;
      }
    }
    return errors;
  }

  if (parsePositiveInteger(countValue(draft)) === null) {
    errors.targetValue = "Enter a target greater than zero.";
  }

  return errors;
}

export function hasTargetDraftErrors(errors: TargetFormErrors): boolean {
  return Object.values(errors).some(Boolean);
}

export function buildCreateTargetBody(draft: TargetFormDraft): CreateTargetBody {
  const common = {
    employee_id: draft.employeeId,
    id: ulid(),
    period_month: draft.periodMonth,
    target_type: draft.targetType,
  };

  if (draft.targetType === "sales") {
    return {
      ...common,
      lines: selectedSalesLines(draft).map((line) => toTargetLineBody(line)),
      target_value: null,
    };
  }

  if (draft.targetType === "outlets") {
    return {
      ...common,
      outlet_category_scope: draft.outletCategoryScope,
      target_value: parsePositiveInteger(draft.outletTargetValue),
    };
  }

  return {
    ...common,
    target_value: parsePositiveInteger(draft.leadTargetValue),
  };
}

export function buildUpdateTargetBody(draft: TargetFormDraft, version: number): UpdateTargetBody {
  const created = buildCreateTargetBody(draft);
  const { employee_id: _employeeId, id: _id, period_month: _periodMonth, ...body } = created;
  void _employeeId;
  void _id;
  void _periodMonth;
  return { ...body, version };
}

export function selectedSalesLines(draft: TargetFormDraft): SalesLineDraft[] {
  return draft.salesLines.filter((line) => line.selected);
}

export function salesTargetTotals(draft: TargetFormDraft, manufacturers: ManufacturerOut[]): SalesTargetTotals {
  const selected = selectedSalesLines(draft);
  let amountPaise = 0;
  let volumeUnits = 0;
  let hasAmount = false;
  let hasVolume = false;
  for (const line of selected) {
    const parsed = parsePositiveInteger(line.value);
    if (parsed === null) continue;
    const basis = lineBasis(line);
    if (basis === "amount") {
      hasAmount = true;
      amountPaise += parsed * 100;
    } else if (basis === "volume") {
      hasVolume = true;
      volumeUnits += parsed;
    }
  }
  return {
    amountPaise: hasAmount ? amountPaise : null,
    selectedCount: selected.length,
    totalCount: draft.salesLines.length,
    volumeUnits: hasVolume ? volumeUnits : null,
  };
}

export function parsePositiveInteger(value: string): number | null {
  const trimmed = value.trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export function lineUnitLabel(line: SalesLineDraft): string {
  return line.unitLabel;
}

export function lineBasis(line: SalesLineDraft): TargetBasis {
  return line.basis;
}

function countValue(draft: TargetFormDraft): string {
  return draft.targetType === "outlets" ? draft.outletTargetValue : draft.leadTargetValue;
}

function salesLinesFromTarget(target: TargetOut, manufacturers: ManufacturerOut[]): SalesLineDraft[] {
  const targetLineIds = new Set(target.lines.map((line) => line.manufacturer_id));
  const rosterLines = manufacturers
    .filter((manufacturer) => !targetLineIds.has(manufacturer.manufacturer_id))
    .map(manufacturerToLineDraft);
  const targetLines = target.lines.map((line) => {
    const displayValue = line.line_basis === "amount"
      ? Math.trunc(line.line_value / 100)
      : line.line_value;
    return {
      basis: line.line_basis,
      manufacturerId: line.manufacturer_id,
      manufacturerLabel: line.manufacturer_label,
      selected: true,
      unitLabel: line.uom_label,
      value: String(displayValue),
    };
  });
  return [...targetLines, ...rosterLines];
}

function manufacturerToLineDraft(manufacturer: ManufacturerOut): SalesLineDraft {
  return {
    basis: manufacturerBasis(manufacturer),
    manufacturerId: manufacturer.manufacturer_id,
    manufacturerLabel: manufacturer.display_label,
    selected: false,
    unitLabel: manufacturerUnitLabel(manufacturer),
    value: "",
  };
}

function toTargetLineBody(line: SalesLineDraft): TargetLineBody {
  const parsed = parsePositiveInteger(line.value);
  if (parsed === null) {
    throw new Error(`Invalid target value for manufacturer ${line.manufacturerId}`);
  }
  return {
    line_value: line.basis === "amount" ? parsed * 100 : parsed,
    manufacturer_id: line.manufacturerId,
  };
}
