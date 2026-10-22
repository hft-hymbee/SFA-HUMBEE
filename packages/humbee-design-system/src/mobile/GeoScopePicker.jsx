import React, { useEffect, useMemo, useState } from "react";
import { Button } from "../core/Button.jsx";
import { Icon } from "../core/Icon.jsx";
import { Checkbox } from "../forms/Checkbox.jsx";
import { TextField } from "../forms/TextField.jsx";
import { BottomSheet } from "./Overlays.jsx";

const EMPTY_SCOPE = {
  zones: [],
  states: [],
  districts: [],
  shopCategories: [],
};

const LEVEL_META = {
  zones: {
    icon: "Map",
    label: "Zone",
    hint: "Select one or more zones",
    subtitle: "Top of the geography hierarchy",
  },
  states: {
    icon: "LocationMarker",
    label: "State",
    hint: "Select states inside the chosen zones",
    blockedHint: "Choose a zone first",
    subtitle: "Grouped by zone",
  },
  districts: {
    icon: "LocationPin",
    label: "District",
    hint: "Select districts inside the chosen states",
    blockedHint: "Choose a state first",
    subtitle: "Grouped by state",
  },
  shopCategories: {
    icon: "InventoryOutlined",
    label: "Shop category",
    hint: "All categories if none are selected",
    subtitle: "Filters which outlets enter the scope",
  },
};

function includesAssigned(assigned, level, id) {
  return !assigned?.[level] || assigned[level].includes(id);
}

function allowedIds(options, assigned, level) {
  return new Set(options.filter((option) => includesAssigned(assigned, level, option.id)).map((option) => option.id));
}

function sanitizeScope(scope, data, assigned) {
  const source = { ...EMPTY_SCOPE, ...scope };
  const zoneIds = allowedIds(data.zones, assigned, "zones");
  const zones = source.zones.filter((id) => zoneIds.has(id));

  const stateIds = allowedIds(data.states, assigned, "states");
  const states = source.states.filter((id) => {
    const option = data.states.find((state) => state.id === id);
    return stateIds.has(id) && option && zones.includes(option.zoneId);
  });

  const districtIds = allowedIds(data.districts, assigned, "districts");
  const districts = source.districts.filter((id) => {
    const option = data.districts.find((district) => district.id === id);
    return districtIds.has(id) && option && states.includes(option.stateId);
  });

  const categoryIds = allowedIds(data.shopCategories, assigned, "shopCategories");
  const shopCategories = source.shopCategories.filter((id) => categoryIds.has(id));

  return { zones, states, districts, shopCategories };
}

function scopesEqual(left, right) {
  return Object.keys(EMPTY_SCOPE).every((key) => (
    left[key].length === right[key].length
    && left[key].every((id, index) => id === right[key][index])
  ));
}

function defaultOutletCount(scope, data) {
  const districtTotal = data.districts
    .filter((district) => scope.districts.includes(district.id))
    .reduce((total, district) => total + (district.outletCount || 0), 0);

  if (!scope.shopCategories.length) return districtTotal;

  const selectedCategories = data.shopCategories.filter((category) => scope.shopCategories.includes(category.id));
  const hasShares = selectedCategories.some((category) => typeof category.outletShare === "number");
  if (!hasShares) return districtTotal;

  const share = selectedCategories.reduce((total, category) => total + (category.outletShare || 0), 0);
  return Math.round(districtTotal * Math.min(share, 1));
}

function buildLevelOptions(data, assigned, scope) {
  const zoneNames = new Map(data.zones.map((option) => [option.id, option.label]));
  const stateNames = new Map(data.states.map((option) => [option.id, option.label]));

  return {
    zones: data.zones
      .filter((option) => includesAssigned(assigned, "zones", option.id))
      .map((option) => ({ ...option })),
    states: data.states
      .filter((option) => scope.zones.includes(option.zoneId) && includesAssigned(assigned, "states", option.id))
      .map((option) => ({ ...option, group: zoneNames.get(option.zoneId) })),
    districts: data.districts
      .filter((option) => scope.states.includes(option.stateId) && includesAssigned(assigned, "districts", option.id))
      .map((option) => ({ ...option, group: stateNames.get(option.stateId) })),
    shopCategories: data.shopCategories
      .filter((option) => includesAssigned(assigned, "shopCategories", option.id))
      .map((option) => ({ ...option })),
  };
}

