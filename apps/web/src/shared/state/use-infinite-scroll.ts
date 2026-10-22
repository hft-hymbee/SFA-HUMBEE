"use client";

import { useEffect, useRef } from "react";

const DEFAULT_THRESHOLD = 0.8;

interface UseInfiniteScrollTriggerOptions {
  hasNextPage: boolean | undefined;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  threshold?: number;
}

function findScrollParent(node: HTMLElement): HTMLElement | null {
  let current = node.parentElement;
  while (current) {
    if (/(auto|scroll)/.test(getComputedStyle(current).overflowY)) return current;
    current = current.parentElement;
  }
  return null;
}

/**
 * Attach the returned ref to any element inside a scrollable list container.
 * Fetches the next page once the container has been scrolled past `threshold`
 * (default 80%), repeating automatically as long as `hasNextPage` stays true.
 */
export function useInfiniteScrollTrigger<T extends HTMLElement>({
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  threshold = DEFAULT_THRESHOLD,
}: UseInfiniteScrollTriggerOptions) {
  const anchorRef = useRef<T>(null);

  useEffect(() => {
    if (!hasNextPage) return;
    const anchor = anchorRef.current;
    if (!anchor) return;
    const container = findScrollParent(anchor);
    if (!container) return;

    const maybeFetchNext = () => {
      if (isFetchingNextPage) return;
      const { scrollTop, scrollHeight, clientHeight } = container;
      if (scrollHeight <= clientHeight) return;
      if (scrollTop + clientHeight >= scrollHeight * threshold) fetchNextPage();
    };

    container.addEventListener("scroll", maybeFetchNext, { passive: true });
    return () => container.removeEventListener("scroll", maybeFetchNext);
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, threshold]);

  return anchorRef;
}
