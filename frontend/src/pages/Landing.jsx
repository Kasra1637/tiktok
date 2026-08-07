import { Link } from "react-router-dom";
import {
  Sparkles, Search, Repeat2, Clapperboard, Globe, Save, Film,
  TrendingUp, ArrowRight, Zap, Target, Layers, Music2,
  Bookmark, Users, ChevronRight, Hash, BarChart3, FileText, BadgeAlert,
} from "lucide-react";
import { Button } from "../components/ui/button";

const FEATURES = [
  {
    icon: Search,
    title: "Discover Viral Hooks",
    description:
      "Browse 10 niches of trending TikTok videos ranked by virality score. Search by keyword or hashtag. Curated creators + trending hashtags per niche.",
  },
  {
    icon: TrendingUp,
    title: "AI Hook Analysis",
    description:
      "Paste any TikTok URL or pick from discovery. AI extracts the first 2\u20133 seconds, analyzes facial expressions, gestures, pacing, text overlays, and audio cues. Effectiveness score 1\u201310.",
  },
  {
    icon: FileText,
    title: "Transcript-Informed Analysis",
    description:
      "When a video has captions available, we pull the actual spoken transcript and ground the hook analysis in real words \u2014 not just visual guesswork.",
  },
  {
    icon: Music2,
    title: "Sound & Music Data",
    description:
      "Every video includes the exact sound used \u2014 title, artist, and duration. See which sounds are trending, then toggle \u201cUse original sound\u201d to get a remix script written for that audio.",
  },
  {
    icon: BadgeAlert,
    title: "Sponsored Post Filtering",
    description:
      "Ad and sponsored posts are automatically flagged. Hide them with one toggle in Discovery to focus on organic hooks worth replicating.",
  },
  {
    icon: Repeat2,
    title: "Face Swap",
    description:
      "Select any frame from a viral video. Your face is swapped in with production-quality geometry tracking \u2014 pose, gesture, lighting, and environment stay identical.",
  },
  {
    icon: Save,
    title: "Saved Face",
    description:
      "Upload your face once \u2014 it persists across sessions. Next time you pick a viral video, just hit Generate. Zero re-uploads needed.",
  },
  {
    icon: Clapperboard,
    title: "AI Video Generation",
    description:
      "Your face-swapped image becomes the first frame. MiniMax H3 generates a 5\u201315 second video at 2K resolution with native audio, V2V motion transfer, and full face consistency \u2014 all in one pass.",
  },
  {
    icon: Globe,
    title: "Brand-Customized Prompts",
    description:
      "Enter your website URL. AI extracts your brand identity \u2014 name, niche, products, audience, and tone \u2014 then writes a tailored video prompt that adapts the viral hook for your brand.",
  },
  {
    icon: Target,
    title: "Content Remixer",
    description:
      "Chat with AI about your remix goal. It checks audience fit between the hook and your brand, asks focused questions, then writes a production-ready video script.",
  },
  {
    icon: Hash,
    title: "Hashtag & Creator Feed",
    description:
      "10 niches with curated creators and trending hashtags (fitness, comedy, beauty, food, fashion, tech, pets, travel, finance, education). Fresh data on every visit.",
  },
  {
    icon: Bookmark,
    title: "Bookmarks = Purchase Intent",
    description:
      "Bookmark count (saves) is a stronger conversion signal than likes. Our virality scoring weights bookmarks to surface hooks that drive real action, not passive scrolling.",
  },
  {
    icon: BarChart3,
    title: "Virality Scoring Engine",
    description:
      "Every video gets a 0\u2013100 score blending engagement rate, view velocity, recency, raw scale, and save intent \u2014 so the best hooks always surface first.",
  },
  {
    icon: Layers,
    title: "MiniMax H3 Powered",
    description:
      "Omni-modal video generation: native stereo audio (dialogue, foley, music), V2V motion transfer from viral references, 2K resolution, and up to 9 image references for character consistency.",
  },
];

