type MaybeText = string | null | undefined;

type OutletSortMode = "name" | "location_then_name";

export interface OutletListItem {
  id?: string;
  name: string;
  location?: MaybeText;
  category?: MaybeText;
  takenBy?: MaybeText;
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
    [outlet.name, outlet.location, outlet.category, outlet.takenBy]
      .filter((value): value is string => Boolean(value))
      .join(" ")
      .toLocaleLowerCase()
      .includes(normalizedQuery)
  ));
}
