/**
 * Clerk configuration and availability check.
 *
 * CRA inlines `process.env.REACT_APP_*` at BUILD time, so a deploy that was
 * built without the key will never have it at runtime. Passing a fake
 * placeholder key to <ClerkProvider> makes Clerk throw
 * ("The publishableKey passed to Clerk is invalid"), which unmounts the whole
 * React tree and leaves a blank page. So we validate the key up front and
 * simply don't mount Clerk when it's absent or malformed — the app then runs
 * in "no-auth" mode, which mirrors the backend's own fallback (it treats
 * unauthenticated requests as user "anonymous" when CLERK_JWKS_URL is unset).
 */

export const CLERK_PUBLISHABLE_KEY = (process.env.REACT_APP_CLERK_PUBLISHABLE_KEY || "").trim();

/**
 * A real Clerk publishable key looks like `pk_test_<base64>` or
 * `pk_live_<base64>` and is comfortably longer than 20 chars. This rejects
 * empty strings, the old hardcoded placeholder, and obvious typos before they
 * can reach Clerk and blow up the render.
 */
export function isValidClerkKey(key) {
  if (!key) return false;
  if (!/^pk_(test|live)_/.test(key)) return false;
  if (key.length < 24) return false;
  if (key.includes("placeholder") || key.includes("your_key") || key.includes("xxx")) return false;
  return true;
}

export const isClerkConfigured = isValidClerkKey(CLERK_PUBLISHABLE_KEY);

if (!isClerkConfigured) {
  // Loud, actionable warning — this is the #1 cause of "the app is blank".
  console.warn(
    "[HookForge] Clerk is not configured, running in no-auth mode.\n" +
    "  Sign-in/sign-up are disabled and all data is stored under the shared\n" +
    "  \"anonymous\" user.\n\n" +
    "  To enable authentication, set REACT_APP_CLERK_PUBLISHABLE_KEY at BUILD\n" +
    "  time (CRA inlines it into the bundle):\n" +
    "    • Local:  add it to frontend/.env then restart/rebuild\n" +
    "    • Docker: pass --build-arg REACT_APP_CLERK_PUBLISHABLE_KEY=pk_...\n" +
    "    • Render: add it as an Environment Variable, then redeploy\n\n" +
    "  Get the key from https://dashboard.clerk.com -> API Keys."
  );
}
