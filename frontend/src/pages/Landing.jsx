import { Link } from "react-router-dom";
import {
  AuthedOnly,
  UnauthedOnly,
  SignInTrigger,
  SignUpTrigger,
  AccountButton,
} from "../components/auth/AuthControls";
import {
  Sparkles, Search, Repeat2, Clapperboard, Globe, Save, Film,
  TrendingUp, ArrowRight, Zap, Target, Layers, Music2,
  Bookmark, FileText, BadgeAlert,
  RotateCcw, Play, Check, Wand2,
} from "lucide-react";
import { Button } from "../components/ui/button";

const FEATURES = [
  {
    icon: Search,
    title: "10-Niche Discovery",
    description:
      "Browse trending TikTok videos across 10 niches, ranked by a live virality score. Search any keyword or hashtag.",
  },
  {
    icon: TrendingUp,
    title: "AI Hook Analysis",
    description:
      "AI breaks down the first 2\u20133 seconds of any video: expressions, gestures, pacing, overlays, and audio cues. Scores it 1\u201310.",
  },
  {
    icon: FileText,
    title: "Transcript-Grounded",
    description:
      "When captions exist, the analysis is grounded in the real spoken words \u2014 not just guesswork from the visuals.",
  },
  {
    icon: Music2,
    title: "Sound Intelligence",
    description:
      "See the exact sound on every video \u2014 title, artist, duration. Toggle \u201cUse original sound\u201d to script your remix around it.",
  },
  {
    icon: BadgeAlert,
    title: "Ad Filtering",
    description:
      "Sponsored posts are auto-flagged. One toggle hides them so you only see organic hooks worth replicating.",
  },
  {
    icon: Repeat2,
    title: "Face Swap",
    description:
      "Pick any frame. AI places your face into the exact pose, lighting, and environment \u2014 identity-preserving, 2K output.",
  },
  {
    icon: Save,
    title: "One-Time Face Upload",
    description:
      "Upload your face once, it persists across sessions. Every future swap is a single click.",
  },
  {
    icon: Bookmark,
    title: "Hook Templates",
    description:
      "Save a proven hook. Its analysis, prompt, and motion reference are cached \u2014 reuse it on any future swap with zero AI cost.",
  },
  {
    icon: Clapperboard,
    title: "AI Video Generation",
    description:
      "Your swapped image becomes frame one. MiniMax H3 generates a 5\u201315s video at 2K with V2V motion transfer from the original clip.",
  },
  {
    icon: RotateCcw,
    title: "Re-roll Takes",
    description:
      "Not happy? Re-roll with the same prompt and references. No re-analysis, just a fresh render.",
  },
  {
    icon: Globe,
    title: "Brand Prompts",
    description:
      "Paste your website URL. AI extracts your brand identity and writes a video prompt that adapts the viral hook to your product.",
  },
  {
    icon: Target,
    title: "Content Remixer",
    description:
      "Chat with AI about your goal. It checks audience fit, asks a few questions, then writes a production-ready video script.",
  },
];

const FLOW_STEPS = [
  {
    step: "1",
    label: "Discover",
    icon: Search,
    detail: "Browse trending TikToks in your niche. Filter by virality, views, or recency.",
  },
  {
    step: "2",
    label: "Analyze",
    icon: TrendingUp,
    detail: "AI dissects the hook \u2014 expressions, pacing, overlays. Save it as a free-to-reuse template.",
  },
  {
    step: "3",
    label: "Swap",
    icon: Repeat2,
    detail: "Your face drops into the creator\u2019s exact pose and scene. One click.",
  },
  {
    step: "4",
    label: "Generate",
    icon: Clapperboard,
    detail: "MiniMax H3 animates your frame into a 5\u201315s video. Re-roll or extend with your brand CTA.",
  },
];

const STATS = [
  { value: "10", label: "Niches" },
  { value: "2K", label: "Resolution" },
  { value: "8", label: "Hook Metrics" },
  { value: "15s", label: "Max Video" },
  { value: "$0", label: "Template Reuse" },
];

