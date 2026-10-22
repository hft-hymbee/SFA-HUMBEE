/**
 * Shared ESLint flat config for the Humbee monorepo.
 *
 * Status: scaffold. Plugin dependencies (typescript-eslint, eslint-plugin-react-hooks,
 * eslint-config-next) are added in Phase 1/2 when `apps/web` adopts TypeScript.
 * See docs/architecture/target-architecture.md §4.
 */

import adherence from './adherence.js';

/** Files that are never linted. */
export const ignores = [
  '**/node_modules/**',
  '**/.next/**',
  '**/out/**',
  '**/dist/**',
  '**/build/**',
  // Generated artifacts — never hand-edited, never linted.
  'archive/**',
  'packages/api-contract/src/**',
  'packages/api-contract/openapi.json',
];

/**
 * Base config: adherence rules plus repo-wide ignores.
 * Apps extend this and add their own framework config.
 */
export default [{ ignores }, adherence];
