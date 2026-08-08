import { Link } from "react-router-dom";
import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/clerk-react";
import { isClerkConfigured } from "../../lib/clerk";

/**
 * Thin wrappers around Clerk's UI primitives.
 *
 * Clerk's components throw when rendered outside a <ClerkProvider>, and we
 * intentionally don't mount that provider when no key is configured. These
 * wrappers keep every page free of `isClerkConfigured` branching and make the
 * no-auth fallback behave sensibly:
 *
 *   no-auth mode  ->  treat the visitor as signed in (matches the backend,
 *                     which files everything under the "anonymous" user), so
 *                     the app is fully usable while Clerk is unconfigured.
 */

/** Renders children only for signed-in users (always, in no-auth mode). */
export function AuthedOnly({ children }) {
  if (!isClerkConfigured) return children;
  return <SignedIn>{children}</SignedIn>;
}

/** Renders children only for signed-out users (never, in no-auth mode). */
export function UnauthedOnly({ children }) {
  if (!isClerkConfigured) return null;
  return <SignedOut>{children}</SignedOut>;
}

/**
 * Opens Clerk's sign-in modal. `children` must be a single clickable element.
 * Falls back to a plain link into the app when Clerk isn't configured.
 */
export function SignInTrigger({ children, fallbackTo = "/discover" }) {
  if (!isClerkConfigured) {
    return <Link to={fallbackTo}>{children}</Link>;
  }
  return <SignInButton mode="modal">{children}</SignInButton>;
}

/** Opens Clerk's sign-up modal. Same fallback behaviour as SignInTrigger. */
export function SignUpTrigger({ children, fallbackTo = "/discover" }) {
  if (!isClerkConfigured) {
    return <Link to={fallbackTo}>{children}</Link>;
  }
  return <SignUpButton mode="modal">{children}</SignUpButton>;
}

/** Avatar + account menu. Renders nothing when Clerk isn't configured. */
export function AccountButton({ appearance }) {
  if (!isClerkConfigured) return null;
  return <UserButton afterSignOutUrl="/" appearance={appearance} />;
}
