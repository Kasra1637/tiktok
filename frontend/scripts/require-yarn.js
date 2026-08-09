/* eslint-disable no-console */
/**
 * Refuse to install with npm.
 *
 * yarn.lock is the tracked lockfile and the Dockerfile installs with
 * `yarn install --frozen-lockfile`. A clean yarn install builds correctly.
 *
 * `npm install` does not. npm hoists more aggressively than yarn and lifts
 * ajv-keywords@5 to the top of node_modules next to ajv@6, which it needs to
 * be ajv@8. The install itself reports success; the failure only shows up
 * later, at build time, as:
 *
 *     Error: Cannot find module 'ajv/dist/compile/codegen'
 *     require stack: ... ajv-keywords ... schema-utils ... terser-webpack-plugin
 *
 * A yarn tree avoids this by nesting schema-utils@4's own ajv@8 and
 * ajv-keywords@5 underneath it, leaving the top-level ajv@6 for the packages
 * (eslint, fork-ts-checker) that actually want v6.
 *
 * Failing loudly here is deliberate: the alternative — pinning ajv via
 * resolutions/overrides — would force one version on every consumer and churn
 * a dependency tree that currently resolves correctly.
 */
const execPath = process.env.npm_execpath || "";
const userAgent = process.env.npm_config_user_agent || "";
const isYarn = /yarn/i.test(execPath) || /^yarn\//i.test(userAgent);

// Allow explicit escape hatch for anyone who knows what they're doing.
if (!isYarn && process.env.ALLOW_NPM_INSTALL !== "true") {
  console.error(
    [
      "",
      "  This project installs with yarn, not npm.",
      "",
      "      yarn install",
      "",
      "  yarn.lock is the tracked lockfile and the Docker image uses",
      "  `yarn install --frozen-lockfile`.",
      "",
      "  npm install appears to succeed but produces a node_modules tree where",
      "  ajv-keywords@5 is hoisted next to ajv@6 instead of ajv@8, and the",
      "  production build then fails with:",
      "",
      "      Cannot find module 'ajv/dist/compile/codegen'",
      "",
      "  Set ALLOW_NPM_INSTALL=true to bypass this check.",
      "",
    ].join("\n")
  );
  process.exit(1);
}
