"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ulid } from "ulid";
import { ErrorState, Skeleton } from "humbee-design-system";
import type { BeatDetailResponse, GeoScope, ShopCategory } from "@humbee/api-contract";
import { SpScreen } from "@/src/features/shell/components";
import { createIdempotencyKey } from "@/src/shared/api";
import { readSessionSync } from "@/src/shared/auth/session";
import { useDebouncedSearchQuery } from "@/src/shared/state";
import type { OutletChoice } from "./service";
import { mapBeat, mapOutlet, useBeatDraftVersion, useBeatMutations, useBeats, useGeographyMaster, useScopeOutlets } from "./service";

export type BeatFrequency = "daily" | "weekly" | "fortnightly" | "monthly";

interface BeatDraft {
  version: 1;
  actorId: string;
  clientId: string;
  beatId: string;
  submitIdempotencyKey: string;
  zones: string[];
  states: string[];
  districts: string[];
  categories: string[];
  outletIds: string[];
  name: string;
  frequency: BeatFrequency;
  days: number[];
  weeks: number[];
}

interface BeatDraftContextValue {
  draft: BeatDraft;
  availableOutlets: OutletChoice[];
  outletsError: Error | null;
  outletsLoading: boolean;
  outletsRefreshing: boolean;
  outletsComplete: boolean;
  outletQuery: string;
  selectedOutlets: OutletChoice[];
  unavailableSelectionCount: number;
  refreshOutlets: () => void;
  setOutletQuery: (query: string) => void;
  setGeoScope: (scope: Pick<BeatDraft, "zones" | "states" | "districts" | "categories">) => void;
  toggleDistrict: (district: string) => void;
  setAllCategories: () => void;
  toggleCategory: (category: string) => void;
  toggleOutlet: (outletId: string) => void;
  toggleOutletGroup: (location: string) => void;
  toggleAllOutlets: () => void;
  setName: (name: string) => void;
  setFrequency: (frequency: BeatFrequency) => void;
  toggleDay: (day: number) => void;
  toggleWeek: (week: number) => void;
  submit: () => Promise<void>;
}

const BeatDraftContext = createContext<BeatDraftContextValue | null>(null);
const DRAFT_STORAGE_PREFIX = "humbee:beat-draft:";
const UNTITLED_BEAT = "Untitled beat";

function draftStorageKey(actorId: string) {
  return `${DRAFT_STORAGE_PREFIX}${actorId || "anonymous"}`;
}

function isBeatFrequency(value: unknown): value is BeatFrequency {
  return value === "daily" || value === "weekly" || value === "fortnightly" || value === "monthly";
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function numberArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is number => typeof item === "number") : [];
}

function asShopCategories(values: string[]): ShopCategory[] {
  return values as ShopCategory[];
}

function createInitialDraft(actorId: string): BeatDraft {
  return {
    version: 1,
    actorId,
    clientId: ulid(),
    beatId: ulid(),
    submitIdempotencyKey: createIdempotencyKey(),
    zones: [],
    states: [],
    districts: [],
    categories: [],
    outletIds: [],
    name: "",
    frequency: "daily",
    days: [],
    weeks: [],
  };
}

function readStoredDraft(initialDraft: BeatDraft, actorId: string): BeatDraft {
  if (typeof window === "undefined") return initialDraft;
  const raw = window.sessionStorage.getItem(draftStorageKey(actorId));
  if (!raw) return initialDraft;
  try {
    const stored = JSON.parse(raw) as Partial<BeatDraft>;
    if (stored.version !== 1 || stored.actorId !== actorId) return initialDraft;
    return {
      ...initialDraft,
      clientId: typeof stored.clientId === "string" ? stored.clientId : initialDraft.clientId,
      beatId: typeof stored.beatId === "string" && stored.beatId.trim() ? stored.beatId : initialDraft.beatId,
      submitIdempotencyKey: typeof stored.submitIdempotencyKey === "string" ? stored.submitIdempotencyKey : initialDraft.submitIdempotencyKey,
      zones: stringArray(stored.zones),
      states: stringArray(stored.states),
      districts: stringArray(stored.districts),
      categories: stringArray(stored.categories),
      outletIds: stringArray(stored.outletIds),
      name: typeof stored.name === "string" ? stored.name : "",
      frequency: isBeatFrequency(stored.frequency) ? stored.frequency : "daily",
      days: numberArray(stored.days),
      weeks: numberArray(stored.weeks),
    };
  } catch {
    return initialDraft;
  }
}

