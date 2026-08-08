import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Loader2, Link2, Menu, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, getErrorMessage } from "../lib/api";
import Sidebar, { MobileSidebar, NAV_GROUPS } from "./Sidebar";

const SIDEBAR_COLLAPSED_KEY = "hookforge_sidebar_collapsed";
const SIDEBAR_W = 264;
const SIDEBAR_W_COLLAPSED = 76;

/** Flat lookup for the current route's label, shown in the top bar. */
const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function currentPageLabel(pathname) {
  const match = NAV_ITEMS.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
  if (match) return match.label;
  if (pathname.startsWith("/analysis/")) return "Hook Analysis";
  if (pathname.startsWith("/generate-video/")) return "Content Remixer";
  return "Workspace";
}

export function AppShell({ children }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    try {
      const video = await api.ingestVideo(url.trim());
      setUrl("");
      navigate(`/analysis/${video.id}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

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
  // OUTSIDE this subtree (the onboarding tour's help button, which lives in
  // OnboardingProvider, an ancestor) can offset itself and not sit underneath
  // the panel. Reset to 0 on unmount so the Landing/legal pages — which have
  // no sidebar — get the full viewport back.
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
      <Sidebar collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />
      <MobileSidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

      <div
        className="flex min-h-screen flex-col transition-[padding] duration-300 ease-out-expo lg:pl-[var(--sb-w)]"
      >
        {/* ---------- Top utility bar ----------
            Holds the global TikTok-URL ingest form that used to live in the
            old top navbar. Navigation itself has moved to the sidebar. */}
        <header className="sticky top-0 z-20 border-b border-[color:var(--hairline)] bg-[hsl(228_14%_7%_/_0.78)] backdrop-blur-xl">
          <div className="mx-auto flex h-auto w-full max-w-[1400px] flex-col gap-2 px-4 py-2.5 md:h-[60px] md:flex-row md:items-center md:gap-4 md:py-0 md:px-6 lg:px-8">
            <div className="flex items-center gap-2 md:shrink-0">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
                data-testid="mobile-nav-toggle"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[color:var(--hairline)] text-muted-foreground transition-colors hover:text-foreground lg:hidden"
              >
                <Menu className="h-4 w-4" />
              </button>

              {/* Compact wordmark for small screens, where the sidebar
                  (and therefore the full logo) is off-canvas. */}
              <span className="flex items-center gap-2 lg:hidden">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--brand-teal)] to-[color:var(--brand-teal-dark)] text-white">
                  <Sparkles className="h-3.5 w-3.5" />
                </span>
                <span className="font-display text-sm font-bold tracking-tight">HookForge</span>
              </span>

              <span className="hidden items-center gap-2 lg:flex">
                <span className="eyebrow">{currentPageLabel(location.pathname)}</span>
              </span>
            </div>

            <form
              onSubmit={handleSubmit}
              className="flex flex-1 items-center gap-2 md:justify-end"
              role="search"
            >
              <label htmlFor="tiktok-url-input" className="sr-only">
                Paste a TikTok video URL to analyze
              </label>
              <div className="relative flex-1 md:max-w-md">
                <Link2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="tiktok-url-input"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Paste a TikTok video URL to analyze..."
                  className="h-9 rounded-xl border-[color:var(--hairline)] bg-secondary/70 pl-9 text-sm transition-colors focus-visible:border-[color:var(--indigo-35)] focus-visible:bg-secondary"
                  data-testid="tiktok-url-input"
                />
              </div>
              <Button
                type="submit"
                disabled={loading}
                data-testid="tiktok-url-submit-button"
                className="h-9 shrink-0 rounded-xl bg-[color:var(--brand-coral)] px-4 font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c]"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Analyze"}
              </Button>
            </form>
          </div>
        </header>

        <main className="relative z-10 mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-6 md:py-8 lg:px-8">
          {children}
        </main>
      </div>

      {/* Build stamp — visual proof of which deploy is live. If this doesn't
          match the latest commit's build stamp, Render served a stale/cached
          build and needs a forced redeploy (see Dockerfile BUILD_STAMP). */}
      <div
        className="pointer-events-none fixed bottom-2 right-2 z-50 select-none rounded-full bg-black/70 px-2.5 py-1 font-mono text-[9px] text-white/60"
        data-testid="build-stamp"
        title="Build version — confirms the deployed frontend matches the latest source"
      >
        build:hookflow-v2
      </div>
    </div>
  );
}

export default AppShell;