const FLOW_STEPS = [
  {
    step: "1",
    label: "Discover",
    detail: "Browse trending TikTok videos in your niche. See the sound, creator stats, and virality score.",
  },
  {
    step: "2",
    label: "Analyze",
    detail: "AI breaks down what makes the hook work \u2014 expressions, gestures, pacing, overlays, and audio cues.",
  },
  {
    step: "3",
    label: "Face Swap",
    detail: "Your face replaces the creator\u2019s. Pose, gesture, lighting, and environment stay identical.",
  },
  {
    step: "4",
    label: "Generate Video",
    detail: "AI creates a branded video from your swapped frame \u2014 with the option to keep the original sound.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen hero-wash">
      <div className="noise-overlay" />

      {/* Header */}
      <header className="relative z-10 max-w-6xl mx-auto px-5 py-6 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[color:var(--brand-teal)] text-white shadow-md">
            <Sparkles className="h-4.5 w-4.5" />
          </span>
          <span className="font-display text-xl font-bold tracking-tight">HookForge</span>
        </div>
        <Link to="/discover">
          <Button className="gap-2 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white px-5 py-2.5 text-sm font-semibold shadow-md">
            Enter App <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </header>

      {/* Hero */}
      <section className="relative z-10 max-w-5xl mx-auto px-5 pt-16 pb-20 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[color:rgba(99,102,241,0.1)] text-[color:var(--brand-teal)] text-sm font-semibold mb-7 border border-[color:rgba(99,102,241,0.15)]">
          <Zap className="h-3.5 w-3.5" /> Viral TikTok Hooks &rarr; Branded Videos
        </div>
        <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1]">
          Discover viral hooks.
          <br />
          <span className="text-[color:var(--brand-teal)]">Swap your face in.</span>
          <br />
          Generate branded videos.
        </h1>
        <p className="text-lg sm:text-xl text-muted-foreground mt-6 max-w-3xl mx-auto leading-relaxed">
          Find trending TikTok videos in your niche, analyze what makes their hook work,
          face-swap yourself into the key frame, then generate a full branded video
          customized to your product and audience &mdash; all from one pipeline.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/discover">
            <Button size="lg" className="gap-2.5 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white px-10 py-6 text-base font-semibold shadow-lg hover:shadow-xl transition-shadow">
              <Sparkles className="h-5 w-5" /> Start Discovering
            </Button>
          </Link>
          <Link to="/face-swap">
            <Button size="lg" variant="outline" className="gap-2.5 rounded-xl px-8 py-6 text-base font-semibold border-border/80 hover:border-[color:rgba(99,102,241,0.4)] hover:bg-[color:rgba(99,102,241,0.04)]">
              <Repeat2 className="h-5 w-5" /> Face Swap
            </Button>
          </Link>
        </div>

        {/* Quick stats bar */}
        <div className="mt-14 flex flex-wrap items-center justify-center gap-6 sm:gap-10">
          {[
            { value: "10", label: "Niches" },
            { value: "2K", label: "Resolution" },
            { value: "8", label: "Hook Metrics" },
            { value: "15s", label: "Max Video" },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <p className="font-display text-2xl sm:text-3xl font-bold text-foreground">{stat.value}</p>
              <p className="text-sm text-muted-foreground mt-0.5">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="relative z-10 max-w-5xl mx-auto px-5 pb-20">
        <h2 className="font-display text-3xl sm:text-4xl font-bold text-center mb-4">How It Works</h2>
        <p className="text-base sm:text-lg text-muted-foreground text-center mb-10 max-w-2xl mx-auto">
          Four steps from trending video to your own branded content.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {FLOW_STEPS.map((s, i) => (
            <div
              key={s.step}
              className="relative rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-6 text-center space-y-3 hover:border-[color:rgba(99,102,241,0.35)] transition-colors group"
            >
              <div className="mx-auto h-11 w-11 rounded-full bg-[color:var(--brand-teal)] text-white flex items-center justify-center font-bold text-lg shadow-md group-hover:scale-105 transition-transform">
                {s.step}
              </div>
              <h3 className="font-display font-semibold text-base">{s.label}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{s.detail}</p>
              {i < FLOW_STEPS.length - 1 && (
                <ChevronRight className="hidden lg:block absolute -right-3.5 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground/40" />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className="relative z-10 max-w-6xl mx-auto px-5 pb-20">
        <h2 className="font-display text-3xl sm:text-4xl font-bold text-center mb-3">Features &amp; Capabilities</h2>
        <p className="text-base sm:text-lg text-muted-foreground text-center mb-10 max-w-2xl mx-auto">
          Everything the app does, at a glance.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-5 sm:p-6 space-y-3 hover:border-[color:rgba(99,102,241,0.35)] hover:shadow-[var(--shadow-tight)] transition-all group"
            >
              <div className="h-10 w-10 rounded-xl bg-[color:rgba(99,102,241,0.1)] flex items-center justify-center group-hover:bg-[color:rgba(99,102,241,0.15)] transition-colors">
                <f.icon className="h-5 w-5 text-[color:var(--brand-teal)]" />
              </div>
              <h3 className="font-display font-semibold text-base">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline Detail */}
      <section className="relative z-10 max-w-5xl mx-auto px-5 pb-20">
        <h2 className="font-display text-3xl sm:text-4xl font-bold text-center mb-10">The Pipeline</h2>
        <div className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-6 sm:p-8 space-y-6">
          <div className="space-y-2">
            <h3 className="font-display font-semibold text-base flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[color:rgba(99,102,241,0.1)]">
                <Film className="h-4 w-4 text-[color:var(--brand-teal)]" />
              </span>
              Phase 1: Image (Face Swap)
            </h3>
            <p className="text-sm sm:text-base text-muted-foreground leading-relaxed pl-10">
              Gemini 2.5 Flash Image Generation takes the selected video frame + your face photo.
              It maps facial geometry, matches skin tone to scene lighting, ensures natural blending at boundaries,
              and preserves the target&apos;s expression and pose. Output: a production-ready PNG with your face in the viral hook pose.
            </p>
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-2">
            <h3 className="font-display font-semibold text-base flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[color:rgba(254,44,85,0.1)]">
                <Clapperboard className="h-4 w-4 text-[color:var(--brand-coral)]" />
              </span>
              Phase 2: Video (Animation)
            </h3>
            <p className="text-sm sm:text-base text-muted-foreground leading-relaxed pl-10">
              The swapped image is passed as <code className="text-xs bg-muted px-1.5 py-0.5 rounded-md font-mono">first_frame</code> to
              MiniMax H3 via OpenRouter&apos;s unified API. The original viral video is fed as a V2V motion reference,
              so H3 replicates the exact timing, camera work, and performance rhythm while generating native stereo
              audio (dialogue, foley, ambient) in a single pass &mdash; no separate audio step needed.
            </p>
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-2">
            <h3 className="font-display font-semibold text-base flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[color:rgba(99,102,241,0.1)]">
                <FileText className="h-4 w-4 text-[color:var(--brand-teal)]" />
              </span>
              Transcript &amp; Ad Detection
            </h3>
            <p className="text-sm sm:text-base text-muted-foreground leading-relaxed pl-10">
              When TikTok provides captions for a video, we fetch the transcript link and use the actual spoken
              words to ground the hook analysis. Posts flagged as ads or sponsored content are marked with a
              &ldquo;Sponsored&rdquo; badge and can be hidden with one toggle in Discovery, so you focus on organic hooks.
            </p>
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-2">
            <h3 className="font-display font-semibold text-base flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[color:rgba(99,102,241,0.1)]">
                <Globe className="h-4 w-4 text-[color:var(--brand-teal)]" />
              </span>
              Brand Integration
            </h3>
            <p className="text-sm sm:text-base text-muted-foreground leading-relaxed pl-10">
              Enter your website URL &mdash; AI scrapes and analyzes your brand name, products, niche, target audience,
              differentiation, and tone. This profile powers the Content Remixer to write video prompts that
              specifically promote your product while replicating the viral hook&apos;s proven mechanics.
            </p>
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-2">
            <h3 className="font-display font-semibold text-base flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[color:rgba(254,44,85,0.1)]">
                <Layers className="h-4 w-4 text-[color:var(--brand-coral)]" />
              </span>
              Models Used
            </h3>
            <div className="text-sm sm:text-base text-muted-foreground leading-relaxed pl-10 space-y-1.5">
              <p><strong className="text-foreground">Hook Analysis:</strong> Google Gemini 2.5 Flash (vision) &mdash; reads frames, outputs structured JSON</p>
              <p><strong className="text-foreground">Face Swap:</strong> Gemini 2.5 Flash Image Generation &mdash; photorealistic identity transfer</p>
              <p><strong className="text-foreground">Video (Best):</strong> ByteDance Seedance 2.0 &mdash; character consistency, native audio, cinematic camera</p>
              <p><strong className="text-foreground">Video (Alt):</strong> Alibaba Wan 2.7 &mdash; strong style/reference preservation</p>
              <p><strong className="text-foreground">Video (Fast):</strong> ByteDance Seedance 2.0 Fast &mdash; same tech, optimized for speed</p>
              <p><strong className="text-foreground">Data:</strong> Clockworks TikTok Scraper &mdash; profiles, hashtags, keyword search, music metadata</p>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="relative z-10 max-w-4xl mx-auto px-5 pb-16 text-center">
        <div className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-8 sm:p-12">
          <h2 className="font-display text-2xl sm:text-3xl font-bold mb-3">Ready to remix viral hooks?</h2>
          <p className="text-base text-muted-foreground mb-8 max-w-xl mx-auto">
            Find the trending sound, swap your face in, and generate a branded video &mdash; all in under 2 minutes.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/discover">
              <Button size="lg" className="gap-2.5 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white px-10 py-6 text-base font-semibold shadow-lg">
                <Sparkles className="h-5 w-5" /> Enter App
              </Button>
            </Link>
            <Link to="/brand">
              <Button size="lg" variant="outline" className="gap-2.5 rounded-xl px-8 py-6 text-base font-semibold border-border/80 hover:border-[color:rgba(99,102,241,0.4)]">
                <Globe className="h-5 w-5" /> Set Up Your Brand
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border/50 bg-card/40 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-5 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5 text-base text-muted-foreground">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[color:var(--brand-teal)] text-white">
              <Sparkles className="h-3 w-3" />
            </span>
            <span className="font-display font-semibold text-foreground">HookForge</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
            <Link to="/privacy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
            <Link to="/terms" className="hover:text-foreground transition-colors">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
