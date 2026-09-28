import { Link } from "react-router-dom";
import {
  AuthedOnly,
  UnauthedOnly,
  SignInTrigger,
  SignUpTrigger,
  AccountButton,
} from "../components/auth/AuthControls";
import {
  Sparkles, Search, Clapperboard, Globe, Film,
  TrendingUp, ArrowRight, Zap, Target, Layers, Music2,
  Bookmark, FileText, BadgeAlert,
  RotateCcw, Check, Wand2, Briefcase, LayoutTemplate, ShieldCheck, Download,
} from "lucide-react";
import { Button } from "../components/ui/button";

const FEATURES = [
  {
    icon: Briefcase,
    title: "App Profiles",
    description:
      "Submit a website, App Store, or Play Store URL. AI researches it into an editable profile \u2014 features, audiences, pricing, brand voice, and claims. Nothing generates until you approve it.",
  },
  {
    icon: Target,
    title: "Audiences & Angles",
    description:
      "Ideal customer segments and content angles, each with the user problem, hook promise, app feature, emotion, CTA, and the claims to respect.",
  },
  {
    icon: LayoutTemplate,
    title: "Hook Template Library",
    description:
      "Curated, versioned hook structures you can search, filter, favorite, preview, duplicate, and customize. Drafts need review before they go live.",
  },
  {
    icon: Wand2,
    title: "Template Recommendations",
    description:
      "Templates ranked for your app, audience, angle, and objective \u2014 with why each fits, the assets it needs, and its limits. Any compatible template can still be picked by hand.",
  },
  {
    icon: FileText,
    title: "Editable Creative Plan",
    description:
      "Hook line, full script, shot and beat timeline, on-screen text, voice, sound, and CTA \u2014 generated as a plan you can rewrite before anything renders.",
  },
  {
    icon: Clapperboard,
    title: "One Coherent Video",
    description:
      "Hook and continuation arrive from a single generation, 10 to 30 seconds where the model supports it. The video model stays a setting, not a dependency.",
  },
  {
    icon: Film,
    title: "Real App Visuals",
    description:
      "Your actual screenshots, recordings, logos, and captions are composited on afterwards with ffmpeg, so interfaces, pricing, and app names stay correct.",
  },
  {
    icon: ShieldCheck,
    title: "Claim Safety",
    description:
      "Approved, review-required, and banned claims are re-checked on every edit. Reviewers see the claims used, their sources, unverified lines, and risks.",
  },
  {
    icon: Layers,
    title: "Asset Library",
    description:
      "Screenshots, recordings, logos, character references, and backgrounds filed per app, with usage history and a guard that refuses another app's assets.",
  },
  {
    icon: Music2,
    title: "Authorized Audio",
    description:
      "Voiceover and background audio become usable only after you confirm the rights, then mix deterministically under the generated clip.",
  },
  {
    icon: RotateCcw,
    title: "Controlled Variations",
    description:
      "Change one axis at a time \u2014 hook, CTA, tone, audience, pacing, or length. Every variation stays linked to its parent generation, script, and model.",
  },
  {
    icon: TrendingUp,
    title: "Internal Analytics",
    description:
      "Success and failure rates, generation time, spend by app and template, and regeneration reasons. Manual performance notes stay marked unverified.",
  },
  {
    icon: Check,
    title: "Feedback Loop",
    description:
      "Approvals, rejections, heavy script edits, and regenerations are recorded per app and template, and re-rank future template recommendations and shape the next creative plans.",
  },
  {
    icon: BadgeAlert,
    title: "History & Operations",
    description:
      "Status, cost, model, and error for every job. Failed generations, storage faults, and video-processing errors stay visible and retryable.",
  },
  {
    icon: Search,
    title: "Optional Trend Research",
    description:
      "Public TikTok data abstracted into reusable mechanics that become reviewed template drafts. Creating a video never requires a source video.",
  },
  {
    icon: Download,
    title: "Manual Publishing",
    description:
      "Download the finished MP4 and post it yourself. There is no posting, scheduling, engagement automation, or platform credential storage anywhere.",
  },
];


