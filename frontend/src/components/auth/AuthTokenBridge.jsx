import { useEffect } from "react";
import { useAuth } from "@clerk/clerk-react";
import { setAuthTokenProvider } from "../../lib/api";
import { forgetCurrentAppId } from "../../lib/currentApp";

/**
 * Registers Clerk's session token source with the API client, and scopes
 * client-side identity lifetime to the signed-in user.
 *
 * Two jobs, one component, both requiring hooks inside <ClerkProvider>:
 *
 * 1. Token source. The axios request interceptor cannot call useAuth(), so it
 *    reads through the module slot this registers. Passing options through
 *    lets the 401 path force a fresh token with { skipCache: true }.
 *
 * 2. Identity remount. The subtree is keyed by userId, so signing out and in
 *    as someone else remounts the app instead of showing the previous user's
 *    state (or a stale empty list) to the new identity. Signing in as the
 *    same user keeps the same key and nothing remounts. On sign-out the
 *    remembered "current app" is forgotten, so the next identity never opens
 *    on the previous user's default — the resolver already guards this, but
 *    forgetting is the honest cleanup.
 */
export function AuthTokenBridge({ children }) {
  const { getToken, userId, isSignedIn } = useAuth();

  useEffect(() => {
    setAuthTokenProvider((opts) => getToken(opts));
    return () => setAuthTokenProvider(null);
  }, [getToken]);

  useEffect(() => {
    if (!isSignedIn) {
      forgetCurrentAppId();
    }
  }, [isSignedIn]);

  return <div key={userId ?? "signed-out"}>{children}</div>;
}

export default AuthTokenBridge;