function draftFromServer(actorId: string, detail: BeatDetailResponse): BeatDraft {
  const beat = mapBeat(detail);
  return {
    ...createInitialDraft(actorId),
    beatId: beat.id,
    zones: beat.zones,
    states: beat.states,
    districts: beat.districts,
    categories: beat.categories,
    outletIds: beat.outletIds,
    name: beat.name === UNTITLED_BEAT ? "" : beat.name,
    frequency: beat.frequencyPlan.cadence,
    days: beat.frequencyPlan.days,
    weeks: beat.frequencyPlan.weeks,
  };
}

function writeStoredDraft(actorId: string, draft: BeatDraft) {
  if (typeof window === "undefined" || !actorId) return;
  window.sessionStorage.setItem(draftStorageKey(actorId), JSON.stringify(draft));
}

function clearStoredDraft(actorId: string) {
  if (typeof window === "undefined" || !actorId) return;
  window.sessionStorage.removeItem(draftStorageKey(actorId));
}

function scopeKey(scope: Pick<BeatDraft, "zones" | "states" | "districts" | "categories">) {
  return JSON.stringify({
    zones: scope.zones,
    states: scope.states,
    districts: scope.districts,
    categories: scope.categories,
  });
}

function draftCode(beatId: string, name: string) {
  const trimmed = name.trim();
  if (!trimmed || trimmed === UNTITLED_BEAT) return beatId;
  return trimmed;
}

