import type { BeatOutletItem, ScopeOutletItem } from "@humbee/api-contract";

type MaybeText = string | null | undefined;

type OutletSortMode = "name" | "location_then_name";

export interface OutletListItem {
  id?: string;
  name: string;
  location?: MaybeText;
  category?: MaybeText;
  takenBy?: MaybeText;
  gstinPan?: MaybeText;
  district?: MaybeText;
  manufacturers?: readonly string[];
}

/** Fields that tell apart outlets sharing a name in the same district. */
export interface OutletIdentityFields {
  gstinPan: string;
  district: string;
  manufacturers: string[];
}

// Not in the generated beat outlet contract yet; read defensively until the API ships them.
type PendingOutletIdentity = {
  gstin_pan?: string | null;
  district_name?: string | null;
  manufacturer_names?: string | null;
};

export function outletIdentity(outlet: ScopeOutletItem | BeatOutletItem): OutletIdentityFields {
  const fields = outlet as (ScopeOutletItem | BeatOutletItem) & PendingOutletIdentity;
  return {
    gstinPan: textValue(fields.gstin_pan),
    district: textValue(fields.district_name),
    manufacturers: [...new Set((fields.manufacturer_names ?? "").split(",").map((name) => name.trim()).filter(Boolean))],
  };
}

function textValue(value: MaybeText) {
  return (value ?? "").trim();
}

function compareText(left: MaybeText, right: MaybeText) {
  return textValue(left).localeCompare(textValue(right), undefined, { sensitivity: "base", numeric: true });
}

export function sortOutletsTakenLast<T extends OutletListItem>(outlets: readonly T[], mode: OutletSortMode = "name"): T[] {
  return [...outlets].sort((left, right) => {
    const leftTaken = Boolean(left.takenBy);
    const rightTaken = Boolean(right.takenBy);
    if (leftTaken !== rightTaken) return leftTaken ? 1 : -1;
    if (mode === "location_then_name") {
      const locationCompare = compareText(left.location, right.location);
      if (locationCompare !== 0) return locationCompare;
    }
    const nameCompare = compareText(left.name, right.name);
    if (nameCompare !== 0) return nameCompare;
    const categoryCompare = compareText(left.category, right.category);
    if (categoryCompare !== 0) return categoryCompare;
    return compareText(left.id, right.id);
  });
}

export function filterOutletsByQuery<T extends OutletListItem>(outlets: readonly T[], query: string): T[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  if (!normalizedQuery) return [...outlets];
  return outlets.filter((outlet) => (
    [outlet.name, outlet.location, outlet.category, outlet.takenBy, outlet.gstinPan, outlet.district, ...(outlet.manufacturers ?? [])]
      .filter((value): value is string => Boolean(value))
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalizedQuery)
  ));
}
