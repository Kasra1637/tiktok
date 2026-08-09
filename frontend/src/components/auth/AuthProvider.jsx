import { ClerkProvider } from "@clerk/clerk-react";
import { CLERK_PUBLISHABLE_KEY, isClerkConfigured } from "../../lib/clerk";

/**
 * Global Clerk appearance — applied to every modal, form, and user button.
 * Sets a dark background and HookForge's brand palette (indigo primary, dark
 * surfaces, 12px radius). We define everything via `variables` so it works
 * without importing @clerk/themes (which is ESM-only and breaks CRA's build).
 */
const clerkAppearance = {
  variables: {
    // Brand colors
    colorPrimary: "#818CF8",           // --brand-indigo (indigo-400)
    colorDanger: "#FE2C55",            // --brand-coral
    colorSuccess: "#10B981",           // emerald-500
    colorWarning: "#F59E0B",           // amber-500
    colorTextOnPrimaryBackground: "#FFFFFF",

    // Surfaces — match the app's dark card layer
    colorBackground: "hsl(228, 14%, 10%)",          // --card
    colorInputBackground: "hsl(228, 12%, 14%)",     // --muted
    colorInputText: "hsl(220, 20%, 93%)",           // --foreground
    colorText: "hsl(220, 20%, 93%)",                // --foreground
    colorTextSecondary: "hsl(220, 10%, 55%)",       // --muted-foreground
    colorNeutral: "hsl(220, 20%, 93%)",             // text color in dark mode

    // Typography
    fontFamily: '"Figtree", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontFamilyButtons: '"Figtree", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',

    // Geometry
    borderRadius: "0.75rem",           // --radius (12px)
    spacingUnit: "4px",
  },
  elements: {
    // Modal overlay
    modalBackdrop: "bg-black/70 backdrop-blur-sm",

    // Card (the popup itself)
    card: "border border-[hsl(228,12%,17%)] shadow-[0_8px_16px_rgba(0,0,0,0.3),0_32px_72px_rgba(0,0,0,0.45)] !bg-[hsl(228,14%,10%)]",
    rootBox: "font-sans",

    // Header
    headerTitle: "font-display font-semibold tracking-tight",
    headerSubtitle: "text-[hsl(220,10%,55%)]",

    // Social / OAuth buttons
    socialButtonsBlockButton:
      "!rounded-xl !border-[hsl(228,12%,17%)] !bg-[hsl(228,12%,16%)] hover:!bg-[hsl(228,12%,20%)] transition-colors font-medium",
    socialButtonsBlockButtonText: "font-medium !text-[hsl(220,20%,93%)]",

    // Primary action button
    formButtonPrimary:
      "!rounded-xl !bg-[#818CF8] hover:!bg-[#6366F1] !shadow-[0_0_0_1px_rgba(129,140,248,0.25),0_8px_28px_rgba(99,102,241,0.28)] font-semibold transition-colors",

    // Input fields
    formFieldInput:
      "!rounded-xl !border-[hsl(228,12%,17%)] !bg-[hsl(228,12%,14%)] focus:!border-[rgba(129,140,248,0.35)] transition-colors !text-[hsl(220,20%,93%)]",
    formFieldLabel: "font-medium text-sm !text-[hsl(220,20%,85%)]",

    // Footer links
    footerActionLink:
      "!text-[#818CF8] hover:!text-[#6366F1] font-medium",

    // Divider
    dividerLine: "!bg-[hsl(228,12%,17%)]",
    dividerText: "!text-[hsl(220,10%,55%)]",

    // User button (avatar in sidebar)
    userButtonAvatarBox: "rounded-lg",
    userButtonPopoverCard: "!border-[hsl(228,12%,17%)] !bg-[hsl(228,14%,10%)] !shadow-[0_8px_16px_rgba(0,0,0,0.3),0_32px_72px_rgba(0,0,0,0.45)]",
  },
};

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
      appearance={clerkAppearance}
    >
      {children}
    </ClerkProvider>
  );
}

export default AuthProvider;
