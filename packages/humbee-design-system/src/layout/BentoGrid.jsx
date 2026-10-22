import React from "react";

/* Humbee BentoGrid — ported from Bento/BentoBoxGrid.js.
   Dashboard grid. masonry=true → CSS columns; masonry=false → CSS grid with colSpan-aware items. */
export function BentoGrid({ children, gap = 2, column = 3, masonry = false, style, ...rest }) {
  const gapPx = gap * 8;
  if (masonry) {
    return (
      <div style={{ columnCount: column, columnGap: gapPx, width: "100%", ...style }} {...rest}>
        {React.Children.map(children, (c) => c && <div style={{ breakInside: "avoid", marginBottom: gapPx }}>{c}</div>)}
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${column}, 1fr)`, gap: gapPx, alignItems: "start", width: "100%", ...style }} {...rest}>
      {children}
    </div>
  );
}

/* A single grid cell. colSpan maps to grid-column span. */
export function BentoItem({ children, colSpan = 1, style, ...rest }) {
  return (
    <div style={{ gridColumn: `span ${colSpan}`, ...style }} {...rest}>{children}</div>
  );
}

export default BentoGrid;