const FLOW_STEPS = [
  {
    step: "1",
    label: "Profile",
    icon: Briefcase,
    detail: "Paste your app's website and store links. AI researches them into an App Profile you review and approve before anything generates.",
  },
  {
    step: "2",
    label: "Brief",
    icon: Target,
    detail: "Choose the audience, objective, and content angle. Hook templates are recommended with the reason each one fits.",
  },
  {
    step: "3",
    label: "Plan",
    icon: FileText,
    detail: "Select real assets, generate the script and shot plan, then edit the hook, on-screen text, CTA, tone, and length.",
  },
  {
    step: "4",
    label: "Deliver",
    icon: Download,
    detail: "Generate one coherent vertical video, composite the real app visuals, download the MP4, and publish it yourself.",
  },
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

const PIPELINE_BLOCKS = [
  {
    icon: Globe,
    tone: "indigo",
    kicker: "Intelligence",
    title: "Researched, Then Approved",
    body: (
      <>
        Website and store pages become an App Profile: features, use cases, competitors, pricing,
        brand voice, and claims sorted into approved, needs-review, and banned. You approve it
        before generation, and a refresh never silently overwrites what you approved.
      </>
    ),
  },
  {
    icon: Clapperboard,
    tone: "coral",
    kicker: "Generation",
    title: "One Coherent Video",
    body: (
      <>
        The studio generates the hook and the continuation as a single vertical clip, with native
        audio where the model supports it. A second pass only happens to extend past the model's
        limit or to replace a failed segment.
      </>
    ),
  },
  {
    icon: Film,
    tone: "indigo",
    kicker: "Compositing",
    title: "Real Visuals, Deterministically",
    body: (
      <>
        The model is asked for people, scenes, and movement \u2014 never your interface. Real
        screenshots, screen recordings, captions, logos, and authorized audio are overlaid afterwards
        with ffmpeg, so UI, pricing, and app names cannot drift.
      </>
    ),
  },
  {
    icon: Search,
    tone: "indigo",
    kicker: "Research",
    title: "Mechanics, Not Imitation",
    body: (
      <>
        Optional trend research abstracts recurring hook structures from public videos into template
        drafts that need review. No creator identity, performance, gesture sequence, voice, or
        copyrighted audio is copied into the library.
      </>
    ),
  },
];


const MODELS = [
  { label: "Text & vision", value: "Gemini 2.5 Flash via OpenRouter \u2014 app research, profiles, angles, creative plans, template abstraction" },
  { label: "Video (default)", value: "bytedance/seedance-2.5 \u2014 4\u201330s in one pass, native audio, first-frame guidance, up to 720p" },
  { label: "Video (alternate)", value: "minimax-h3 \u2014 5\u201315s per pass at 2K; 20s and 30s need a second pass" },
  { label: "Model control", value: "VIDEO_MODEL_DEFAULT and VIDEO_MODEL_ALLOWLIST \u2014 the studio refuses any editor model that cannot generate from a prompt" },
  { label: "Research data", value: "Apify TikTok scraper (public data only) \u2014 feeds the optional trend-research workflow" },
];


function SectionHeading({ eyebrow, title, lede, id }) {
  return (
    <div className="mx-auto mb-12 max-w-2xl text-center" id={id}>
      {eyebrow && (
        <span className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-[color:var(--hairline)] bg-[color:var(--indigo-6)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-[color:var(--brand-indigo)]">
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
            <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white shadow-[var(--glow-indigo)]">
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
                  className="gap-2 rounded-xl bg-[color:var(--brand-indigo)] px-4 text-sm font-semibold text-white shadow-[var(--glow-indigo)] hover:bg-[color:var(--brand-indigo-dark)]"
                  data-testid="landing-enter-app-button"
                >
                  Get Started <ArrowRight className="h-4 w-4" />
                </Button>
              </SignUpTrigger>
            </UnauthedOnly>
            <AuthedOnly>
              <Link to="/">
                <Button
                  className="gap-2 rounded-xl bg-[color:var(--brand-indigo)] px-4 text-sm font-semibold text-white shadow-[var(--glow-indigo)] hover:bg-[color:var(--brand-indigo-dark)]"
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
          <div className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] px-3.5 py-1.5 text-sm font-semibold text-[color:var(--brand-indigo)] backdrop-blur-sm">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 animate-pulse-ring rounded-full bg-[color:var(--brand-indigo)]" />
              <span className="relative h-1.5 w-1.5 rounded-full bg-[color:var(--brand-indigo)]" />
            </span>
            App profile &rarr; Hook template &rarr; One coherent video &rarr; Manual publishing
          </div>

          <h1
            className="animate-fade-up font-display mt-8 text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-[4.5rem]"
            style={{ animationDelay: "60ms" }}
          >
            <span className="text-shine">Reusable hooks.</span>
            <br />
            <span className="text-gradient-brand">Real app visuals.</span>
            <br />
            <span className="text-shine">Manual publishing.</span>
          </h1>

          <p
            className="animate-fade-up mx-auto mt-7 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl"
            style={{ animationDelay: "120ms" }}
          >
            HookForge researches your app's website and store listings into a profile you approve,
            recommends a curated hook template, and generates one coherent vertical video with your
            real screenshots, recordings, and logo. Download the MP4 and publish it yourself.
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
                  <Sparkles className="h-5 w-5" /> Get Started
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
              <Link to="/create" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  className="w-full gap-2.5 rounded-xl bg-[color:var(--brand-coral)] px-9 py-6 text-base font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] sm:w-auto"
                >
                  <Sparkles className="h-5 w-5" /> Go to App
                </Button>
              </Link>
              <Link to="/templates" className="w-full sm:w-auto">
                <Button
                  size="lg"
                  variant="outline"
                  className="w-full gap-2.5 rounded-xl border-[color:var(--hairline-strong)] bg-[color:var(--indigo-4)] px-8 py-6 text-base font-semibold backdrop-blur-sm hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] sm:w-auto"
                >
                  <Bookmark className="h-5 w-5" /> Browse Templates
                </Button>
              </Link>
            </AuthedOnly>
          </div>

          <div
            className="animate-fade-up mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground"
            style={{ animationDelay: "220ms" }}
          >
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Approved app profiles
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Real app visuals
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Manual publishing only
            </span>
          </div>

          {/* Stats bar anchor kept for onboarding tour compatibility */}
          <div data-testid="landing-stats" className="hidden" />

        </div>
      </section>

      {/* ---------- How it works ---------- */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-24" data-testid="landing-how-it-works">
        <SectionHeading
          id="how-it-works"
          eyebrow="The workflow"
          title="How It Works"
          lede="From app URL to a downloadable MP4. No source video, no automatic publishing."
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
                <div className="relative mx-auto mb-4 flex h-[52px] w-[52px] items-center justify-center rounded-2xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] font-bold text-white shadow-[var(--glow-indigo)]">
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
          lede="Everything between an app URL and a downloadable MP4."
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="surface surface-interactive shimmer-on-hover group rounded-2xl p-6 text-center"
            >
              <div className="relative mx-auto mb-4 flex h-[52px] w-[52px] items-center justify-center rounded-2xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white shadow-[var(--glow-indigo)]">
                <f.icon className="h-5 w-5" />
                <span className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/25 to-transparent" />
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
          lede="What happens between an approved App Profile and a downloadable video."
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
                        isCoral ? "text-[color:var(--brand-coral)]" : "text-[color:var(--brand-indigo)]"
                      }`}
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <span
                      className={`eyebrow ${
                        isCoral ? "text-[color:var(--brand-coral)]" : "text-[color:var(--brand-indigo)]"
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
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-[color:var(--brand-indigo)]">
                <Zap className="h-3 w-3" /> No source video required
              </span>
              <h2 className="font-display mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                Turn your app listing into a video.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                Paste an app URL, approve the profile, pick a template, and generate one coherent
                video with your real app visuals. Download it and post it yourself &mdash; nothing
                is ever published automatically.
              </p>
              <div className="mt-9 flex flex-col items-center justify-center gap-3.5 sm:flex-row">
                <UnauthedOnly>
                  <SignUpTrigger>
                    <Button
                      size="lg"
                      className="w-full gap-2.5 rounded-xl bg-[color:var(--brand-coral)] px-9 py-6 text-base font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] sm:w-auto"
                    >
                      <Sparkles className="h-5 w-5" /> Get Started
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
                      <Globe className="h-5 w-5" /> Set Up an App Profile
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
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white">
                  <Sparkles className="h-4 w-4" />
                </span>
                <span className="font-display text-base font-bold tracking-tight">HookForge</span>
              </div>
              <p className="mt-3 max-w-xs text-sm leading-relaxed text-muted-foreground">
                Template-based app promos &mdash; research, review, generate, publish manually.
              </p>
            </div>

            <div>
              <p className="eyebrow mb-3">Product</p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link to="/create" className="transition-colors hover:text-foreground">Create Video</Link>
                </li>
                <li>
                  <Link to="/templates" className="transition-colors hover:text-foreground">Hook Templates</Link>
                </li>
                <li>
                  <Link to="/history" className="transition-colors hover:text-foreground">Generation History</Link>
                </li>
                <li>
                  <Link to="/app-profiles" className="transition-colors hover:text-foreground">App Profiles</Link>
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
              &copy; {new Date().getFullYear()} HookForge. Built for mobile app founders.
            </p>
              <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Wand2 className="h-3 w-3 text-[color:var(--brand-indigo)]" /> Template studio with manual publishing
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
