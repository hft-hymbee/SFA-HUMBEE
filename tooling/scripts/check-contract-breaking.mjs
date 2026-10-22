import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..", "..");
const contractPath = path.join(repoRoot, "packages", "api-contract", "openapi.json");
const changelogPath = path.join(repoRoot, "packages", "api-contract", "CHANGELOG.md");

function readJson(filePath) {
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function resolveBaseRef() {
  const baseRef = process.env.GITHUB_BASE_REF;
  if (baseRef) {
    return `origin/${baseRef}`;
  }

  try {
    execFileSync("git", ["show-ref", "--verify", "--quiet", "refs/remotes/origin/main"], {
      cwd: repoRoot,
      stdio: "ignore",
    });
    return "origin/main";
  } catch {
    return "HEAD~1";
  }
}

function readPreviousContract() {
  const baseRef = resolveBaseRef();

  try {
    const mergeBase = execFileSync("git", ["merge-base", "HEAD", baseRef], {
      cwd: repoRoot,
      encoding: "utf8",
    }).trim();

    execFileSync("git", ["cat-file", "-e", `${mergeBase}:packages/api-contract/openapi.json`], {
      cwd: repoRoot,
      stdio: "ignore",
    });

    const raw = execFileSync("git", ["show", `${mergeBase}:packages/api-contract/openapi.json`], {
      cwd: repoRoot,
      encoding: "utf8",
    });

    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function enumMembers(schema) {
  if (!schema || typeof schema !== "object") {
    return [];
  }

  if (Array.isArray(schema.enum)) {
    return schema.enum.filter((member) => typeof member === "string");
  }

  return [];
}

function collectBreaks(previous, next) {
  const breaks = [];

  const previousPaths = previous.paths ?? {};
  const nextPaths = next.paths ?? {};

  for (const endpoint of Object.keys(previousPaths)) {
    if (!(endpoint in nextPaths)) {
      breaks.push(`Removed path: ${endpoint}`);
      continue;
    }

    const previousMethods = previousPaths[endpoint] ?? {};
    const nextMethods = nextPaths[endpoint] ?? {};

    for (const method of Object.keys(previousMethods)) {
      if (!(method in nextMethods)) {
        breaks.push(`Removed operation: ${method.toUpperCase()} ${endpoint}`);
      }
    }
  }

  const previousSchemas = previous.components?.schemas ?? {};
  const nextSchemas = next.components?.schemas ?? {};

  for (const schemaName of Object.keys(previousSchemas)) {
    const previousSchema = previousSchemas[schemaName];
    const nextSchema = nextSchemas[schemaName];

    if (!nextSchema) {
      breaks.push(`Removed schema: components.schemas.${schemaName}`);
      continue;
    }

    const previousRequired = new Set(previousSchema.required ?? []);
    const nextRequired = new Set(nextSchema.required ?? []);
    for (const field of previousRequired) {
      if (!nextRequired.has(field)) {
        breaks.push(
          `Removed required field: components.schemas.${schemaName}.required includes '${field}' previously`,
        );
      }
    }

    const previousSchemaEnum = new Set(enumMembers(previousSchema));
    const nextSchemaEnum = new Set(enumMembers(nextSchema));
    for (const oldValue of previousSchemaEnum) {
      if (!nextSchemaEnum.has(oldValue)) {
        breaks.push(`Removed enum value: components.schemas.${schemaName} no longer has '${oldValue}'`);
      }
    }

    const previousProps = previousSchema.properties ?? {};
    const nextProps = nextSchema.properties ?? {};
    for (const propName of Object.keys(previousProps)) {
      if (!(propName in nextProps)) {
        continue;
      }

      const previousPropEnum = new Set(enumMembers(previousProps[propName]));
      const nextPropEnum = new Set(enumMembers(nextProps[propName]));
      for (const oldValue of previousPropEnum) {
        if (!nextPropEnum.has(oldValue)) {
          breaks.push(
            `Removed enum value: components.schemas.${schemaName}.properties.${propName} no longer has '${oldValue}'`,
          );
        }
      }
    }
  }

  return breaks;
}

function changelogHasBreakingEntry() {
  const changelog = readFileSync(changelogPath, "utf8");
  const breakingToken = /BREAKING CHANGE:/i;
  return breakingToken.test(changelog);
}

const currentContract = readJson(contractPath);
const previousContract = readPreviousContract();

if (!previousContract) {
  console.log("No prior contract artifact found in git history; skipping breaking-change gate.");
  process.exit(0);
}

const breakingChanges = collectBreaks(previousContract, currentContract);
if (breakingChanges.length === 0) {
  console.log("No breaking API changes detected.");
  process.exit(0);
}

if (!changelogHasBreakingEntry()) {
  console.error("Breaking API changes detected without CHANGELOG entry.");
  for (const item of breakingChanges) {
    console.error(`- ${item}`);
  }
  console.error("Add a 'BREAKING CHANGE:' note to packages/api-contract/CHANGELOG.md.");
  process.exit(1);
}

console.log("Breaking API changes detected and CHANGELOG contains BREAKING CHANGE entry.");
