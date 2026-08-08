import { ClerkProvider } from "@clerk/clerk-react";
import { CLERK_PUBLISHABLE_KEY, isClerkConfigured } from "../../lib/clerk";

/**
 * Mounts <ClerkProvider> only when a valid publishable key is present.
 *
 * When it isn't, children render with no auth provider at all. That is the
 * whole point: Clerk throws on an invalid key, and because the provider sits
 * above the router, that throw blanked the entire app. No provider means the
 * marketing site and the app still render, just without sign-in.
 */
export function AuthProvider({ children }) {
  if (!isClerkConfigured) return children;

  return (
    <ClerkProvider
      publishableKey={CLERK_PUBLISHABLE_KEY}
      afterSignOutUrl="/"
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
    >
      {children}
    </ClerkProvider>
  );
}

export default AuthProvider;
