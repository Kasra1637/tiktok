import { useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Sparkles, History as HistoryIcon, Loader2, Briefcase } from "lucide-react";
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

  return (
    <div className="relative min-h-screen hero-wash">
      <header className="sticky top-0 z-20 border-b border-border bg-[color:var(--card)]/90 backdrop-blur-sm">
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 lg:px-8 h-16 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 shrink-0" data-testid="logo-home-link">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[color:var(--brand-teal)] text-white">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="font-display text-lg font-semibold tracking-tight">HookForge</span>
          </Link>

          <form onSubmit={handleSubmit} className="flex-1 flex items-center gap-2 max-w-xl">
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste a TikTok video URL to analyze..."
              className="bg-white/80"
              data-testid="tiktok-url-input"
            />
            <Button type="submit" disabled={loading} data-testid="tiktok-url-submit-button" className="shrink-0 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Analyze"}
            </Button>
          </form>

          <Link
            to="/brand"
            data-testid="brand-nav-link"
            className={`flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-xl hover:bg-[color:rgba(13,148,136,0.08)] transition-colors shrink-0 ${location.pathname === "/brand" ? "text-[color:var(--brand-teal)]" : "text-foreground"}`}
          >
            <Briefcase className="h-4 w-4" /> Your Brand
          </Link>

          <Link
            to="/history"
            data-testid="history-nav-link"
            className={`flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-xl hover:bg-[color:rgba(13,148,136,0.08)] transition-colors shrink-0 ${location.pathname === "/history" ? "text-[color:var(--brand-teal)]" : "text-foreground"}`}
          >
            <HistoryIcon className="h-4 w-4" /> History
          </Link>
        </div>
      </header>
      <main className="relative z-10 max-w-[1400px] mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8">
        {children}
      </main>
    </div>
  );
}

export default AppShell;
