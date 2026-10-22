import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS from "openapi-typescript";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..", "..");
const openapiPath = path.join(repoRoot, "packages", "api-contract", "openapi.json");
const outputDir = path.join(repoRoot, "packages", "api-contract", "src");
const outputPath = path.join(outputDir, "generated-types.d.ts");

const rawSpec = await readFile(openapiPath, "utf8");
const schema = JSON.parse(rawSpec);
const generatedTypes = await openapiTS(schema);

await mkdir(outputDir, { recursive: true });
await writeFile(
  outputPath,
  [
    "/* eslint-disable */",
    "/**",
    " * GENERATED FILE - DO NOT EDIT BY HAND.",
    " * Regenerate via: pnpm --filter @humbee/api-contract run generate",
    " */",
    "",
    generatedTypes.trimEnd(),
    "",
  ].join("\n"),
  "utf8",
);

console.log(`Wrote generated API types: ${outputPath}`);
