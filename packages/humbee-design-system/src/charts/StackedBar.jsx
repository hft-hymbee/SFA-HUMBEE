import React, { useEffect, useRef } from "react";
import { am5, am5Color, bevelGradient, mountAmChart, shadow } from "./chartRoot.js";
import * as am5xy from "@amcharts/amcharts5/xy";

/* Humbee StackedBar — a single 100%-stacked horizontal bar: "Visits today" on
   every dashboard, and the manager team-target pace bar. Each part grows in
   from zero on mount/update instead of snapping to width, and an optional
   reference marker (pace, a target line) sits on top. */
export function StackedBar({ parts, height = 20, referenceValue, referenceLabel, style }) {
  const elRef = useRef(null);

  useEffect(() => {
    const dispose = mountAmChart(elRef.current, (root) => {
      const total = parts.reduce((sum, part) => sum + part.value, 0) || 1;
      const chart = root.container.children.push(
        am5xy.XYChart.new(root, {
          paddingLeft: 0, paddingRight: 0, paddingTop: 0, paddingBottom: 0,
          layout: root.verticalLayout,
        }),
      );
      chart.plotContainer.set("interactiveChildren", false);

      const categoryAxis = chart.yAxes.push(
        am5xy.CategoryAxis.new(root, {
          categoryField: "row",
          renderer: am5xy.AxisRendererY.new(root, { minGridDistance: 1 }),
        }),
      );
      categoryAxis.data.setAll([{ row: "row" }]);
      categoryAxis.get("renderer").grid.template.set("forceHidden", true);
      categoryAxis.get("renderer").labels.template.set("forceHidden", true);

      const valueAxis = chart.xAxes.push(
        am5xy.ValueAxis.new(root, {
          min: 0,
          max: total,
          strictMinMax: true,
          renderer: am5xy.AxisRendererX.new(root, {}),
        }),
      );
      valueAxis.get("renderer").grid.template.set("forceHidden", true);
      valueAxis.get("renderer").labels.template.set("forceHidden", true);

      parts.forEach((part, index) => {
        const isFirst = index === 0;
        const isLast = index === parts.length - 1;
        const series = chart.series.push(
          am5xy.ColumnSeries.new(root, {
            name: part.label,
            xAxis: valueAxis,
            yAxis: categoryAxis,
            valueXField: "value",
            categoryYField: "row",
            stacked: true,
          }),
        );
        series.columns.template.setAll({
          fillGradient: bevelGradient(root, part.color, { angle: 90 }),
          strokeOpacity: part.hasBorder ? 1 : 0,
          stroke: part.hasBorder ? am5Color("var(--n-400)") : undefined,
          strokeWidth: 1,
          cornerRadiusTL: isFirst ? 4 : 2,
          cornerRadiusBL: isFirst ? 4 : 2,
          cornerRadiusTR: isLast ? 4 : 2,
          cornerRadiusBR: isLast ? 4 : 2,
          tooltipText: `${part.label}: {valueX}`,
        });
        shadow(series.columns.template, "#2F2A24", { blur: 3, opacity: 0.12, offsetY: 1 });
        series.data.setAll([{ row: "row", value: part.value }]);
        series.appear(700, 100 * index);
      });

      if (referenceValue !== undefined) {
        const rangeDataItem = valueAxis.makeDataItem({ value: referenceValue });
        const range = valueAxis.createAxisRange(rangeDataItem);
        range.get("grid")?.setAll({ stroke: am5Color("var(--ink)"), strokeOpacity: 1, strokeWidth: 2, forceHidden: false });
        if (referenceLabel) {
          range.get("label")?.setAll({
            text: referenceLabel,
            forceHidden: false,
            fill: am5Color("var(--ink)"),
            fontSize: 10,
            fontWeight: "700",
            centerX: am5.p50,
            dy: -14,
          });
        }
      }

      chart.appear(500, 0);
    });
    return dispose;
  }, [JSON.stringify(parts), referenceValue, referenceLabel]);

  return <div ref={elRef} style={{ width: "100%", height, ...style }} />;
}

export default StackedBar;
