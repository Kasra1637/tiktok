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
  FileText, BadgeAlert,
  RotateCcw, Check, Wand2, Briefcase, LayoutTemplate, ShieldCheck, Download,
} from "lucide-react";
import { Button } from "../components/ui/button";

const FEATURES = [
  {
    icon: Briefcase,
    title: "Your App Hub",
    description:
      "Paste your links once. We draft the profile, you approve it, and every video after that starts from it.",
  },
  {
    icon: Target,
    title: "Audiences & Angles",
    description:
      "Pick who you're talking to and what you want them to do. The angle hands you the hook, the promise and the close.",
  },
  {
    icon: LayoutTemplate,
    title: "Hook Template Library",
    description:
      "Never start from a blank page. Favourite what works, reshape what doesn't.",
  },
  {
    icon: Wand2,
    title: "Smart Template Picks",
    description:
      "A shortlist for your app and angle. Each pick tells you why it fits, and where it falls short.",
  },
  {
    icon: FileText,
    title: "Script First, Video Second",
    description:
      "Read the script before you pay for the video. Rewrite any word of it. Planning itself costs nothing.",
  },
  {
    icon: Clapperboard,
    title: "Ten to Thirty Seconds",
    description:
      "10, 15, 20 or 30 seconds, vertical. Hooks run 2 to 6, because four seconds is the cheapest test of the whole idea.",
  },
  {
    icon: Film,
    title: "No Fake UI",
    description:
      "The model is forbidden from drawing your screens, prices or ratings. Captions and the CTA come from the script you approved.",
  },
  {
    icon: ShieldCheck,
    title: "Claims, Checked",
    description:
      "A checker, not the AI, re-reads your script on every edit. Anything on your never-use list stays blocked; prices your profile never listed get flagged.",
  },
  {
    icon: Layers,
    title: "One Photo, You On Camera",
    description:
      "One photograph. That face is you in every clip. No avatar, no voice clone, no stand-in.",
  },
  {
    icon: Music2,
    title: "Sound, Generated With It",
    description:
      "Speech and room tone arrive with the clip. No audio files to license, no mixing. Add the trending sound where you post.",
  },
  {
    icon: RotateCcw,
    title: "Change One Thing",
    description:
      "Swap the hook, the CTA, the tone, the template or the length and get a fresh draft back. Nothing renders until you say so.",
  },
  {
    icon: TrendingUp,
    title: "Measured, Not Guesswork",
    description:
      "Success rate, failures, spend and rework, broken down by app, template, model and audience. Unpriced runs stay labelled unpriced.",
  },
  {
    icon: Check,
    title: "Feedback Loop",
    description:
      "Reject a template and it slides down the list. Your winners keep climbing.",
  },
  {
    icon: BadgeAlert,
    title: "Every Run, Accounted For",
    description:
      "Every video shows its receipts: the exact prompt sent, the claim check at generation time, the model, the cost and where it came from, any error.",
  },
  {
    icon: Search,
    title: "Hook Anatomy",
    description:
      "Paste a TikTok link. We read the first three seconds — pacing, cuts, faces, on-screen text, audio — then score the hook.",
  },
  {
    icon: Download,
    title: "You Post It",
    description:
      "Download it, post it wherever. We never touch your accounts.",
  },
];





