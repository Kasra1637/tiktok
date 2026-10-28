import { Link } from "react-router-dom";
import {
  AuthedOnly,
  UnauthedOnly,
  SignInTrigger,
  SignUpTrigger,
  AccountButton,
} from "./auth/AuthControls";
import { Sparkles, Zap, Film, Wand2 } from "lucide-react";
import { Button } from "./ui/button";

/**
 * Shared chrome for the public marketing pages (Landing, Features).
 *
 * Both render outside AppShell, so each used to carry its own copy of the
 * sticky header, the uppercase pill, the closing sign-up CTA and the
 * footer — four blocks drifting independently. One module owns them now;
 * pages pass content (nav links, footer links, CTA variant) as props and
 * keep their own sections. Stateless: props in, markup out.
 *
 * Marketing shares the app weights (normal/semibold) and xs/sm/base, plus
 * the display ladder 2xl-6xl for editorial headings — pinned by the
 * marketing display-scale smoke check, not an exemption.
 */

/**
 * The one uppercase pill on the marketing pages: 12px semibold, tracked,
 * brand-indigo on indigo. `strong` is the same pill at one step deeper
 * border and fill, for text sitting on glass rather than on the page.
 */
export function EyebrowPill({ strong = false, className, children }) {
  return (
    <span
      className={`eyebrow eyebrow-accent inline-flex items-center gap-1.5 rounded-full border px-3 py-1 ${
        strong
          ? "border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)]"
          : "border-[color:var(--hairline)] bg-[color:var(--indigo-6)]"
      }${className ? ` ${className}` : ""}`}
    >
      {children}
    </span>
  );
}

/**
 * Sticky public header: logo home, one nav row, sign-in / account cluster.
 * Each link is `{ to, label }` for a router link or `{ href, label }` for
 * an in-page anchor — Landing mixes a /features link with section anchors,
 * Features mixes a Home link with row anchors.
 */
export function MarketingHeader({ navLabel, links }) {
  return (
    <header className="sticky top-0 z-30 border-b border-[color:var(--hairline)] bg-[hsl(228_14%_7%_/_0.72)] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white shadow-[var(--glow-indigo)]">
            <Sparkles className="h-[18px] w-[18px]" />
            <span className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-b from-white/25 to-transparent" />
          </span>
          <span className="font-display text-base font-semibold tracking-tight">HookForge</span>
        </Link>

        <nav aria-label={navLabel} className="ml-auto hidden items-center gap-1 lg:flex">
          {links.map((l) =>
            l.to ? (
              <Link
                key={l.to + l.label}
                to={l.to}
                className="rounded-lg px-3 py-2 text-sm font-normal text-muted-foreground transition-colors hover:bg-[color:var(--indigo-6)] hover:text-foreground"
              >
                {l.label}
              </Link>
            ) : (
              <a
                key={l.href}
                href={l.href}
                className="rounded-lg px-3 py-2 text-sm font-normal text-muted-foreground transition-colors hover:bg-[color:var(--indigo-6)] hover:text-foreground"
              >
                {l.label}
              </a>
            )
          )}
        </nav>

        <div className="ml-3 flex shrink-0 items-center gap-2 lg:ml-5">
          <UnauthedOnly>
            <SignInTrigger>
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
                Sign In
              </Button>
            </SignInTrigger>
          </UnauthedOnly>
          <AuthedOnly>
            <AccountButton />
          </AuthedOnly>
        </div>
      </div>
    </header>
  );
}

/**
 * The one closing ask. `secondary` adds the outline Demo + CTA action
 * (Landing); without it the CTA is the single sign-up action (Features).
 */
export function FinalCta({ testId, secondary = false }) {
  return (
    <section className="relative z-10 mx-auto max-w-4xl px-5 pb-24" data-testid={testId}>
      <div className="border-gradient relative rounded-3xl p-[1px]">
        <div className="surface-glass relative overflow-hidden rounded-3xl px-6 py-12 text-center sm:px-12 sm:py-16">
          <div className="spotlight-indigo absolute inset-0" aria-hidden="true" />
          <div className="relative">
            <EyebrowPill strong>
              <Zap className="h-3 w-3" /> Ready when you are
            </EyebrowPill>
            <h2 className="font-display mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
              Make your next app story.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
              Start with your app&apos;s facts and a message you want to share. Review the script,
              generate your Hook + Story, and keep the real product at the heart of your demo.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3.5 sm:flex-row">
              <UnauthedOnly>
                <SignUpTrigger>
                  <Button
                    variant="accent"
                    size="lg"
                    className="w-full gap-2.5 px-9 sm:w-auto"
                  >
                    <Sparkles className="h-4 w-4" /> Create your first video
                  </Button>
                </SignUpTrigger>
              </UnauthedOnly>
              <AuthedOnly>
                <Button
                  asChild
                  variant="accent"
                  size="lg"
                  className="w-full gap-2.5 px-9 sm:w-auto"
                >
                  <Link to="/create"><Sparkles className="h-4 w-4" /> Create Video</Link>
                </Button>
              </AuthedOnly>
              {secondary && (
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="w-full gap-2.5 px-8 sm:w-auto"
                >
                  <Link to="/demo-cta"><Film className="h-4 w-4" /> Style your own footage</Link>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/**
 * Public footer: brand block, one Product link column, Legal column.
 * The bottom rule gets its gutter from `pt-10` on a wrapper, not `mt-10`
 * on the bordered row (see the smoke check on border-t spacing).
 */
export function MarketingFooter({ productLinks, tagline = true }) {
  return (
    <footer className="relative z-10 border-t border-[color:var(--hairline)] bg-[hsl(228_14%_8%_/_0.6)] backdrop-blur-sm">
      <div className="mx-auto max-w-6xl px-5 py-12">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white">
                <Sparkles className="h-4 w-4" />
              </span>
              <span className="font-display text-base font-semibold tracking-tight">HookForge</span>
            </div>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
              App stories grounded in your product. Generate a Hook + Story, style your
              own footage, and publish on your terms.
            </p>
          </div>

          <div>
            <p className="eyebrow mb-3">Product</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {productLinks.map((l) => (
                <li key={l.to}>
                  <Link to={l.to} className="transition-colors hover:text-foreground">{l.label}</Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="eyebrow mb-3">Legal</p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>
                <Link to="/privacy" className="transition-colors hover:text-foreground">Privacy Policy</Link>
              </li>
              <li>
                <Link to="/terms" className="transition-colors hover:text-foreground">Terms of Service</Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="pt-10">
          <div className="flex flex-col items-center justify-between gap-3 border-t border-border/50 pt-6 sm:flex-row">
            <p className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} HookForge. Built for mobile-app founders and marketers.
            </p>
            {tagline && (
              <p className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <Wand2 className="h-3 w-3 text-[color:var(--brand-indigo)]" /> Your message. Your final say.
              </p>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}
