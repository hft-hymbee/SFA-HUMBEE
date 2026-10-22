import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const prototypeConfigPath = path.resolve(
  fileURLToPath(new URL("../../apps/sfa-prototype/_adherence.oxlintrc.json", import.meta.url)),
);

function withErrorSeverity(ruleValue, fallback) {
  if (!Array.isArray(ruleValue) || ruleValue.length === 0) {
    return fallback;
  }

  const [, ...rest] = ruleValue;
  return ["error", ...rest];
}

function loadPrototypeRules() {
  try {
    const raw = readFileSync(prototypeConfigPath, "utf8");
    const parsed = JSON.parse(raw);
    return parsed?.rules ?? {};
  } catch {
    return {};
  }
}

const prototypeRules = loadPrototypeRules();

const fallbackRestrictedSyntax = [
  "error",
  {
    selector: "Literal[value=/#[0-9a-fA-F]{3,8}\\b/]",
    message:
      "Raw hex colour — use a design-system colour token via var(--…). See @humbee/design-tokens.",
  },
  {
    selector: "Literal[value=/\\b\\d+px\\b/]",
    message:
      "Raw px value — use a design-system spacing/radius token via var(--…). See @humbee/design-tokens.",
  },
  {
    selector: "Literal[value=/font-family\\s*:\\s*(?!['\\\"]?(?:Lato))/i]",
    message: "Font not provided by the design system. Available: Lato.",
  },
];

const fallbackRestrictedImports = [
  "error",
  {
    patterns: [
      {
        group: [
          "humbee-design-system/src/*",
          "humbee-design-system/humbee-design-system/*",
          "@humbee/design-system/src/*",
        ],
        message:
          "Import design-system components from the package barrel ('humbee-design-system'), not component internals.",
      },
    ],
  },
];

/**
 * Full adherence payload from the prototype, including per-component prop and literal-value checks.
 * The source of truth is still `_adherence.oxlintrc.json`; this package consumes it directly so
 * `apps/web` and `apps/sfa-prototype` enforce the same component contracts.
 */
export const tokenAdherenceRules = {
  "no-restricted-syntax": withErrorSeverity(
    prototypeRules["no-restricted-syntax"],
    fallbackRestrictedSyntax,
  ),
};

export const importBoundaryRules = {
  "no-restricted-imports": withErrorSeverity(
    prototypeRules["no-restricted-imports"],
    fallbackRestrictedImports,
  ),
};

export default {
  name: "humbee/adherence",
  rules: {
    ...tokenAdherenceRules,
    ...importBoundaryRules,
  },
};