const FLOW_STEPS = [
  {
    step: "1",
    label: "Profile",
    icon: Briefcase,
    detail: "Paste your links. We draft your app profile; you approve it.",
  },
  {
    step: "2",
    label: "Brief",
    icon: Target,
    detail: "Pick your audience and goal. Get template picks with reasons.",
  },
  {
    step: "3",
    label: "Plan",
    icon: FileText,
    detail: "Add your photo. Get the script and shot plan, then edit every line.",
  },
  {
    step: "4",
    label: "Grow",
    icon: Layers,
    detail: "Approve the hook, then extend it. Each segment picks up from the last frame.",
  },
  {
    step: "5",
    label: "Deliver",
    icon: Download,
    detail: "Generate, download, post it wherever your audience is.",
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
    title: "Studied, Then Approved",
    body: (
      <>
        Your links become a profile: features, audience, pricing, and what you're allowed to
        claim. You approve it before anything generates, and a refresh never overwrites that.
      </>
    ),
  },
  {
    icon: Clapperboard,
    tone: "coral",
    kicker: "Generation",
    title: "One Smooth Video",
    body: (
      <>
        Hook and ending arrive in a single vertical clip, with sound where the model supports
        it. A second pass only stretches the length or replaces a dead segment.
      </>
    ),
  },
  {
    icon: Layers,
    tone: "coral",
    kicker: "Continuity",
    title: "Beat by Beat, Seam Held",
    body: (
      <>
        Extend the hook and the last frame becomes the next first frame, so you, the light and
        the room carry through instead of jumping. If a model drops a reference, we name the one
        it dropped.
      </>
    ),
  },
  {
    icon: Film,
    tone: "indigo",
    kicker: "Finishing",
    title: "Your Words, Locked In",
    body: (
      <>
        The scene gets built around you from your app's verified facts. Captions and the end
        card layer on afterwards, taken from the script you approved.
      </>
    ),
  },
  {
    icon: Search,
    tone: "indigo",
    kicker: "Research",
    title: "Ideas, Not Copies",
    body: (
      <>
        Patterns turn into template drafts that wait for your review. No creator's face, voice
        or sound ever crosses into what you make.
      </>
    ),
  },
];




const MODELS = [
  { label: "Words & analysis", value: "Gemini 2.5 Flash — research, profiles, angles, scripts" },
  { label: "Video", value: "MiniMax H3 — 2K picture, native sound, 5 to 15 seconds per pass; longer videos are built segment by segment" },
  { label: "Finishing touches", value: "Captions and end card, layered on precisely" },
  { label: "Trend spotting", value: "Public TikTok metadata via a research API key — Trend Research tab only" },
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
          <h1
            className="animate-fade-up font-display text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-[4.5rem]"
            style={{ animationDelay: "60ms" }}
          >
            <span className="text-shine">Your face, not a stranger's.</span>
            <br />
            <span className="text-gradient-brand">Photo in, promo out.</span>
            <br />
            <span className="text-shine">Posted by you, not by us.</span>
          </h1>

          <p
            className="animate-fade-up mx-auto mt-7 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl"
            style={{ animationDelay: "120ms" }}
          >
            People trust a face they know. Yours anchors every clip, and the scene
            around it comes from what we know about your app.
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
            </AuthedOnly>
          </div>

          <div
            className="animate-fade-up mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground"
            style={{ animationDelay: "220ms" }}
          >
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> You approve every word
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Your real face
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Nothing auto-posts
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Nothing spent until you render
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
          eyebrow="Dead simple"
          title="App Link to Video in 5 Steps"
          lede="No filming. No editing. No source video. Just five steps."
        />

        <div className="relative">
          {/* Connecting line behind the cards on wide screens */}
          <div
            aria-hidden="true"
            className="absolute left-0 right-0 top-[42px] hidden h-px bg-gradient-to-r from-transparent via-[color:var(--indigo-25)] to-transparent lg:block"
          />
          <div className="relative grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {FLOW_STEPS.map((s) => (
              <div
                key={s.step}
                className="surface surface-interactive shimmer-on-hover group rounded-2xl p-5 text-center"
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
          title="Everything Handled"
          lede="From a link to a finished video. Every step in between handled."
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
          title="How It Gets Made"
          lede="How a link becomes a video you're happy to post."
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
                <h3 className="font-display mt-1 text-base font-semibold sm:text-lg">The Engine Room</h3>
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
                <Zap className="h-3 w-3" /> Ready when you are
              </span>
              <h2 className="font-display mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                Your next promo is one link away.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                Paste your link. Approve the profile. Pick a hook. Get a promo with you
                in it, ready to post.
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
                  <Link to="/" className="w-full sm:w-auto">
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
                      <Globe className="h-5 w-5" /> Open Your App Profile
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
                App promos for founders. Paste a link, get a video with you in it, post it yourself.
              </p>
            </div>

            <div>
              <p className="eyebrow mb-3">Product</p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link to="/create" className="transition-colors hover:text-foreground">Create Video</Link>
                </li>
                <li>
                  <Link to="/history" className="transition-colors hover:text-foreground">Generation History</Link>
                </li>
                <li>
                  <Link to="/app-profiles" className="transition-colors hover:text-foreground">Your app</Link>
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
