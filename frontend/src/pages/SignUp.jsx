import { SignUp as ClerkSignUp } from "@clerk/clerk-react";
import { Link } from "react-router-dom";
import { Sparkles, ArrowLeft } from "lucide-react";
import { isClerkConfigured } from "../lib/clerk";

/**
 * Sign-up page. Same pattern as SignIn — Clerk handles the full flow, we
 * provide the brand wrapper.
 */
export default function SignUp() {
  return (
    <div className="relative min-h-screen hero-wash">
      <div className="noise-overlay" />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-12">
        {/* Compact brand header */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white shadow-[var(--glow-indigo)]">
              <Sparkles className="h-5 w-5" />
              <span className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-b from-white/25 to-transparent" />
            </span>
            <span className="font-display text-2xl font-semibold tracking-tight">HookForge</span>
          </Link>
          <p className="text-sm text-muted-foreground">Create your account to get started.</p>
        </div>

        {!isClerkConfigured ? (
          <div className="surface-solid w-full max-w-[400px] rounded-2xl text-center">
            <p className="font-display text-sm font-semibold">Authentication isn&apos;t configured</p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Set <code className="font-mono">REACT_APP_CLERK_PUBLISHABLE_KEY</code> at build time.
              This enables sign up; until then, the app runs without accounts.
            </p>
            <Link
              to="/"
              className="mt-4 inline-flex text-xs font-semibold text-[color:var(--brand-indigo)] hover:underline"
            >
              Continue to the app
            </Link>
          </div>
        ) : (
        <ClerkSignUp
          routing="path"
          path="/sign-up"
          signInUrl="/sign-in"
          appearance={{
            elements: {
              rootBox: "mx-auto w-full max-w-[400px]",
              card: "surface-solid rounded-2xl border border-[color:var(--hairline)] shadow-[var(--shadow-xl)] !bg-card",
              headerTitle: "font-display",
              headerSubtitle: "text-muted-foreground",
              socialButtonsBlockButton: "rounded-xl border-[color:var(--hairline)] bg-secondary/40 hover:bg-secondary transition-colors",
              formButtonPrimary: "rounded-xl bg-[color:var(--brand-indigo)] hover:bg-[color:var(--brand-indigo-dark)] shadow-[var(--glow-indigo)]",
              formFieldInput: "rounded-xl border-[color:var(--hairline)] bg-secondary/40 focus:border-[color:var(--indigo-35)]",
              footerActionLink: "text-[color:var(--brand-indigo)] hover:text-[color:var(--brand-indigo-dark)]",
              identityPreviewEditButton: "text-[color:var(--brand-indigo)]",
            },
          }}
        />
        )}

        <Link
          to="/"
          className="mt-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to home
        </Link>
      </div>
    </div>
  );
}
