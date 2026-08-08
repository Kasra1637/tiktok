import { useAuth } from "@clerk/clerk-react";
import { Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { isClerkConfigured } from "../lib/clerk";

/** The real gate — only ever rendered inside a mounted <ClerkProvider>. */
function ClerkGate({ children }) {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center hero-wash">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-[color:var(--brand-teal)]" />
          <p className="text-sm text-muted-foreground">Loading your session...</p>
        </div>
      </div>
    );
  }

  if (!isSignedIn) return <Navigate to="/sign-in" replace />;

  return children;
}

/**
 * Gates the authenticated app routes.
 *
 * When Clerk isn't configured there is no <ClerkProvider> in the tree, so
 * calling useAuth() would throw. In that case we let the request through —
 * the backend does the same thing (everything is filed under the "anonymous"
 * user), which keeps the app fully usable before auth keys are added.
 */
export function ProtectedRoute({ children }) {
  if (!isClerkConfigured) return children;
  return <ClerkGate>{children}</ClerkGate>;
}

export default ProtectedRoute;
