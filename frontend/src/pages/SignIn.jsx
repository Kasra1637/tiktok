import { SignIn as ClerkSignIn } from "@clerk/clerk-react";
import { Link } from "react-router-dom";
import { Sparkles, ArrowLeft } from "lucide-react";
import { isClerkConfigured } from "../lib/clerk";

/**
 * Sign-in page. Clerk's <SignIn /> component handles the full OAuth / email
 * flow (including TikTok once you add it as a social provider in your Clerk
 * dashboard). We just wrap it with our brand chrome so it feels native.
 */
export default function SignIn() {
  return (
    <div className="relative min-h-screen hero-wash">
      <div className="noise-overlay" />
      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-4 py-12">
        {/* Compact brand header */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[color:var(--brand-teal)] to-[color:var(--brand-teal-dark)] text-white shadow-[var(--glow-indigo)]">
              <Sparkles className="h-5 w-5" />
              <span className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-b from-white/25 to-transparent" />
            </span>
            <span className="font-display text-xl font-bold tracking-tight">HookForge</span>
          </Link>
          <p className="text-sm text-muted-foreground">Sign in to save your hooks, face swaps, and brand profile.</p>
        </div>

        {!isClerkConfigured ? (
          <div className="surface-solid w-full max-w-[400px] rounded-2xl p-6 text-center">
            <p className="font-display text-sm font-semibold">Authentication isn&apos;t configured</p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Set <code className="font-mono">REACT_APP_CLERK_PUBLISHABLE_KEY</code> at build time to
              enable sign in. Until then the app runs without accounts.
            </p>
            <Link
              to="/discover"
              className="mt-4 inline-flex text-xs font-semibold text-[color:var(--brand-teal)] hover:underline"
            >
              Continue to the app
            </Link>
          </div>
        ) : (
        <ClerkSignIn
          routing="path"
          path="/sign-in"
          signUpUrl="/sign-up"
          appearance={{
            elements: {
              rootBox: "mx-auto w-full max-w-[400px]",
              card: "surface-solid rounded-2xl border border-[color:var(--hairline)] shadow-[var(--shadow-xl)] !bg-card",
              headerTitle: "font-display",
              headerSubtitle: "text-muted-foreground",
              socialButtonsBlockButton: "rounded-xl border-[color:var(--hairline)] bg-secondary/40 hover:bg-secondary transition-colors",
              formButtonPrimary: "rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] shadow-[var(--glow-indigo)]",
              formFieldInput: "rounded-xl border-[color:var(--hairline)] bg-secondary/40 focus:border-[color:var(--indigo-35)]",
              footerActionLink: "text-[color:var(--brand-teal)] hover:text-[color:var(--brand-teal-dark)]",
              identityPreviewEditButton: "text-[color:var(--brand-teal)]",
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
