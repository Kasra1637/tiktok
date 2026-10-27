import { Link } from "react-router-dom";
import { ArrowLeft, Sparkles } from "lucide-react";

/**
 * Shared chrome for the standalone legal pages (Privacy, Terms).
 *
 * These routes render outside AppShell, so they carry their own background,
 * back-link, masthead and footer. Extracting the wrapper keeps the two pages
 * visually identical and leaves each page file as pure prose content.
 */
export function LegalPage({ title, updated, children }) {
  return (
    <div className="relative min-h-screen hero-wash">
      <div className="noise-overlay" />

      <div className="relative z-10 mx-auto max-w-3xl px-5 py-10">
        <div className="mb-8 flex items-center justify-between gap-4">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-xl border border-[color:var(--hairline)] bg-card/50 px-3 py-2 text-sm font-normal text-muted-foreground backdrop-blur-sm transition-colors hover:border-[color:var(--indigo-35)] hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to home
          </Link>
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white">
              <Sparkles className="h-3.5 w-3.5" />
            </span>
            <span className="font-display text-sm font-semibold tracking-tight">HookForge</span>
          </Link>
        </div>

        <header className="mb-9">
          <span className="eyebrow">Legal</span>
          <h1 className="font-display mt-1.5 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
          <p className="mt-2 text-sm text-muted-foreground">Last updated: {updated}</p>
        </header>

        {/* `legal-prose` (defined below) styles the raw section/h2/ul/li markup
            so each page body stays free of repetitive utility classes. */}
        <div className="legal-prose space-y-8">{children}</div>

        <footer className="mt-14 flex flex-col items-center justify-between gap-3 border-t border-[color:var(--hairline)] pt-6 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} HookForge
          </p>
          <div className="flex items-center gap-5 text-xs text-muted-foreground">
            <Link to="/privacy" className="transition-colors hover:text-foreground">Privacy Policy</Link>
            <Link to="/terms" className="transition-colors hover:text-foreground">Terms of Service</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}

/** One numbered clause block. */
export function LegalSection({ number, title, children }) {
  return (
    <section className="scroll-mt-8">
      <h2 className="font-display flex items-baseline gap-2.5 text-base font-semibold tracking-tight">
        <span className="font-mono text-xs font-semibold text-[color:var(--brand-indigo)]">
          {String(number).padStart(2, "0")}
        </span>
        {title}
      </h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

/** Sub-heading inside a clause. */
export function LegalSubheading({ children }) {
  return <h3 className="text-xs font-semibold text-foreground">{children}</h3>;
}

/** Bulleted list with brand-colored markers. */
export function LegalList({ children }) {
  return <ul className="space-y-2">{children}</ul>;
}

export function LegalItem({ children }) {
  return (
    <li className="flex items-start gap-2.5">
      <span
        aria-hidden="true"
        className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[color:var(--indigo-45)]"
      />
      <span className="leading-relaxed">{children}</span>
    </li>
  );
}

export default LegalPage;