export function BeatDraftProvider({
  children,
}: {
  children: ReactNode;
}) {
  const actorId = readSessionSync()?.employeeId ?? "";
  const geography = useGeographyMaster();
  const mutations = useBeatMutations();
  const createRequestedBeatId = useRef<string | null>(null);
  const failedCreateBeatId = useRef<string | null>(null);
  const requestedScopeKey = useRef<string | null>(null);
  const savedScopeKey = useRef<string | null>(null);
  const [createdBeatId, setCreatedBeatId] = useState<string | null>(null);
  const [savedScopeKeyValue, setSavedScopeKeyValue] = useState<string | null>(null);
  const initialDraft = useMemo(
    () => createInitialDraft(actorId),
    [actorId],
  );
  const [draft, setDraft] = useState<BeatDraft>(() => readStoredDraft(initialDraft, actorId));
  const serverDrafts = useBeats("draft", { refetchOnMount: "always" });
  const [resumeBeatId, setResumeBeatId] = useState<string | null>(null);
  const [resumedForActor, setResumedForActor] = useState<string | null>(null);
  const resumeResolved = resumedForActor === actorId;
  const resumeDetail = useBeatDraftVersion(resumeBeatId ?? "", Boolean(resumeBeatId) && !resumeResolved);
  const [outletQuery, setOutletQuery] = useState("");
  const debouncedOutletQuery = useDebouncedSearchQuery(outletQuery);
  const draftInAssignedScope = useMemo(() => {
    const pool = geography.data?.pool;
    if (!pool) return false;
    return draft.zones.every((id) => pool.zones.includes(id))
      && draft.states.every((id) => pool.states.includes(id))
      && draft.districts.every((id) => pool.districts.includes(id))
      && draft.categories.every((id) => pool.cats.includes(id as ShopCategory));
  }, [draft.categories, draft.districts, draft.states, draft.zones, geography.data?.pool]);
  const draftScopeKey = useMemo(() => scopeKey(draft), [draft]);
  const draftScopePayload = useMemo<GeoScope>(() => ({
    zones: draft.zones,
    states: draft.states,
    districts: draft.districts,
    cats: asShopCategories(draft.categories),
  }), [draft.categories, draft.districts, draft.states, draft.zones]);
  const hasOutletScope = draft.districts.length > 0 && draftInAssignedScope;
  const outletScopeReady = hasOutletScope && createdBeatId === draft.beatId && savedScopeKeyValue === draftScopeKey;
  const scopeOutlets = useScopeOutlets(draft.beatId, debouncedOutletQuery, outletScopeReady, draftScopeKey);
  const outlets = useMemo(() => (outletScopeReady ? scopeOutlets.data ?? [] : []).map(mapOutlet), [outletScopeReady, scopeOutlets.data]);

  useEffect(() => {
    if (!actorId || draft.actorId === actorId) return;
    queueMicrotask(() => setDraft(readStoredDraft(initialDraft, actorId)));
  }, [actorId, draft.actorId, initialDraft]);

  useEffect(() => {
    if (resumeResolved) writeStoredDraft(actorId, draft);
  }, [actorId, draft, resumeResolved]);

  useEffect(() => {
    if (!actorId || resumeResolved || !serverDrafts.isSuccess || serverDrafts.isFetching) return;
    const draftIds = serverDrafts.data.items.map((item) => item.id);
    if (draftIds.includes(draft.beatId)) {
      queueMicrotask(() => setResumedForActor(actorId));
      return;
    }
    const latestDraftId = draftIds[0];
    if (!latestDraftId) {
      queueMicrotask(() => {
        setDraft(createInitialDraft(actorId));
        setResumedForActor(actorId);
      });
      return;
    }
    if (resumeBeatId !== latestDraftId) {
      queueMicrotask(() => setResumeBeatId(latestDraftId));
      return;
    }
    if (resumeDetail.isPending || resumeDetail.isFetching) return;
    const detail = resumeDetail.data;
    queueMicrotask(() => {
      setDraft(detail ? draftFromServer(actorId, detail) : createInitialDraft(actorId));
      setResumedForActor(actorId);
    });
  }, [actorId, draft.beatId, resumeBeatId, resumeDetail.data, resumeDetail.isFetching, resumeDetail.isPending, resumeResolved, serverDrafts.data, serverDrafts.isFetching, serverDrafts.isSuccess]);

  useEffect(() => {
    const pool = geography.data?.pool;
    if (!pool) return;
    const zones = draft.zones.filter((id) => pool.zones.includes(id));
    const states = draft.states.filter((id) => pool.states.includes(id));
    const districts = draft.districts.filter((id) => pool.districts.includes(id));
    const categories = draft.categories.filter((id) => pool.cats.includes(id as ShopCategory));
    if (
      zones.length === draft.zones.length
      && states.length === draft.states.length
      && districts.length === draft.districts.length
      && categories.length === draft.categories.length
    ) {
      return;
    }
    queueMicrotask(() => {
      setOutletQuery("");
      setDraft((current) => ({ ...current, zones, states, districts, categories, outletIds: [] }));
    });
  }, [draft.categories, draft.districts, draft.states, draft.zones, geography.data?.pool]);

  useEffect(() => {
    if (!resumeResolved || !draft.beatId || createdBeatId === draft.beatId || failedCreateBeatId.current === draft.beatId || mutations.create.isPending) return;
    if (mutations.create.data?.id === draft.beatId) {
      queueMicrotask(() => setCreatedBeatId(draft.beatId));
      return;
    }
    if (createRequestedBeatId.current === draft.beatId) return;
    const beatId = draft.beatId;
    createRequestedBeatId.current = beatId;
    void mutations.create.mutateAsync(beatId)
      .then((beat) => {
        failedCreateBeatId.current = null;
        setCreatedBeatId(beat.id);
        setDraft((current) => current.beatId === beat.id ? current : { ...current, beatId: beat.id });
      })
      .catch(() => {
        createRequestedBeatId.current = null;
        failedCreateBeatId.current = beatId;
        setCreatedBeatId(null);
      });
  }, [createdBeatId, draft.beatId, mutations.create, resumeResolved]);

  const saveScope = useCallback((key: string, geoScope: GeoScope) => {
    if (!draft.beatId || createdBeatId !== draft.beatId || requestedScopeKey.current === key || mutations.saveDraft.isPending) return false;
    const beatId = draft.beatId;
    requestedScopeKey.current = key;
    void mutations.saveDraft.mutateAsync({
      beatId,
      geoScope,
    })
      .then(() => {
        savedScopeKey.current = key;
        setSavedScopeKeyValue(key);
      })
      .catch(() => undefined);
    return true;
  }, [createdBeatId, draft.beatId, mutations.saveDraft]);

  useEffect(() => {
    if (!hasOutletScope) {
      requestedScopeKey.current = null;
      savedScopeKey.current = null;
      queueMicrotask(() => setSavedScopeKeyValue(null));
      return;
    }
    if (createdBeatId !== draft.beatId || savedScopeKeyValue === draftScopeKey) return;
    saveScope(draftScopeKey, draftScopePayload);
  }, [createdBeatId, draft.beatId, draftScopeKey, draftScopePayload, hasOutletScope, saveScope, savedScopeKeyValue]);

  const availableOutlets = outlets;
  const draftCreationLoading = Boolean(draft.beatId && hasOutletScope && createdBeatId !== draft.beatId && mutations.create.isPending);
  const scopeSaveLoading = Boolean(hasOutletScope && createdBeatId === draft.beatId && savedScopeKeyValue !== draftScopeKey && mutations.saveDraft.isPending);
  const outletWalkPending = Boolean(scopeOutlets.isFetching || scopeOutlets.hasNextPage);
  const outletInitialLoading = Boolean(outletScopeReady && (scopeOutlets.isPending || (outletWalkPending && !outlets.length)));
  const outletRefreshing = Boolean(outletScopeReady && outletWalkPending && outlets.length > 0);

  const outletsComplete = Boolean(outletScopeReady && !debouncedOutletQuery && !outletQuery && scopeOutlets.isSuccess && !outletWalkPending);
  const selectableOutlets = useMemo(() => availableOutlets.filter((outlet) => !outlet.takenBy), [availableOutlets]);
  const selectedOutlets = useMemo(() => {
    const selectedIdSet = new Set(draft.outletIds);
    return selectableOutlets.filter((outlet) => selectedIdSet.has(outlet.id));
  }, [selectableOutlets, draft.outletIds]);
  const unavailableSelectionCount = outletsComplete ? draft.outletIds.length - selectedOutlets.length : 0;

  const updateScope = useCallback((
    nextZones: string[],
    nextStates: string[],
    nextDistricts: string[],
    nextCategories: string[],
  ) => {
    setDraft((current) => ({
      ...current,
      zones: nextZones,
      states: nextStates,
      districts: nextDistricts,
      categories: nextCategories,
      outletIds: [],
    }));
  }, []);

  const replaceOutletSelection = useCallback((nextOutletIds: string[]) => {
    setDraft((current) => current.beatId === draft.beatId ? { ...current, outletIds: nextOutletIds } : current);
  }, [draft.beatId]);

  const value = useMemo<BeatDraftContextValue>(() => ({
    draft,
    availableOutlets,
    outletsError: mutations.create.isError ? mutations.create.error : mutations.saveDraft.isError ? mutations.saveDraft.error : scopeOutlets.isError ? scopeOutlets.error : null,
    outletsLoading: Boolean(draftCreationLoading || scopeSaveLoading || outletInitialLoading),
    outletsRefreshing: outletRefreshing,
    outletsComplete,
    outletQuery,
    selectedOutlets,
    unavailableSelectionCount,
    refreshOutlets: () => {
      if (hasOutletScope && createdBeatId !== draft.beatId) {
        failedCreateBeatId.current = null;
        createRequestedBeatId.current = null;
        mutations.create.reset();
        return;
      }
      if (hasOutletScope && savedScopeKey.current !== draftScopeKey) {
        requestedScopeKey.current = null;
        saveScope(draftScopeKey, draftScopePayload);
        return;
      }
      void scopeOutlets.refetch();
    },
    setOutletQuery,
    setGeoScope: (nextScope) => {
      setOutletQuery("");
      updateScope(nextScope.zones, nextScope.states, nextScope.districts, nextScope.categories);
    },
    toggleDistrict: (district) => {
      const districts = draft.districts.includes(district)
        ? draft.districts.filter((value) => value !== district)
        : [...draft.districts, district];
      updateScope(draft.zones, draft.states, districts, draft.categories);
    },
    setAllCategories: () => updateScope(draft.zones, draft.states, draft.districts, []),
    toggleCategory: (category) => {
      const categories = draft.categories.includes(category)
        ? draft.categories.filter((value) => value !== category)
        : [...draft.categories, category];
      updateScope(draft.zones, draft.states, draft.districts, categories);
    },
    toggleOutlet: (outletId) => {
      if (!selectableOutlets.some((outlet) => outlet.id === outletId)) return;
      const outletIds = draft.outletIds.includes(outletId)
        ? draft.outletIds.filter((id) => id !== outletId)
        : [...draft.outletIds, outletId];
      replaceOutletSelection(outletIds);
    },
    toggleOutletGroup: (location) => {
      const groupIds = selectableOutlets.filter((outlet) => outlet.location === location).map((outlet) => outlet.id);
      const groupIdSet = new Set(groupIds);
      const selectedIdSet = new Set(draft.outletIds);
      const allSelected = groupIds.length > 0 && groupIds.every((id) => selectedIdSet.has(id));
      const outletIds = allSelected
        ? draft.outletIds.filter((id) => !groupIdSet.has(id))
        : [...new Set([...draft.outletIds, ...groupIds])];
      replaceOutletSelection(outletIds);
    },
    toggleAllOutlets: () => {
      if (outletWalkPending) return;
      const outletIdsInScope = selectableOutlets.map((outlet) => outlet.id);
      const outletIdSet = new Set(outletIdsInScope);
      const selectedIdSet = new Set(draft.outletIds);
      const allSelected = outletIdsInScope.length > 0 && outletIdsInScope.every((id) => selectedIdSet.has(id));
      const outletIds = allSelected
        ? draft.outletIds.filter((id) => !outletIdSet.has(id))
        : [...new Set([...draft.outletIds, ...outletIdsInScope])];
      replaceOutletSelection(outletIds);
    },
    setName: (name) => setDraft((current) => ({ ...current, name })),
    setFrequency: (frequency) => setDraft((current) => ({ ...current, frequency })),
    toggleDay: (day) => setDraft((current) => ({
      ...current,
      days: current.days.includes(day) ? current.days.filter((value) => value !== day) : [...current.days, day],
    })),
    toggleWeek: (week) => setDraft((current) => ({
      ...current,
      weeks: current.weeks.includes(week) ? current.weeks.filter((value) => value !== week) : [...current.weeks, week],
    })),
    submit: async () => {
      if (!draft.beatId) throw new Error("Beat draft is not ready.");
      if (!outletsComplete) throw new Error("Outlets are still loading. Try again in a moment.");
      const trimmedName = draft.name.trim();
      await mutations.saveDraft.mutateAsync({
        beatId: draft.beatId,
        displayName: trimmedName,
        code: draftCode(draft.beatId, trimmedName),
        geoScope: { zones: draft.zones, states: draft.states, districts: draft.districts, cats: asShopCategories(draft.categories) },
        frequency: { frequency: draft.frequency, visit_days: draft.days, week_cycle: draft.weeks },
      });
      await mutations.replaceOutlets.mutateAsync({ beatId: draft.beatId, outletRefs: selectedOutlets.map((outlet) => outlet.id) });
      await mutations.submit.mutateAsync({ beatId: draft.beatId, idempotencyKey: draft.submitIdempotencyKey });
      clearStoredDraft(actorId);
    },
  }), [actorId, availableOutlets, createdBeatId, draft, draftCreationLoading, draftScopeKey, draftScopePayload, hasOutletScope, mutations.create, mutations.replaceOutlets, mutations.saveDraft, mutations.submit, outletInitialLoading, outletQuery, outletRefreshing, outletWalkPending, outletsComplete, replaceOutletSelection, saveScope, scopeOutlets, scopeSaveLoading, selectableOutlets, selectedOutlets, unavailableSelectionCount, updateScope]);

  if (!resumeResolved) {
    return (
      <SpScreen title="Create beat" back>
        {serverDrafts.isError ? (
          <ErrorState onRetry={() => void serverDrafts.refetch()} />
        ) : (
          <div className="sp-content"><Skeleton height={320} radius={12} /></div>
        )}
      </SpScreen>
    );
  }

  return <BeatDraftContext.Provider value={value}>{children}</BeatDraftContext.Provider>;
}

export function useBeatDraft() {
  const context = useContext(BeatDraftContext);
  if (!context) throw new Error("useBeatDraft must be used within BeatDraftProvider");
  return context;
}
