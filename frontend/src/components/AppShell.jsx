import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Menu, Sparkles } from "lucide-react";
import Sidebar, { MobileSidebar } from "./Sidebar";

const SIDEBAR_COLLAPSED_KEY = "hookforge_sidebar_collapsed";
const SIDEBAR_W = 264;
const SIDEBAR_W_COLLAPSED = 76;

const SHOW_BUILD_STAMP =
  process.env.NODE_ENV !== "production" ||
  process.env.REACT_APP_SHOW_BUILD_STAMP === "true";

export function AppShell({ children }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const location = useLocation();

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const nextValue = !prev;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, nextValue ? "1" : "0");
      } catch {
        // Storage unavailable (private mode) — the preference just won't persist.
      }
      return nextValue;
    });
  };

  // Publish the live sidebar width on :root so fixed-position chrome rendered
  // OUTSIDE this subtree can offset itself and not sit underneath the panel.
  // Reset to 0 on unmount so the Landing/legal pages — which have no sidebar —
  // get the full viewport back.
  useEffect(() => {
    const width = collapsed ? SIDEBAR_W_COLLAPSED : SIDEBAR_W;
    document.documentElement.style.setProperty("--app-sidebar-w", `${width}px`);
    return () => {
      document.documentElement.style.setProperty("--app-sidebar-w", "0px");
    };
  }, [collapsed]);

  // Close the mobile drawer on navigation so it never covers the page the
  // user just asked for.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  // Escape closes the drawer. Registered only while it's open so the tour
  // overlay's own Escape handler stays unaffected the rest of the time.
  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  return (
    <div
      className="relative min-h-screen hero-wash"
      style={{ "--sb-w": collapsed ? `${SIDEBAR_W_COLLAPSED}px` : `${SIDEBAR_W}px` }}
    >
      {/* Skip link: without it keyboard users tab through the whole sidebar on every page before reaching the content. Visible only on focus. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-[color:var(--brand-indigo)] focus:px-4 focus:py-2 focus:text-sm focus:text-white"
      >
        Skip to content
      </a>
      <Sidebar collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />
      <MobileSidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

      <div
        className="flex min-h-screen flex-col transition-[padding] duration-300 ease-out-expo lg:pl-[var(--sb-w)]"
      >
        {/* Mobile-only top strip: hamburger + wordmark. Hidden on desktop
            where the full sidebar is always visible. */}
        <div className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-[color:var(--hairline)] bg-[hsl(228_14%_7%_/_0.78)] px-4 backdrop-blur-xl lg:hidden">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation"
            data-testid="mobile-nav-toggle"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[color:var(--hairline)] text-muted-foreground transition-colors hover:text-foreground"
          >
            <Menu className="h-4 w-4" />
          </button>
          <span className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white">
              <Sparkles className="h-3.5 w-3.5" />
            </span>
            <span className="font-display text-sm font-semibold tracking-tight">HookForge</span>
          </span>
        </div>

        <main id="main-content" tabIndex={-1} className="relative z-10 mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 outline-none md:px-6 md:py-8 lg:px-8">
          {children}
        </main>
      </div>

      {/* Build stamp — visual proof of which deploy is live.
          Hidden in production builds: it is fixed to the bottom-right corner
          and was overlapping real page content (e.g. empty-state copy on
          Discover at narrow widths). Still available where it's actually
          useful — always in development, and in a production build when
          REACT_APP_SHOW_BUILD_STAMP=true is set at build time to verify a
          deploy. CRA inlines both values, so this branch is dead-code
          eliminated from the normal production bundle. */}
      {SHOW_BUILD_STAMP && (
        <div
          className="pointer-events-none fixed bottom-2 right-2 z-50 select-none rounded-full bg-black/70 px-2.5 py-1 font-mono text-xs text-white/75"
          data-testid="build-stamp"
          title="Build version — confirms the deployed frontend matches the latest source"
        >
          build:hookflow-v2
        </div>
      )}
    </div>
  );
}

export default AppShell;