const NAV_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#pipeline", label: "Pipeline" },
];

/** Soft drifting color fields behind the hero. Decorative only. */
function Aurora() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="aurora-blob animate-float-slow"
        style={{
          top: "-14rem",
          left: "8%",
          width: "34rem",
          height: "34rem",
          background: "radial-gradient(circle, rgba(99,102,241,0.22), transparent 65%)",
        }}
      />
      <div
        className="aurora-blob animate-float-slower"
        style={{
          top: "-10rem",
          right: "4%",
          width: "30rem",
          height: "30rem",
          background: "radial-gradient(circle, rgba(254,44,85,0.16), transparent 65%)",
        }}
      />
      <div
        className="aurora-blob animate-float-slow"
        style={{
          top: "22rem",
          left: "38%",
          width: "26rem",
          height: "26rem",
          background: "radial-gradient(circle, rgba(129,140,248,0.12), transparent 70%)",
        }}
      />
    </div>
  );
}

/**
 * Abstract product preview: the four pipeline stages rendered as connected
 * panels. Deliberately built from markup rather than a screenshot so it
 * always matches the live theme and never goes stale.
 */
function PipelinePreview() {
  return (
    <div className="border-gradient relative mx-auto mt-16 max-w-4xl rounded-3xl p-[1px]">
      <div className="surface-glass relative overflow-hidden rounded-3xl p-4 sm:p-6">
        {/* Fake window chrome */}
        <div className="mb-5 flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--brand-coral)]/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/60" />
          <span className="ml-3 font-mono text-[10px] text-muted-foreground">hookforge / pipeline</span>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          {FLOW_STEPS.map((s, i) => (
            <div
              key={s.step}
              className="group relative rounded-2xl border border-[color:var(--hairline)] bg-[color:var(--indigo-4)] p-3.5"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[color:var(--indigo-10)] text-[color:var(--brand-teal)]">
                  <s.icon className="h-3.5 w-3.5" />
                </span>
                <span className="font-mono text-[10px] text-muted-foreground/60">0{s.step}</span>
              </div>

              {/* Skeleton "frame" — 9:16 to echo the vertical video format */}
              <div className="relative mb-3 aspect-[9/16] overflow-hidden rounded-xl bg-gradient-to-b from-[color:var(--indigo-10)] to-transparent">
                <div className="absolute inset-0 grid place-items-center">
                  {i === 3 ? (
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[color:var(--brand-coral)] text-white shadow-[var(--glow-coral)]">
                      <Play className="h-3.5 w-3.5" />
                    </span>
                  ) : (
                    <span className="flex h-8 w-8 items-center justify-center rounded-full border border-[color:var(--indigo-25)] text-[color:var(--brand-teal)]">
                      <s.icon className="h-3.5 w-3.5" />
                    </span>
                  )}
                </div>
                <div className="absolute bottom-2 left-2 right-2 space-y-1.5">
                  <span className="block h-1.5 w-3/4 rounded-full bg-white/10" />
                  <span className="block h-1.5 w-1/2 rounded-full bg-white/[0.07]" />
                </div>
              </div>

              <p className="font-display text-xs font-semibold">{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const PIPELINE_BLOCKS = [
  {
    icon: Film,
    tone: "indigo",
    kicker: "Phase 1",
    title: "Image (Face Swap)",
    body: (
      <>
        Grok Imagine places your face into the selected frame &mdash; matching pose, outfit,
        background, lighting, and camera angle. Output: a 2K, 9:16 PNG ready for animation.
      </>
    ),
  },
  {
    icon: Clapperboard,
    tone: "coral",
    kicker: "Phase 2",
    title: "Video (Animation)",
    body: (
      <>
        Your swapped image is the{" "}
        <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-xs">first_frame</code>.
        The original clip is the V2V motion reference. MiniMax H3 replicates the exact timing and camera work
        at 2K resolution. Videos are muted by default (add a trending sound in TikTok) with an optional AI-audio toggle.
        Re-roll for another take, or extend into a longer branded video with a CTA.
      </>
    ),
  },
  {
    icon: Bookmark,
    tone: "indigo",
    kicker: "Reuse",
    title: "Hook Templates",
    body: (
      <>
        Save any hook that works. The analysis, prompt, and source clip are cached. Reusing a template
        later skips all AI analysis &mdash; you only pay for the video render itself.
      </>
    ),
  },
  {
    icon: FileText,
    tone: "indigo",
    kicker: "Signal",
    title: "Transcript & Ad Detection",
    body: (
      <>
        Transcripts ground the analysis in real spoken words. Ads are auto-flagged and hideable
        with one toggle so you focus on organic hooks.
      </>
    ),
  },
  {
    icon: Globe,
    tone: "indigo",
    kicker: "Brand",
    title: "Brand Integration",
    body: (
      <>
        Paste your URL &mdash; AI extracts your brand name, products, audience, and tone. This profile
        powers the Content Remixer to write prompts that promote your product while replicating the hook&apos;s
        proven mechanics.
      </>
    ),
  },
];

const MODELS = [
  { label: "Hook Analysis", value: "Gemini 2.5 Flash (vision) \u2014 frame reading, structured JSON output" },
  { label: "Face Swap", value: "Grok Imagine \u2014 identity-preserving compositing, 2K" },
  { label: "Video", value: "MiniMax H3 \u2014 V2V motion transfer, native audio, 2K, up to 15s" },
  { label: "Brand & Remix", value: "Gemini 2.5 Flash \u2014 brand extraction, prompt writing, remix chat" },
  { label: "Data", value: "Apify TikTok Scraper + yt-dlp \u2014 profiles, hashtags, keyword search, music" },
];

function SectionHeading({ eyebrow, title, lede, id }) {
  return (
    <div className="mx-auto mb-12 max-w-2xl text-center" id={id}>
      {eyebrow && (
        <span className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-[color:var(--hairline)] bg-[color:var(--indigo-6)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--brand-teal)]">
          {eyebrow}
        </span>
      )}
      <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">{title}</h2>
      {lede && <p className="mt-3.5 text-base leading-relaxed text-muted-foreground sm:text-lg">{lede}</p>}
    </div>
  );
}

export default function Landing() {
  return (
    <div className="relative min-h-screen hero-wash">
      <div className="noise-overlay" />

      {/* ---------- Header ---------- */}
      <header className="sticky top-0 z-30 border-b border-[color:var(--hairline)] bg-[hsl(228_14%_7%_/_0.72)] backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[color:var(--brand-teal)] to-[color:var(--brand-teal-dark)] text-white shadow-[var(--glow-indigo)]">
              <Sparkles className="h-[18px] w-[18px]" />
              <span className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-b from-white/25 to-transparent" />
            </span>
            <span className="font-display text-lg font-bold tracking-tight">HookForge</span>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-[color:var(--indigo-6)] hover:text-foreground"
              >
                {l.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <UnauthedOnly>
              <SignInTrigger>
                <button className="rounded-xl px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-[color:var(--indigo-6)] hover:text-foreground">
                  Sign In
                </button>
              </SignInTrigger>
              {/* Same testid as the signed-in "Enter App" button — the two
                  branches are mutually exclusive, so the onboarding tour
                  always finds exactly one primary CTA to anchor to. */}
              <SignUpTrigger>
                <Button
                  className="gap-2 rounded-xl bg-[color:var(--brand-teal)] px-4 text-sm font-semibold text-white shadow-[var(--glow-indigo)] hover:bg-[color:var(--brand-teal-dark)]"
                  data-testid="landing-enter-app-button"
                >
                  Get Started <ArrowRight className="h-4 w-4" />
                </Button>
              </SignUpTrigger>
            </UnauthedOnly>
            <AuthedOnly>
              <Link to="/discover">
                <Button
                  className="gap-2 rounded-xl bg-[color:var(--brand-teal)] px-4 text-sm font-semibold text-white shadow-[var(--glow-indigo)] hover:bg-[color:var(--brand-teal-dark)]"
                  data-testid="landing-enter-app-button"
                >
                  Enter App <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <AccountButton />
            </AuthedOnly>
          </div>
        </div>
      </header>

      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden">
        <Aurora />
        <div className="grid-overlay" />
        <div className="relative z-10 mx-auto max-w-5xl px-5 pb-24 pt-20 text-center sm:pt-28">
          <div className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] px-3.5 py-1.5 text-sm font-semibold text-[color:var(--brand-teal)] backdrop-blur-sm">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 animate-pulse-ring rounded-full bg-[color:var(--brand-teal)]" />
              <span className="relative h-1.5 w-1.5 rounded-full bg-[color:var(--brand-teal)]" />
            </span>
            Viral hooks &rarr; Your face &rarr; Branded video
          </div>

          <h1
            className="animate-fade-up font-display mt-8 text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-[4.5rem]"
            style={{ animationDelay: "60ms" }}
          >
            <span className="text-shine">Your face.</span>
            <br />
            <span className="text-gradient-brand">Proven TikTok hooks.</span>
            <br />
            <span className="text-shine">Infinite video.</span>
          </h1>

          <p
            className="animate-fade-up mx-auto mt-7 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl"
            style={{ animationDelay: "120ms" }}
          >
            Pick a trending hook, swap yourself into the key frame, and generate a branded
            video in under two minutes. Save any hook as a template &mdash; every future
            remix costs nothing.
          </p>

          <div
            className="animate-fade-up mt-10 flex flex-col items-center justify-center gap-3.5 sm:flex-row"
            style={{ animationDelay: "180ms" }}
          >
            <UnauthedOnly>
              <SignUpTrigger>
                <Button
                  size="lg"
                  className="w-full gap-2.5 rounded-xl bg-[color:var(--brand-coral)] px-9 py-6 text-base font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] sm:w-auto"
                >
                  <Sparkles className="h-5 w-5" /> Start Free
                </Button>
              </SignUpTrigger>
              <SignInTrigger>
                <Button
                  size="lg"
                  variant="outline"
                  className="w-full gap-2.5 rounded-xl border-[color:var(--hairline-strong)] bg-[color:var(--indigo-4)] px-8 py-6 text-base font-semibold backdrop-blur-sm hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] sm:w-auto"
                >
                  I have an account
                </Button>
              </SignInTrigger>
            </UnauthedOnly>
            <AuthedOnly>
              <Link to="/discover" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  className="w-full gap-2.5 rounded-xl bg-[color:var(--brand-coral)] px-9 py-6 text-base font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] sm:w-auto"
                >
                  <Sparkles className="h-5 w-5" /> Go to App
                </Button>
              </Link>
              <Link to="/face-swap" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  variant="outline"
                  className="w-full gap-2.5 rounded-xl border-[color:var(--hairline-strong)] bg-[color:var(--indigo-4)] px-8 py-6 text-base font-semibold backdrop-blur-sm hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] sm:w-auto"
                >
                  <Repeat2 className="h-5 w-5" /> Face Swap
                </Button>
              </Link>
            </AuthedOnly>
          </div>

          <div
            className="animate-fade-up mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground"
            style={{ animationDelay: "220ms" }}
          >
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-teal)]" /> Upload your face once
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-teal)]" /> 2K vertical output
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-teal)]" /> Free template reuse
            </span>
          </div>

          {/* Quick stats bar */}
          <div
            className="animate-fade-up surface-glass mt-14 rounded-2xl px-2 py-5 sm:px-6"
            data-testid="landing-stats"
            style={{ animationDelay: "260ms" }}
          >
            <dl className="grid grid-cols-3 gap-y-5 sm:grid-cols-5 sm:gap-y-0">
              {STATS.map((stat, i) => (
                <div
                  key={stat.label}
                  className={`text-center sm:px-2 ${
                    i > 0 ? "sm:border-l sm:border-border/50" : ""
                  }`}
                >
                  <dt className="sr-only">{stat.label}</dt>
                  <dd>
                    <span className="font-display block text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                      {stat.value}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground sm:text-sm">{stat.label}</span>
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <PipelinePreview />
        </div>
      </section>

      {/* ---------- How it works ---------- */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-24" data-testid="landing-how-it-works">
        <SectionHeading
          id="how-it-works"
          eyebrow="The loop"
          title="How It Works"
          lede="Four steps. Under two minutes. Every saved hook makes the next one free."
        />

        <div className="relative">
          {/* Connecting line behind the cards on wide screens */}
          <div
            aria-hidden="true"
            className="absolute left-0 right-0 top-[42px] hidden h-px bg-gradient-to-r from-transparent via-[color:var(--indigo-25)] to-transparent lg:block"
          />
          <div className="relative grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FLOW_STEPS.map((s) => (
              <div
                key={s.step}
                className="surface surface-interactive shimmer-on-hover group rounded-2xl p-6 text-center"
              >
                <div className="relative mx-auto mb-4 flex h-[52px] w-[52px] items-center justify-center rounded-2xl bg-gradient-to-br from-[color:var(--brand-teal)] to-[color:var(--brand-teal-dark)] font-bold text-white shadow-[var(--glow-indigo)]">
                  <span className="font-display text-lg">{s.step}</span>
                  <span className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/25 to-transparent" />
                </div>
                <h3 className="font-display text-base font-semibold">{s.label}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Features ---------- */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 pb-24" data-testid="landing-features">
        <SectionHeading
          id="features"
          eyebrow="Capabilities"
          title="What You Get"
          lede="Every tool in the pipeline, from discovery to publish-ready video."
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="surface surface-interactive shimmer-on-hover group rounded-2xl p-5 sm:p-6"
            >
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] transition-colors duration-200 group-hover:border-[color:var(--indigo-35)] group-hover:bg-[color:var(--indigo-15)]">
                <f.icon className="h-5 w-5 text-[color:var(--brand-teal)]" />
              </div>
              <h3 className="font-display text-base font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------- Pipeline ---------- */}
      <section className="relative z-10 mx-auto max-w-5xl px-5 pb-24">
        <SectionHeading
          id="pipeline"
          eyebrow="Under the hood"
          title="The Pipeline"
          lede="What happens between picking a hook and downloading your video."
        />

        <div className="space-y-4">
          {PIPELINE_BLOCKS.map((block) => {
            const isCoral = block.tone === "coral";
            return (
              <div
                key={block.title}
                className="surface surface-interactive rounded-2xl p-5 sm:p-7"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:gap-5">
                  <div
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${
                      isCoral
                        ? "border-[color:var(--coral-25)] bg-[color:var(--coral-12)]"
                        : "border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)]"
                    }`}
                  >
                    <block.icon
                      className={`h-5 w-5 ${
                        isCoral ? "text-[color:var(--brand-coral)]" : "text-[color:var(--brand-teal)]"
                      }`}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <span
                      className={`eyebrow ${
                        isCoral ? "text-[color:var(--brand-coral)]" : "text-[color:var(--brand-teal)]"
                      }`}
                    >
                      {block.kicker}
                    </span>
                    <h3 className="font-display mt-1 text-base font-semibold sm:text-lg">{block.title}</h3>
                    <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground sm:text-base">
                      {block.body}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Models used — table-like layout reads better than a bullet list */}
          <div className="surface rounded-2xl p-5 sm:p-7">
            <div className="flex flex-col gap-4 sm:flex-row sm:gap-5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[color:var(--coral-25)] bg-[color:var(--coral-12)]">
                <Layers className="h-5 w-5 text-[color:var(--brand-coral)]" />
              </div>
              <div className="min-w-0 flex-1">
                <span className="eyebrow text-[color:var(--brand-coral)]">Stack</span>
                <h3 className="font-display mt-1 text-base font-semibold sm:text-lg">Models Used</h3>
                <dl className="mt-4 divide-y divide-border/60">
                  {MODELS.map((m) => (
                    <div key={m.label} className="grid gap-1 py-2.5 sm:grid-cols-[180px_1fr] sm:gap-4">
                      <dt className="font-display text-sm font-semibold text-foreground">{m.label}</dt>
                      <dd className="text-sm leading-relaxed text-muted-foreground">{m.value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Final CTA ---------- */}
      <section className="relative z-10 mx-auto max-w-4xl px-5 pb-24">
        <div className="border-gradient relative rounded-3xl p-[1px]">
          <div className="surface-glass relative overflow-hidden rounded-3xl px-6 py-12 text-center sm:px-12 sm:py-16">
            <div className="spotlight-indigo absolute inset-0" aria-hidden="true" />
            <div className="relative">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--brand-teal)]">
                <Zap className="h-3 w-3" /> Under 2 minutes
              </span>
              <h2 className="font-display mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                Start making content that converts.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                Find a trending hook, swap your face in, generate a branded video &mdash; done.
                Save the hook as a template and every future remix is free.
              </p>
              <div className="mt-9 flex flex-col items-center justify-center gap-3.5 sm:flex-row">
                <UnauthedOnly>
                  <SignUpTrigger>
                    <Button
                      size="lg"
                      className="w-full gap-2.5 rounded-xl bg-[color:var(--brand-coral)] px-9 py-6 text-base font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] sm:w-auto"
                    >
                      <Sparkles className="h-5 w-5" /> Get Started Free
                    </Button>
                  </SignUpTrigger>
                  <SignInTrigger>
                    <Button
                      size="lg"
                      variant="outline"
                      className="w-full gap-2.5 rounded-xl border-[color:var(--hairline-strong)] bg-[color:var(--indigo-4)] px-8 py-6 text-base font-semibold hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] sm:w-auto"
                    >
                      Sign In
                    </Button>
                  </SignInTrigger>
                </UnauthedOnly>
                <AuthedOnly>
                  <Link to="/discover" className="w-full sm:w-auto">
                    <Button
                      size="lg"
                      className="w-full gap-2.5 rounded-xl bg-[color:var(--brand-coral)] px-9 py-6 text-base font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] sm:w-auto"
                    >
                      <Sparkles className="h-5 w-5" /> Enter App
                    </Button>
                  </Link>
                  <Link to="/brand" className="w-full sm:w-auto">
                    <Button
                      size="lg"
                      variant="outline"
                      className="w-full gap-2.5 rounded-xl border-[color:var(--hairline-strong)] bg-[color:var(--indigo-4)] px-8 py-6 text-base font-semibold hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] sm:w-auto"
                    >
                      <Globe className="h-5 w-5" /> Set Up Your Brand
                    </Button>
                  </Link>
                </AuthedOnly>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Footer ---------- */}
      <footer className="relative z-10 border-t border-[color:var(--hairline)] bg-[hsl(228_14%_8%_/_0.6)] backdrop-blur-sm">
        <div className="mx-auto max-w-6xl px-5 py-12">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <div className="lg:col-span-2">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--brand-teal)] to-[color:var(--brand-teal-dark)] text-white">
                  <Sparkles className="h-4 w-4" />
                </span>
                <span className="font-display text-base font-bold tracking-tight">HookForge</span>
              </div>
              <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
                Your face in proven viral hooks &mdash; discover, swap, generate, publish.
              </p>
            </div>

            <div>
              <p className="eyebrow mb-3">Product</p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link to="/discover" className="transition-colors hover:text-foreground">Discover Hooks</Link>
                </li>
                <li>
                  <Link to="/face-swap" className="transition-colors hover:text-foreground">Face Swap</Link>
                </li>
                <li>
                  <Link to="/templates" className="transition-colors hover:text-foreground">Hook Templates</Link>
                </li>
                <li>
                  <Link to="/brand" className="transition-colors hover:text-foreground">Your Brand</Link>
                </li>
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

          <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-border/50 pt-6 sm:flex-row">
            <p className="text-xs text-muted-foreground">
              &copy; {new Date().getFullYear()} HookForge. Built for creators.
            </p>
            <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Wand2 className="h-3 w-3 text-[color:var(--brand-teal)]" /> Powered by MiniMax H3 &amp; Gemini 2.5 Flash
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