function selectedNames(options, selected) {
  const selectedSet = new Set(selected);
  return options.filter((option) => selectedSet.has(option.id)).map((option) => option.label);
}

function SelectionRow({ level, options, selected, disabled, readOnly, onOpen, first }) {
  const meta = LEVEL_META[level];
  const names = selectedNames(options, selected);
  const shown = names.slice(0, 2);
  const extra = names.length - shown.length;
  const hint = disabled ? meta.blockedHint : meta.hint;

  return (
    <div
      role={readOnly || disabled ? undefined : "button"}
      tabIndex={readOnly || disabled ? undefined : 0}
      aria-label={readOnly || disabled ? undefined : `Choose ${meta.label.toLowerCase()}`}
      onClick={readOnly || disabled ? undefined : onOpen}
      onKeyDown={readOnly || disabled ? undefined : (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
      style={{
        display: "flex",
        gap: "var(--space-md)",
        alignItems: "flex-start",
        minHeight: "calc(var(--space-xl) + var(--space-md))",
        padding: "var(--space-md)",
        borderTopWidth: first ? 0 : 1,
        borderTopStyle: "solid",
        borderTopColor: "var(--color-border-subtle)",
        cursor: readOnly || disabled ? "default" : "pointer",
        opacity: disabled ? 0.5 : 1,
        background: "var(--surface-card)",
        boxSizing: "border-box",
      }}
    >
      <span style={{
        width: "var(--space-xl)",
        height: "var(--space-xl)",
        borderRadius: "var(--radius-md)",
        flexShrink: 0,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        background: selected.length ? "var(--color-primary-surface)" : "var(--surface-muted)",
      }}>
        <Icon
          name={meta.icon}
          size={20}
          color={selected.length ? "var(--color-primary)" : "var(--color-neutral-500)"}
        />
      </span>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
          <span style={{
            color: "var(--color-text-primary)",
            fontSize: "var(--text-label-sm-size)",
            lineHeight: "var(--text-label-sm-line)",
            fontWeight: "var(--font-weight-bold)",
          }}>
            {meta.label}
          </span>
          {!!selected.length && (
            <span style={{
              color: "var(--color-primary)",
              background: "var(--color-primary-surface)",
              borderRadius: "var(--radius-pill)",
              padding: "0 var(--space-sm)",
              fontSize: "var(--text-label-xs-size)",
              lineHeight: "var(--text-label-xs-line)",
              fontWeight: "var(--font-weight-bold)",
            }}>
              {selected.length} / {options.length}
            </span>
          )}
        </span>
        {!selected.length ? (
          <span style={{
            display: "block",
            marginTop: "var(--space-xs)",
            color: "var(--color-text-placeholder)",
            fontSize: "var(--text-body-sm-size)",
            lineHeight: "var(--text-body-sm-line)",
          }}>
            {hint}
          </span>
        ) : (
          <span style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-xs)", marginTop: "var(--space-sm)" }}>
            {shown.map((name) => (
              <span key={name} style={{
                maxWidth: "calc(var(--space-2xl) * 3)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                color: "var(--color-primary-dark)",
                background: "var(--color-primary-surface-hover)",
                borderWidth: 1,
                borderStyle: "solid",
                borderColor: "var(--color-border-subtle)",
                borderRadius: "var(--radius-pill)",
                padding: "var(--space-xs) var(--space-sm)",
                fontSize: "var(--text-label-xs-size)",
                lineHeight: "var(--text-label-xs-line)",
                fontWeight: "var(--font-weight-bold)",
              }}>
                {name}
              </span>
            ))}
            {extra > 0 && (
              <span style={{
                padding: "var(--space-xs)",
                color: "var(--color-primary)",
                fontSize: "var(--text-label-xs-size)",
                lineHeight: "var(--text-label-xs-line)",
                fontWeight: "var(--font-weight-bold)",
              }}>
                +{extra} more
              </span>
            )}
          </span>
        )}
      </span>
      {!readOnly && <Icon name="KeyboardArrowRight" size={20} color="var(--color-neutral-400)" />}
    </div>
  );
}

function SelectionSheet({ level, options, selected, locale, onApply, onClose }) {
  const [draft, setDraft] = useState(selected);
  const [query, setQuery] = useState("");
  const meta = LEVEL_META[level];
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visible = options.filter((option) => (
    !normalizedQuery
    || option.label.toLocaleLowerCase().includes(normalizedQuery)
    || option.group?.toLocaleLowerCase().includes(normalizedQuery)
  ));
  const allVisibleSelected = visible.length > 0 && visible.every((option) => draft.includes(option.id));

  const sections = useMemo(() => {
    const groups = new Map();
    visible.forEach((option) => {
      const group = option.group || "";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(option);
    });
    return Array.from(groups.entries());
  }, [visible]);

  const toggle = (id) => {
    setDraft((current) => (
      current.includes(id)
        ? current.filter((selectedId) => selectedId !== id)
        : [...current, id]
    ));
  };

  const toggleVisible = () => {
    const visibleIds = new Set(visible.map((option) => option.id));
    setDraft((current) => (
      allVisibleSelected
        ? current.filter((id) => !visibleIds.has(id))
        : [...new Set([...current, ...visibleIds])]
    ));
  };

  return (
    <BottomSheet
      open
      onClose={onClose}
      style={{
        display: "flex",
        flexDirection: "column",
        maxHeight: "88%",
        padding: 0,
        overflow: "hidden",
        borderRadius: "var(--radius-lg) var(--radius-lg) 0 0",
        background: "var(--surface-card)",
        boxShadow: "var(--shadow-modal)",
      }}
    >
      <div style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "var(--space-md)",
        padding: "var(--space-md)",
        flexShrink: 0,
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            color: "var(--color-text-primary)",
            fontSize: "var(--text-h3-size)",
            lineHeight: "var(--text-h3-line)",
            fontWeight: "var(--text-h3-weight)",
          }}>
            Select {meta.label.toLowerCase()}
          </div>
          <div style={{
            color: "var(--color-text-secondary)",
            fontSize: "var(--text-caption-size)",
            lineHeight: "var(--text-caption-line)",
          }}>
            {meta.subtitle}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close selection"
          style={{
            width: "calc(var(--space-xl) + var(--space-md))",
            height: "calc(var(--space-xl) + var(--space-md))",
            border: "none",
            borderRadius: "var(--radius-pill)",
            background: "var(--surface-muted)",
            color: "var(--color-text-secondary)",
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Icon name="Close" size={20} />
        </button>
      </div>
      <div style={{ padding: "0 var(--space-md) var(--space-sm)", flexShrink: 0 }}>
        <TextField
          aria-label={`Search ${meta.label.toLowerCase()}`}
          placeholder={`Search ${meta.label.toLowerCase()}`}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          startAdornment={<Icon name="SearchOutlined" size={20} color="var(--color-text-placeholder)" />}
        />
      </div>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "var(--space-sm)",
        padding: "0 var(--space-md) var(--space-sm)",
        flexShrink: 0,
      }}>
        <span style={{
          color: "var(--color-text-secondary)",
          fontSize: "var(--text-caption-size)",
          lineHeight: "var(--text-caption-line)",
        }}>
          {visible.length} {visible.length === 1 ? "option" : "options"}{normalizedQuery ? " matching" : ""}
        </span>
        <Button
          variant="text"
          size="small"
          label={allVisibleSelected ? "Clear these" : normalizedQuery ? "Select matching" : "Select all"}
          disabled={!visible.length}
          onClick={toggleVisible}
        />
      </div>
      <div
        role="listbox"
        aria-label={`${meta.label} options`}
        aria-multiselectable="true"
        style={{
          flex: 1,
          overflowY: "auto",
          borderTopWidth: 1,
          borderTopStyle: "solid",
          borderTopColor: "var(--color-border-subtle)",
        }}
      >
        {!visible.length && (
          <div style={{
            padding: "var(--space-2xl) var(--space-md)",
            textAlign: "center",
            color: "var(--color-text-secondary)",
            fontSize: "var(--text-body-sm-size)",
            lineHeight: "var(--text-body-sm-line)",
          }}>
            No options match “{query}”.
          </div>
        )}
        {sections.map(([group, items]) => (
          <React.Fragment key={group || "all"}>
            {group && (
              <div style={{
                position: "sticky",
                top: 0,
                zIndex: 1,
                padding: "var(--space-sm) var(--space-md)",
                borderBottomWidth: 1,
                borderBottomStyle: "solid",
                borderBottomColor: "var(--color-border-subtle)",
                background: "var(--surface-muted)",
                color: "var(--color-text-secondary)",
                fontSize: "var(--text-overline-size)",
                lineHeight: "var(--text-overline-line)",
                fontWeight: "var(--text-overline-weight)",
                letterSpacing: "var(--text-overline-tracking)",
                textTransform: "uppercase",
              }}>
                {group}
              </div>
            )}
            {items.map((option) => {
              const checked = draft.includes(option.id);
              return (
                <div
                  key={option.id}
                  role="option"
                  tabIndex={0}
                  aria-selected={checked}
                  onClick={() => toggle(option.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggle(option.id);
                    }
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-md)",
                    minHeight: "calc(var(--space-xl) + var(--space-md))",
                    padding: "var(--space-sm) var(--space-md)",
                    borderBottomWidth: 1,
                    borderBottomStyle: "solid",
                    borderBottomColor: "var(--color-border-subtle)",
                    background: checked ? "var(--color-primary-surface-hover)" : "var(--surface-card)",
                    cursor: "pointer",
                    boxSizing: "border-box",
                  }}
                >
                  <Checkbox checked={checked} onChange={() => toggle(option.id)} style={{ pointerEvents: "none" }} />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{
                      display: "block",
                      color: "var(--color-text-primary)",
                      fontSize: "var(--text-body-size)",
                      lineHeight: "var(--text-body-line)",
                      fontWeight: checked ? "var(--font-weight-bold)" : "var(--font-weight-regular)",
                    }}>
                      {option.label}
                    </span>
                    {typeof option.outletCount === "number" && (
                      <span style={{
                        display: "block",
                        color: "var(--color-text-secondary)",
                        fontSize: "var(--text-caption-size)",
                        lineHeight: "var(--text-caption-line)",
                      }}>
                        {option.outletCount.toLocaleString(locale)} outlets
                      </span>
                    )}
                  </span>
                  {checked && <Icon name="Check" size={20} color="var(--color-primary)" />}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-md)",
        padding: "var(--space-md)",
        borderTopWidth: 1,
        borderTopStyle: "solid",
        borderTopColor: "var(--color-border-subtle)",
        background: "var(--surface-card)",
        flexShrink: 0,
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            color: "var(--color-text-primary)",
            fontSize: "var(--text-label-size)",
            lineHeight: "var(--text-label-line)",
            fontWeight: "var(--font-weight-bold)",
          }}>
            {draft.length} selected
          </div>
          <div style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            color: "var(--color-text-secondary)",
            fontSize: "var(--text-caption-size)",
            lineHeight: "var(--text-caption-line)",
          }}>
            {draft.length ? selectedNames(options, draft).join(", ") : "Nothing selected yet"}
          </div>
        </div>
        <Button label="Apply" onClick={() => onApply(draft)} style={{ flexShrink: 0 }} />
      </div>
    </BottomSheet>
  );
}

