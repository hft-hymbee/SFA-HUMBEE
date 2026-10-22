"use client";

import { useEffect, useState } from "react";

export const SEARCH_API_DEBOUNCE_MS = 2_000;

export function useDebouncedValue<T>(value: T, delayMs = SEARCH_API_DEBOUNCE_MS) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedValue(value), delayMs);
    return () => window.clearTimeout(timeout);
  }, [delayMs, value]);
  return debouncedValue;
}

export function useDebouncedSearchQuery(query: string, delayMs = SEARCH_API_DEBOUNCE_MS) {
  const [debouncedQuery, setDebouncedQuery] = useState(query);
  if (!query.trim() && debouncedQuery !== query) setDebouncedQuery(query);
  useEffect(() => {
    if (!query.trim()) return;
    const timeout = window.setTimeout(() => setDebouncedQuery(query), delayMs);
    return () => window.clearTimeout(timeout);
  }, [delayMs, query]);
  return debouncedQuery;
}
