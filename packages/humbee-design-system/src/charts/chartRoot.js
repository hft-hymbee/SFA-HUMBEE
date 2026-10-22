import * as am5 from "@amcharts/amcharts5";
import AnimatedTheme from "@amcharts/amcharts5/themes/Animated";

/* Shared amCharts5 bootstrap for every Chart/ component.
   One root per mounted chart; always themed with AnimatedTheme so series draw in,
   bullets pop, and value changes tween instead of snapping. Callers own only the
   chart-building step (buildFn) and get a disposer back for their effect cleanup. */
export function mountAmChart(container, buildFn) {
  if (!container) return () => {};
  const root = am5.Root.new(container);
  root.setThemes([AnimatedTheme.new(root)]);
  // amCharts5 shows its attribution logo unless a commercial license key is
  // registered with am5.addLicense() at app startup — do that instead of
  // disposing root._logo, which would ship without the required attribution.
  buildFn(root, am5);
  return () => root.dispose();
}

/* amCharts colors are resolved at build time, so a CSS custom property string
   ("var(--primary)") has to become a real hex before am5.color can use it. */
export function resolveCssVar(value) {
  if (typeof window === "undefined" || !value?.startsWith("var(")) return value;
  const name = value.slice(4, -1).split(",")[0].trim();
  const resolved = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return resolved || "#995A00";
}

export function am5Color(value) {
  return am5.color(resolveCssVar(value));
}

/* Two-stop bevel gradient — the "depth" treatment used on every solid fill
   (columns, donut slices, treemap cells) instead of a flat color. */
export function bevelGradient(root, baseColor, { angle = 90, lighten = 0.22, darken = 0.18 } = {}) {
  const base = am5Color(baseColor);
  return am5.LinearGradient.new(root, {
    rotation: angle,
    stops: [
      { color: am5.Color.brighten(base, lighten) },
      { color: base },
      { color: am5.Color.brighten(base, -darken) },
    ],
  });
}

export function shadow(target, color = "#2F2A24", { blur = 6, opacity = 0.22, offsetY = 2 } = {}) {
  target.setAll({
    shadowColor: am5Color(color),
    shadowBlur: blur,
    shadowOpacity: opacity,
    shadowOffsetX: 0,
    shadowOffsetY: offsetY,
  });
}

export { am5 };
