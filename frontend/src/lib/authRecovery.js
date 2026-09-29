/**
 * The rules for what happens after a 401, kept pure so they can be asserted.
 *
 * Why this file exists: a 401 used to fall through to whatever `.catch(() =>
 * setX([]))` the page had, so a dead session rendered as "no apps" — a
 * profile that exists looked deleted. The interceptor in lib/api.js now
 * retries once with a forced-fresh token; these two predicates decide the two
 * branches around that retry. Getting either wrong fails loudly in the worst
 * way: retrying forever loops requests, and redirecting unconditionally
 * bounces marketing visitors (or a misconfigured no-auth deploy) into
 * sign-in. Both invariants are pinned in scripts/check-frontend-logic.cjs.
 */

/** Pages where sending the user to sign-in is never the answer. */
export function isAuthPage(pathname) {
  return /^\/(sign-in|sign-up)/.test(typeof pathname === "string" ? pathname : "");
}

/**
 * Whether a failed request deserves one retry with a forced-fresh token.
 * Only a first-time 401 qualifies: anything else, or an already-retried
 * request, must reject so errors keep flowing to the caller.
 */
export function shouldRetryWithFreshToken({ status, alreadyRetried } = {}) {
  return status === 401 && !alreadyRetried;
}

/**
 * Whether a still-failing request means the session is dead and the user
 * belongs on /sign-in. All three must hold:
 *
 * - attemptedAuth: the request actually carried credentials. A 401 on a
 *   credential-less request (public endpoint, no-auth mode) is a backend
 *   problem, not a dead session — redirecting then would bounce a marketing
 *   visitor to sign-in.
 * - clerkConfigured: without Clerk there is no sign-in to go to; redirecting
 *   would loop a misconfigured deploy into a page that cannot help.
 * - not already on an auth page: redirecting from /sign-in to /sign-in is a
 *   reload loop wearing a trench coat.
 */
export function shouldForceSignIn({ attemptedAuth, clerkConfigured, pathname } = {}) {
  if (!attemptedAuth) return false;
  if (!clerkConfigured) return false;
  if (isAuthPage(pathname)) return false;
  return true;
}
