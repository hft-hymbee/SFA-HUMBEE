import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import humbeeConfig from "@humbee/eslint-config";

export default defineConfig([
  ...humbeeConfig,
  ...nextVitals,
  {
    files: ["app/**/*.{js,jsx,ts,tsx}", "src/**/*.{js,jsx,ts,tsx}"],
    rules: {
      "no-restricted-properties": [
        "error",
        {
          object: "navigator",
          property: "geolocation",
          message:
            "Use src/shared/capabilities for geolocation access, not navigator.geolocation directly.",
        },
      ],
    },
  },
  {
    files: ["src/shared/capabilities/**/*.{js,jsx,ts,tsx}"],
    rules: {
      "no-restricted-properties": "off",
    },
  },
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
  ]),
]);
