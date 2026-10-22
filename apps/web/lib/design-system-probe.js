import * as DesignSystem from "humbee-design-system";
import theme from "humbee-design-system/theme";

export const designSystemExportCount = Object.keys(DesignSystem).length;
export const designSystemPrimaryColor =
  theme?.palette?.primary?.main ?? "var(--humbee-color-primary-600)";
