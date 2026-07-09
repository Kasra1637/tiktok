import { Link } from "react-router-dom";
import { Sparkles, Search, Repeat2, Clapperboard, Globe, Save, Film, TrendingUp, ArrowRight, Zap, Target, Layers } from "lucide-react";
import { Button } from "../components/ui/button";

const FEATURES = [
  {
    icon: Search,
    title: "Discover Viral Hooks",
    description: "Browse 10 niches of trending TikTok videos sorted by virality score. Search by keyword or hashtag. Curated, trending, or mixed feeds.",
  },
  {
    icon: TrendingUp,
    title: "AI Hook Analysis",
    description: "Paste any TikTok URL or pick from discovery. AI extracts the first 2-3 seconds, analyzes facial expressions, gestures, pacing, text overlays, and audio cues. Gets an effectiveness score out of 10.",
  },
  {
    icon: Repeat2,
    title: "Face Swap",
    description: "Select a frame from any viral video. Your face is swapped in while keeping pose, gesture, environment, background, and clothing intact. Only the identity changes.",
  },
  {
    icon: Save,
    title: "Saved Face",
    description: "Upload your face once, it persists across sessions. Next time you select a viral video, just hit Generate — zero uploads needed.",
  },
  {
    icon: Clapperboard,
    title: "AI Video Generation",
    description: "Your swapped face becomes the first frame. Seedance 2.0 or Wan 2.7 animate it into a 5-30 second video with full face consistency throughout.",
  },
  {
    icon: Globe,
    title: "Brand-Customized Videos",
    description: "Enter your website URL. AI extracts your brand, niche, products, audience, and tone — then writes a custom video prompt that adapts the viral hook for your brand.",
  },
  {
    icon: Target,
    title: "Content Remixer",
    description: "Chat with AI about your remix goal. It checks audience fit, asks smart questions, then generates a production-ready video script tailored to your product.",
  },
  {
    icon: Layers,
    title: "Multiple Video Models",
    description: "Choose between Seedance 2.0 (best quality, native audio, cinematic camera), Wan 2.7 (style preservation), or Seedance Fast (quick previews).",
  },
];

const FLOW_STEPS = [
  { step: "1", label: "Discover", detail: "Browse trending TikTok videos in your niche" },
  { step: "2", label: "Analyze", detail: "AI breaks down what makes the hook work" },
  { step: "3", label: "Face Swap", detail: "Your face replaces the creator's — everything else stays" },
  { step: "4", label: "Generate Video", detail: "AI creates a branded video from your swapped frame" },
];