export function GeoScopePicker({
  zones = [],
  states = [],
  districts = [],
  shopCategories = [],
  value,
  defaultValue = EMPTY_SCOPE,
  assigned,
  onChange,
  getOutletCount = defaultOutletCount,
  cascadeChildren = true,
  readOnly = false,
  disabled = false,
  showScopeSummary = true,
  locale = "en-IN",
  style,
}) {
  const data = useMemo(
    () => ({ zones, states, districts, shopCategories }),
    [zones, states, districts, shopCategories],
  );
  const controlled = value !== undefined;
  const [internalValue, setInternalValue] = useState(() => sanitizeScope(defaultValue, data, assigned));
  const [activeLevel, setActiveLevel] = useState(null);
  const scope = sanitizeScope(controlled ? value : internalValue, data, assigned);
  const options = buildLevelOptions(data, assigned, scope);
  const rawOutletCount = getOutletCount(scope, data);
  const hasOutletCountData = (
    getOutletCount !== defaultOutletCount
    || districts.some((district) => typeof district.outletCount === "number")
  ) && Number.isFinite(rawOutletCount);
  const outletCount = hasOutletCountData ? Math.max(0, Math.round(rawOutletCount)) : 0;

  useEffect(() => {
    if (controlled || scopesEqual(internalValue, scope)) return;
    setInternalValue(scope);
    onChange?.({ ...scope, outletCount });
  }, [controlled, internalValue, onChange, outletCount, scope]);

  const commit = (nextScope) => {
    const next = sanitizeScope(nextScope, data, assigned);
    const nextOutletCount = Math.max(0, Math.round(getOutletCount(next, data) || 0));
    if (!controlled) setInternalValue(next);
    if (!scopesEqual(scope, next)) onChange?.({ ...next, outletCount: nextOutletCount });
  };

  const applyLevel = (level, selected) => {
    const next = { ...scope, [level]: selected };
    if (level === "zones") {
      if (cascadeChildren) {
        next.states = states
          .filter((state) => selected.includes(state.zoneId) && includesAssigned(assigned, "states", state.id))
          .map((state) => state.id);
        next.districts = districts
          .filter((district) => next.states.includes(district.stateId) && includesAssigned(assigned, "districts", district.id))
          .map((district) => district.id);
      } else {
        next.states = scope.states.filter((id) => {
          const option = states.find((state) => state.id === id);
          return option && selected.includes(option.zoneId);
        });
        next.districts = scope.districts.filter((id) => {
          const option = districts.find((district) => district.id === id);
          return option && next.states.includes(option.stateId);
        });
      }
    }
    if (level === "states") {
      if (cascadeChildren) {
        next.districts = districts
          .filter((district) => selected.includes(district.stateId) && includesAssigned(assigned, "districts", district.id))
          .map((district) => district.id);
      } else {
        next.districts = scope.districts.filter((id) => {
          const option = districts.find((district) => district.id === id);
          return option && selected.includes(option.stateId);
        });
      }
    }
    commit(next);
    setActiveLevel(null);
  };

  const showShopCategories = shopCategories.length > 0;
  const levels = showShopCategories
    ? ["zones", "states", "districts", "shopCategories"]
    : ["zones", "states", "districts"];
  const activeOptions = activeLevel ? options[activeLevel] : [];
  const districtSummary = `${scope.districts.length} ${scope.districts.length === 1 ? "district" : "districts"}`;
  const categorySummary = showShopCategories
    ? scope.shopCategories.length
      ? `${scope.shopCategories.length} ${scope.shopCategories.length === 1 ? "category" : "categories"}`
      : "all categories"
    : null;

  return (
    <div style={{ fontFamily: "var(--font-family-base)", ...style }}>
      <div style={{
        overflow: "hidden",
        borderWidth: 1,
        borderStyle: "solid",
        borderColor: "var(--color-border-subtle)",
        borderRadius: "var(--radius-lg)",
        background: "var(--surface-card)",
        boxShadow: "var(--shadow-card)",
      }}>
        {levels.map((level, index) => (
          <SelectionRow
            key={level}
            level={level}
            options={options[level]}
            selected={scope[level]}
            disabled={disabled || (level === "states" && !scope.zones.length) || (level === "districts" && !scope.states.length)}
            readOnly={readOnly}
            onOpen={() => setActiveLevel(level)}
            first={index === 0}
          />
        ))}
      </div>
      {showScopeSummary ? (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-md)",
          marginTop: "var(--space-md)",
          padding: "var(--space-md)",
          borderWidth: 1,
          borderStyle: "solid",
          borderColor: "var(--color-border-subtle)",
          borderRadius: "var(--radius-lg)",
          background: "var(--color-primary-surface-hover)",
        }}>
          <span style={{
            width: "calc(var(--space-xl) + var(--space-md))",
            height: "calc(var(--space-xl) + var(--space-md))",
            borderRadius: "var(--radius-md)",
            background: "var(--color-primary-surface)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}>
            <Icon name="InventoryOutlined" size={22} color="var(--color-primary)" />
          </span>
          <span style={{ flex: 1, minWidth: 0 }}>
            {hasOutletCountData ? (
              <span style={{
                display: "block",
                color: "var(--color-primary-dark)",
                fontSize: "var(--text-h2-size)",
                lineHeight: "var(--text-h2-line)",
                fontWeight: "var(--font-weight-bold)",
              }}>
                {`${outletCount.toLocaleString(locale)} outlets`}
              </span>
            ) : null}
            <span style={{
              display: "block",
              color: "var(--color-text-secondary)",
              fontSize: "var(--text-caption-size)",
              lineHeight: "var(--text-caption-line)",
            }}>
              In scope · {districtSummary}{categorySummary ? ` · ${categorySummary}` : ""}
            </span>
          </span>
        </div>
      ) : null}
      {activeLevel && !readOnly && !disabled && (
        <SelectionSheet
          key={activeLevel}
          level={activeLevel}
          options={activeOptions}
          selected={scope[activeLevel]}
          locale={locale}
          onApply={(selected) => applyLevel(activeLevel, selected)}
          onClose={() => setActiveLevel(null)}
        />
      )}
    </div>
  );
}

export default GeoScopePicker;
