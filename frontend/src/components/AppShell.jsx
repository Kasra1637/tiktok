import { useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Sparkles, History as HistoryIcon, Loader2, Link2, Briefcase, Repeat2 } from "lucide-react";
import { toast } from "sonner";
import { api, getErrorMessage } from "../lib/api";

export function AppShell({ children }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
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

  const isHistory = location.pathname === "/history";
  const isBrand = location.pathname === "/brand";
  const isFaceSwap = location.pathname === "/face-swap";

  return (
    <div className="relative min-h-screen hero-wash">
      <header className="sticky top-0 z-20 border-b border-border/40 bg-background/90 backdrop-blur-md">
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 lg:px-8 py-2 md:h-14 md:py-0 flex flex-col md:flex-row md:items-center gap-2 md:gap-4">
          <div className="flex items-center justify-between md:justify-start gap-3 md:shrink-0">
            <Link to="/discover" className="flex items-center gap-1.5 shrink-0" data-testid="logo-home-link">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[color:var(--brand-teal)] text-white transition-transform hover:scale-105">
                <Sparkles className="h-3.5 w-3.5" />
              </span>
              <span className="font-display text-base font-semibold tracking-tight">HookForge</span>
            </Link>
          </div>

          <form onSubmit={handleSubmit} className="flex-1 flex items-center gap-2 md:max-w-xl" role="search">
            <label htmlFor="tiktok-url-input" className="sr-only">
              Paste a TikTok video URL to analyze
            </label>
            <div className="relative flex-1">
              <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                id="tiktok-url-input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Paste a TikTok video URL to analyze..."
                className="bg-secondary pl-9"
                data-testid="tiktok-url-input"
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              data-testid="tiktok-url-submit-button"
              className="shrink-0 bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Analyze"}
            </Button>
          </form>

          <nav className="flex items-center gap-1 shrink-0">
            <Link
              to="/face-swap"
              data-testid="face-swap-nav-link"
              aria-current={isFaceSwap ? "page" : undefined}
              className={`flex items-center gap-1.5 text-sm font-medium px-2.5 py-1.5 rounded-xl hover:bg-[color:rgba(99,102,241,0.08)] transition-colors ${
                isFaceSwap ? "text-[color:var(--brand-teal)]" : "text-foreground"
              }`}
            >
              <Repeat2 className="h-4 w-4" />
              <span className="hidden md:inline">Face Swap</span>
            </Link>

            <Link
              to="/brand"
              data-testid="brand-nav-link"
              aria-current={isBrand ? "page" : undefined}
              className={`flex items-center gap-1.5 text-sm font-medium px-2.5 py-1.5 rounded-xl hover:bg-[color:rgba(99,102,241,0.08)] transition-colors ${
                isBrand ? "text-[color:var(--brand-teal)]" : "text-foreground"
              }`}
            >
              <Briefcase className="h-4 w-4" />
              <span className="hidden md:inline">Your Brand</span>
            </Link>

            <Link
              to="/history"
              data-testid="history-nav-link"
              aria-current={isHistory ? "page" : undefined}
              className={`flex items-center gap-1.5 text-sm font-medium px-2.5 py-1.5 rounded-xl hover:bg-[color:rgba(99,102,241,0.08)] transition-colors ${
                isHistory ? "text-[color:var(--brand-teal)]" : "text-foreground"
              }`}
            >
              <HistoryIcon className="h-4 w-4" />
              <span className="hidden md:inline">History</span>
            </Link>
          </nav>
        </div>
      </header>
      <main className="relative z-10 max-w-[1400px] mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8">
        {children}
      </main>
    </div>
  );
}

export default AppShell;