export default function Landing() {
  return (
    <div className="min-h-screen hero-wash">
      <div className="noise-overlay" />

      {/* Header */}
      <header className="relative z-10 max-w-5xl mx-auto px-4 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[color:var(--brand-teal)] text-white">
            <Sparkles className="h-4 w-4" />
          </span>
          <span className="font-display text-lg font-bold tracking-tight">HookForge</span>
        </div>
        <Link to="/discover">
          <Button className="gap-1.5 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white">
            Enter App <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
      </header>

      {/* Hero */}
      <section className="relative z-10 max-w-4xl mx-auto px-4 pt-12 pb-16 text-center">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[color:rgba(99,102,241,0.08)] text-[color:var(--brand-teal-dark)] text-xs font-semibold mb-5">
          <Zap className="h-3 w-3" /> Internal Tool — HookForge
        </div>
        <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight leading-tight">
          Discover viral hooks.<br />Swap your face in.<br />Generate branded videos.
        </h1>
        <p className="text-muted-foreground mt-4 max-w-2xl mx-auto leading-relaxed">
          Find trending TikTok videos in your niche, analyze what makes their hook work,
          face-swap yourself into the key frame, then generate a full branded video
          customized to your product and audience — all from one pipeline.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link to="/discover">
            <Button size="lg" className="gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white px-8 py-5 text-sm font-semibold shadow-md">
              <Sparkles className="h-4 w-4" /> Enter App
            </Button>
          </Link>
          <Link to="/face-swap">
            <Button size="lg" variant="outline" className="gap-2 rounded-xl px-6 py-5 text-sm font-semibold">
              <Repeat2 className="h-4 w-4" /> Face Swap
            </Button>
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section className="relative z-10 max-w-4xl mx-auto px-4 pb-16">
        <h2 className="font-display text-2xl font-bold text-center mb-8">How It Works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FLOW_STEPS.map((s) => (
            <div key={s.step} className="rounded-xl border border-border bg-card/80 p-4 text-center space-y-2">
              <div className="mx-auto h-9 w-9 rounded-full bg-[color:var(--brand-teal)] text-white flex items-center justify-center font-bold text-sm">
                {s.step}
              </div>
              <h3 className="font-display font-semibold text-sm">{s.label}</h3>
              <p className="text-xs text-muted-foreground">{s.detail}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className="relative z-10 max-w-5xl mx-auto px-4 pb-16">
        <h2 className="font-display text-2xl font-bold text-center mb-2">Features & Capabilities</h2>
        <p className="text-sm text-muted-foreground text-center mb-8">Everything the app does, at a glance.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-card/80 p-4 space-y-2.5 hover:border-[color:rgba(99,102,241,0.3)] transition-colors">
              <div className="h-8 w-8 rounded-lg bg-[color:rgba(99,102,241,0.08)] flex items-center justify-center">
                <f.icon className="h-4 w-4 text-[color:var(--brand-teal)]" />
              </div>
              <h3 className="font-display font-semibold text-sm">{f.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline Detail */}
      <section className="relative z-10 max-w-4xl mx-auto px-4 pb-16">
        <h2 className="font-display text-2xl font-bold text-center mb-8">The Pipeline</h2>
        <div className="rounded-2xl border border-border bg-card/80 p-6 space-y-5">
          <div className="space-y-1">
            <h3 className="font-display font-semibold text-sm flex items-center gap-2"><Film className="h-4 w-4 text-[color:var(--brand-teal)]" /> Phase 1: Image (Face Swap)</h3>
            <p className="text-xs text-muted-foreground leading-relaxed pl-6">
              Gemini 2.5 Flash Image Generation model takes the selected video frame + your face photo.
              It maps facial geometry, matches skin tone to scene lighting, ensures natural blending at boundaries,
              and preserves the target's expression/pose. Output: a production-ready PNG with your face in the viral hook pose.
            </p>
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-1">
            <h3 className="font-display font-semibold text-sm flex items-center gap-2"><Clapperboard className="h-4 w-4 text-[color:var(--brand-coral)]" /> Phase 2: Video (Animation)</h3>
            <p className="text-xs text-muted-foreground leading-relaxed pl-6">
              The swapped image is passed as <code className="text-[10px] bg-muted px-1 py-0.5 rounded">first_frame</code> to the video model
              (Seedance 2.0 or Wan 2.7) via OpenRouter's unified API. The model generates 5-30 seconds of video
              maintaining face consistency throughout. The prompt is either auto-generated from your brand profile
              or manually entered/pasted (e.g. from ChatGPT).
            </p>
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-1">
            <h3 className="font-display font-semibold text-sm flex items-center gap-2"><Globe className="h-4 w-4 text-[color:var(--brand-teal)]" /> Brand Integration</h3>
            <p className="text-xs text-muted-foreground leading-relaxed pl-6">
              Enter your website URL — AI scrapes and analyzes your brand name, products, niche, target audience,
              differentiation, and tone. This profile is used by the Content Remixer to write video prompts that
              specifically promote your product while replicating the viral hook's proven mechanics.
            </p>
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-1">
            <h3 className="font-display font-semibold text-sm flex items-center gap-2"><Layers className="h-4 w-4 text-[color:var(--brand-coral)]" /> Models Used</h3>
            <div className="text-xs text-muted-foreground leading-relaxed pl-6 space-y-1">
              <p><strong>Hook Analysis:</strong> Google Gemini 2.5 Flash (vision) — reads frames, outputs structured JSON</p>
              <p><strong>Face Swap:</strong> Gemini 2.5 Flash Image Generation — photorealistic identity transfer</p>
              <p><strong>Video (Best):</strong> ByteDance Seedance 2.0 — character consistency, native audio, cinematic camera</p>
              <p><strong>Video (Alt):</strong> Alibaba Wan 2.7 — strong style/reference preservation</p>
              <p><strong>Video (Fast):</strong> ByteDance Seedance 2.0 Fast — same tech, optimized for speed</p>
              <p><strong>Brand Analysis & Prompts:</strong> Gemini 2.5 Flash (text) — structured extraction and scriptwriting</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 max-w-4xl mx-auto px-4 pb-12 text-center">
        <Link to="/discover">
          <Button size="lg" className="gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white px-10 py-5 text-base font-semibold shadow-lg">
            <Sparkles className="h-5 w-5" /> Enter App
          </Button>
        </Link>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border/50 bg-card/40">
        <div className="max-w-5xl mx-auto px-4 py-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-[color:var(--brand-teal)] text-white">
              <Sparkles className="h-2.5 w-2.5" />
            </span>
            <span className="font-medium">HookForge</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <Link to="/privacy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
            <Link to="/terms" className="hover:text-foreground transition-colors">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
