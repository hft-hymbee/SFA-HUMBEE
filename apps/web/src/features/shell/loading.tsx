"use client";

import { Skeleton, SkeletonRow } from "humbee-design-system";
import type { CSSProperties } from "react";

export function SpPageSkeleton({
  rows = 3,
  withCard = true,
  className = "sp-content",
  style,
}: {
  rows?: number;
  withCard?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={className} style={style}>
      <Skeleton width="42%" height={16} />
      <div className="sp-list">
        {Array.from({ length: rows }).map((_, index) => <SkeletonRow key={index} />)}
      </div>
      {withCard ? <Skeleton height={88} radius={12} /> : null}
    </div>
  );
}

export function SpListSkeleton({
  rows = 3,
  className = "sp-list",
  style,
}: {
  rows?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div className={className} style={style}>
      {Array.from({ length: rows }).map((_, index) => <SkeletonRow key={index} />)}
    </div>
  );
}

export function SpInlineSkeleton({
  width = "48%",
  height = 14,
}: {
  width?: CSSProperties["width"];
  height?: number;
}) {
  return <Skeleton width={width} height={height} />;
}

export function SpFieldSkeleton({
  labelWidth = "34%",
  inputHeight = 44,
}: {
  labelWidth?: CSSProperties["width"];
  inputHeight?: number;
}) {
  return (
    <div className="sp-stack" style={{ gap: "var(--space-xs)" }}>
      <Skeleton width={labelWidth} height={12} />
      <Skeleton width="100%" height={inputHeight} radius={10} />
    </div>
  );
}
