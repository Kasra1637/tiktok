import { Link } from "react-router-dom";
import {
  AuthedOnly,
  UnauthedOnly,
  SignInTrigger,
  SignUpTrigger,
  AccountButton,
} from "../components/auth/AuthControls";
import {
  Sparkles, Clapperboard, Film, Zap, Target,
  FileText, X, Check, Wand2, Briefcase, LayoutTemplate, ShieldCheck, Video, Globe,
} from "lucide-react";
import { Button } from "../components/ui/button";

const FEATURES = [
  {
    icon: Briefcase,
    title: "Start with your app’s facts",
    description:
      "Research your website and store listings, or add the details yourself. Review and approve one profile to use across your videos.",
  },
  {
    icon: Target,
    title: "Make your message specific",
    description:
      "Choose the required video goal, then optionally add an audience angle and tone. These guide template suggestions and the free script plan.",
  },
  {
    icon: LayoutTemplate,
    title: "Find an opening that fits",
    description:
      "Compare goal-matched templates by fit score, reasons, and caveats. Choose one, then add a clear presenter photo for the generated clip.",
  },
  {
    icon: FileText,
    title: "Make the script your own",
    description:
      "Review the free script plan, edit and save the hook, story, and visual directions, then check flagged claims. Render Hook + Story in the final step.",
  },
  {
    icon: Clapperboard,
    title: "Start with a photo, not a shoot",
    description:
      "The final step uses your approved plan and presenter photo to render one Hook + Story clip. It does not include your filmed demo, closing call to action, or on-screen text.",
  },
  {
    icon: ShieldCheck,
    title: "Catch flagged claims early",
    description:
      "Review claim warnings alongside your script. Matches to your banned claims block generation; you still make the final factual review.",
  },
  {
    icon: Film,
    title: "Give your footage a polished frame",
    description:
      "Bring a clip to Demo + CTA. Choose a phone mockup, adjust framing and zoom, and add your own hook text and end card.",
  },
  {
    icon: Video,
    title: "Keep your next idea within reach",
    description:
      "Revisit clips in History, make a draft variation, and record results by hand. Review each new draft before generating another video.",
  },
];

const FLOW_STEPS = [
  {
    step: "1",
    label: "Introduce your app",
    detail: "Add your website or store links—or enter the details yourself. Review the profile and approve the facts.",
  },
  {
    step: "2",
    label: "Choose a goal and audience",
    detail: "Set a goal for the video (required). Add an audience angle and tone if you want to focus the story; both are optional.",
  },
  {
    step: "3",
    label: "Pick a template",
    detail: "Compare goal-matched recommendations and their caveats. Choose a template, then add a clear presenter photo.",
  },
  {
    step: "4",
    label: "Review, then render",
    detail: "Review the free script plan, edit and save it, then check flagged claims. Once the plan passes its checks, render Hook + Story in the final step.",
  },
  {
    step: "5",
    label: "Add your real product demo",
    detail: "Record your demo separately. Demo + CTA styles one clip at a time; combine clips in your own editor, then download and publish them yourself.",
  },
];

/**
 * Problem / solution contrast. Left is the manual path, right is the product.
 *
 * The two lists are written to similar lengths on purpose. The cards sit side by
 * side in a two-column grid, and unbalanced bullets wrap to a ragged second line
 * on one side only — which makes the slow path look busier than it is and
 * quietly flatters the product.
 */
const WEEK_WITHOUT = [
  "Describe your app from scratch whenever you start a new script.",
  "Guess which opening fits your app and people you want to reach.",
  "Start with a blank script and work out the story as you go.",
  "Search your folders for clips and notes from your earlier posts.",
];

const WEEK_WITH = [
  "Reuse your app profile you have already reviewed and approved.",          "Compare the openings with fit scores, reasons, and limitations.",
  "Review an editable script before you start the video render.",
  "Find your clips and manually logged results together in History.",
];

const NAV_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#your-week", label: "Why HookForge" },
  { href: "#features", label: "What you get" },
  { href: "#pipeline", label: "Your control" },
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
    icon: Clapperboard,
    tone: "coral",
    kicker: "Hook + Story",
    title: "Generate the opening, keep the demo real",
    body: "Create one AI-generated clip: an opening hook followed by the story. Your real app demo and closing message are not generated footage. Record the demo yourself, using the separate brief as a guide.",
  },
  {
    icon: Film,
    tone: "indigo",
    kicker: "Demo + CTA",
    title: "Put your own footage in the spotlight",
    body: "Style one source clip at a time—your own recording or a finished Hook + Story. Add a floating or hand-held phone mockup, framing and zoom, plus hook text and an end card you write. Combine separate clips in your own editor when needed; Demo + CTA does not assemble them for you.",
  },
  {
    icon: ShieldCheck,
    tone: "indigo",
    kicker: "Your review",
    title: "Stay in charge of the message",
    body: "Approve your app profile and review the script before rendering. Claim checks flag language to revisit, not a guarantee that every claim is correct. Review the finished clip, download it, and choose where and when to publish.",
  },
];

const QUESTIONS = [
  {
    question: "Can I use footage I already have?",
    answer: "Yes. Open Demo + CTA with your own video, including a screen recording. You don’t need to generate a Hook + Story first.",
  },
  {
    question: "Can I change the script before generating?",
    answer: "Yes. Edit the hook, script, tone, and creative directions, then save them and review the claim check. Once the plan passes its checks it is ready; rendering the video is a separate action.",
  },
  {
    question: "Does the video use my real face and voice?",
    answer: "Your photo guides the AI presenter; it is not a recording of you or a clone of your voice. Check the likeness and delivery in the finished clip before using it.",
  },
  {
    question: "Will my clip have sound, and how can I export it?",
    answer: "Audio depends on the video model you choose; some models produce silent clips. Demo + CTA exports MP4 or WebM depending on your browser and settings. Transparent exports use WebM.",
  },
  {
    question: "Does HookForge post or track results for me?",
    answer: "No. Download your videos and publish them yourself. You can enter views, likes, comments, shares, and saves in History, along with notes and your own verdict. Results are manually logged, not synced from TikTok.",
  },
];


function SectionHeading({ eyebrow, title, lede, id }) {
  return (
    <div className="mx-auto mb-12 max-w-2xl scroll-mt-24 text-center" id={id}>
      {eyebrow && <EyebrowPill className="mb-3">{eyebrow}</EyebrowPill>}
      <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">{title}</h2>
      {lede && <p className="mt-3.5 text-base leading-relaxed text-muted-foreground sm:text-lg">{lede}</p>}
    </div>
  );
}

/**
 * The one uppercase pill on the marketing page: 12px semibold, tracked,
 * brand-indigo on indigo. `strong` is the same pill at one step deeper
 * border and fill, for text sitting on glass rather than on the page.
 */
function EyebrowPill({ strong = false, className, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-[color:var(--brand-indigo)] ${
        strong
          ? "border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)]"
          : "border-[color:var(--hairline)] bg-[color:var(--indigo-6)]"
      }${className ? ` ${className}` : ""}`}
    >
      {children}
    </span>
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

          <nav aria-label="Landing page" className="ml-auto hidden items-center gap-1 lg:flex">
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

          <div className="ml-3 flex shrink-0 items-center gap-2 lg:ml-5">
            <UnauthedOnly>
              <SignInTrigger>
                <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
                  Sign In
                </Button>
              </SignInTrigger>
            </UnauthedOnly>
            <AuthedOnly>
              <AccountButton />
            </AuthedOnly>
          </div>
        </div>
      </header>

      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden" data-testid="landing-hero">
        <Aurora />
        <div className="grid-overlay" />
        <div className="relative z-10 mx-auto max-w-6xl px-5 pb-24 pt-20 text-center sm:pt-28 lg:grid lg:grid-cols-[1.02fr_1fr] lg:items-center lg:gap-14 lg:text-left">
        <div className="min-w-0">
          <h1
            className="animate-fade-up font-display text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-[4.5rem]"
            style={{ animationDelay: "60ms" }}
          >
            <span className="text-shine">Give your app a story</span>
            <br />
            <span className="text-gradient-brand">Worth watching.</span>
          </h1>

          <p
            className="animate-fade-up mx-auto mt-7 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl"
            style={{ animationDelay: "120ms" }}
          >
            Turn your app’s features into an editable script and an AI-generated Hook + Story
            using your photo. Bring your own footage to Demo + CTA for phone mockups,
            on-screen text, and an end card.
          </p>

          <div
            className="animate-fade-up mt-10 flex flex-col items-center justify-center gap-3.5 sm:flex-row lg:justify-start"
            style={{ animationDelay: "180ms" }}
          >

            <UnauthedOnly>
              <SignUpTrigger>
                <Button
                  variant="accent"
                  size="lg"
                  className="w-full gap-2.5 px-9 sm:w-auto"
                >
                  <Sparkles className="h-4 w-4" /> Create your first video
                </Button>
              </SignUpTrigger>
            </UnauthedOnly>
            <AuthedOnly>
              <Button
                asChild
                variant="accent"
                size="lg"
                className="w-full gap-2.5 px-9 sm:w-auto"
              >
                <Link to="/create"><Sparkles className="h-4 w-4" /> Create Video</Link>
              </Button>
            </AuthedOnly>
            <Button
              size="lg"
              variant="outline"
              asChild
              className="w-full px-8 sm:w-auto"
            >
              <a href="#how-it-works">See how it works</a>
            </Button>
          </div>

          <UnauthedOnly>
            <p className="mt-5 text-sm text-muted-foreground">
              Already have an account?{" "}
              <SignInTrigger>
                <button className="font-semibold text-[color:var(--brand-indigo)] hover:underline">Sign in</button>
              </SignInTrigger>
            </p>
          </UnauthedOnly>

          <div
            className="animate-fade-up mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground lg:justify-start"
            style={{ animationDelay: "220ms" }}
          >
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Review before rendering
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Keep your real demo
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" /> Publish on your terms
            </span>
          </div>
          </div>
          {/* The app itself, beside the pitch: the real Create Video
              journey (profile → angle → goal → ranked templates) plus the
              editable Demo + CTA canvas, recorded from the running app.
              A minimal floating card frames it: gradient hairline, a URL
              pill naming where this lives, and a portrait viewport matching
              the capture so the whole interface shows with no cropping.
              Playback runs at 4x so the full journey fits the loop. Autoplay
              is silent and loops; under reduced motion it stays paused on
              the poster frame. */}
          <figure
            className="animate-fade-up mx-auto mt-12 w-full max-w-[360px] lg:mx-0 lg:mt-0"
            style={{ animationDelay: "280ms" }}
            data-testid="landing-hero-shot"
          >
            <div className="border-gradient relative rounded-2xl p-[1px] shadow-[0_24px_80px_-24px_rgb(0_0_0/0.8)]">
              <div className="overflow-hidden rounded-2xl bg-black">
                <div className="flex items-center gap-2 border-b border-[color:var(--hairline)] bg-white/[0.02] px-3 py-2">
                  <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
                  <Globe className="h-3 w-3 shrink-0 text-muted-foreground" />
                  <span className="truncate rounded-full border border-[color:var(--hairline)] bg-white/[0.03] px-2.5 py-0.5 text-xs text-muted-foreground">
                    hookforge.app/create
                  </span>
                  <span className="ml-auto shrink-0 text-xs text-muted-foreground">4× loop</span>
                </div>
                <div className="relative aspect-[9/13] w-full">
                  <video
                    className="absolute inset-0 block h-full w-full object-contain"
                    autoPlay
                    muted
                    loop
                    playsInline
                    preload="metadata"
                    poster={`${process.env.PUBLIC_URL}/hero-demo-poster.jpg`}
                    aria-label="Screen recording at 4x speed: the Create Video wizard interface and the Demo CTA canvas, full interface with no page header or footer"
                    ref={(v) => {
                      if (!v) return;
                      v.muted = true;
                      if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) v.pause();
                    }}
                  >
                    <source src={`${process.env.PUBLIC_URL}/hero-demo.webm`} type="video/webm" />
                    <source src={`${process.env.PUBLIC_URL}/hero-demo.mp4`} type="video/mp4" />
                  </video>
                </div>
              </div>
            </div>
          </figure>
        </div>
      </section>

      {/* ---------- How it works ---------- */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-24" data-testid="landing-how-it-works">
        <SectionHeading
          id="how-it-works"
          eyebrow="How it works"
          title="From app facts to your next story"
          lede="Build the opening around what your app does. Review the message before you turn it into video."
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
                className="surface surface-interactive shimmer-on-hover group rounded-2xl text-center"
              >
                <div className="relative mx-auto mb-5 flex h-[52px] w-[52px] items-center justify-center rounded-2xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] font-bold text-white shadow-[var(--glow-indigo)]">
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

      {/* ---------- Your week: problem / solution ---------- */}
      <section
        className="relative z-10 mx-auto max-w-6xl px-5 pb-24"
        data-testid="landing-your-week"
      >
        <SectionHeading
          id="your-week"
          eyebrow="The difference"
          title="Spend less effort starting from scratch"
          lede="Keep your app’s facts, creative choices, and past work close by—so your next idea has somewhere to start."
        />

        <div className="grid gap-5 lg:grid-cols-2">
          <div className="surface rounded-2xl">
            <span className="eyebrow">Starting from scratch</span>
            <ul className="mt-5 space-y-3.5">
              {WEEK_WITHOUT.map((line) => (
                <li key={line} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                  <X className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* `.surface` is un-layered CSS, so it beats any Tailwind border or
              background utility placed on the same element. The gradient hairline
              is a masked pseudo-element instead, which nothing can override. */}
          <div className="border-gradient relative rounded-2xl p-[1px]">
            <div className="surface surface-interactive shimmer-on-hover rounded-2xl">
              <span className="eyebrow text-[color:var(--brand-indigo)]">With HookForge</span>
              <ul className="mt-5 space-y-3.5">
                {WEEK_WITH.map((line) => (
                  <li key={line} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Features ---------- */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 pb-24" data-testid="landing-features">
        <SectionHeading
          id="features"
          eyebrow="What you get"
          title="A clearer way to tell your app’s story"
          lede="From the first idea to the clip you review, keep the message grounded in your product and shaped by you."
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="surface surface-interactive shimmer-on-hover group rounded-2xl text-center"
            >
              <div className="relative mx-auto mb-5 flex h-[52px] w-[52px] items-center justify-center rounded-2xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white shadow-[var(--glow-indigo)]">
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
      <section className="relative z-10 mx-auto max-w-5xl px-5 pb-24" data-testid="landing-capabilities">
        <SectionHeading
          id="pipeline"
          eyebrow="Your control"
          title="Your story. Your real product."
          lede="Generate the opening, show the real app, and decide what makes the final cut."
        />

        <div className="space-y-4">
          {PIPELINE_BLOCKS.map((block) => {
            const isCoral = block.tone === "coral";
            return (
              <div
                key={block.title}
                data-testid={`landing-capability-${block.kicker === "Hook + Story" ? "generation" : block.kicker === "Demo + CTA" ? "editor" : "review"}`}
                className="surface surface-interactive rounded-2xl"
              >
                <div className="flex flex-col gap-5 sm:flex-row sm:gap-5">
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

          <div className="surface rounded-2xl" data-testid="landing-questions">
            <h3 className="font-display text-lg font-semibold">A few things worth knowing</h3>
            <div className="mt-5 divide-y divide-border/60">
              {QUESTIONS.map((q) => (
                <details key={q.question} className="py-4">
                  <summary className="cursor-pointer font-display text-sm font-semibold text-foreground">
                    {q.question}
                  </summary>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{q.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Final CTA ---------- */}
      <section className="relative z-10 mx-auto max-w-4xl px-5 pb-24" data-testid="landing-final-cta">
        <div className="border-gradient relative rounded-3xl p-[1px]">
          <div className="surface-glass relative overflow-hidden rounded-3xl px-6 py-12 text-center sm:px-12 sm:py-16">
            <div className="spotlight-indigo absolute inset-0" aria-hidden="true" />
            <div className="relative">
              <EyebrowPill strong>
                <Zap className="h-3 w-3" /> Ready when you are
              </EyebrowPill>
              <h2 className="font-display mt-5 text-3xl font-bold tracking-tight sm:text-4xl">
                Make your next app story.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                Start with your app’s facts and a message you want to share. Review the script,
                generate your Hook + Story, and keep the real product at the heart of your demo.
              </p>
              <div className="mt-9 flex flex-col items-center justify-center gap-3.5 sm:flex-row">
                <UnauthedOnly>
                  <SignUpTrigger>
                    <Button
                      variant="accent"
                      size="lg"
                      className="w-full gap-2.5 px-9 sm:w-auto"
                    >
                      <Sparkles className="h-4 w-4" /> Create your first video
                    </Button>
                  </SignUpTrigger>
                </UnauthedOnly>
                <AuthedOnly>
                  <Button
                    asChild
                    variant="accent"
                    size="lg"
                    className="w-full gap-2.5 px-9 sm:w-auto"
                  >
                    <Link to="/create"><Sparkles className="h-4 w-4" /> Create Video</Link>
                  </Button>
                </AuthedOnly>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="w-full gap-2.5 px-8 sm:w-auto"
                >
                  <Link to="/demo-cta"><Film className="h-4 w-4" /> Style your own footage</Link>
                </Button>
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
                App stories grounded in your product. Generate a Hook + Story, style your
                own footage, and publish on your terms.
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
                  <Link to="/brand" className="transition-colors hover:text-foreground">App Profile</Link>
                </li>
                <li>
                  <Link to="/demo-cta" className="transition-colors hover:text-foreground">Demo + CTA</Link>
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
              &copy; {new Date().getFullYear()} HookForge. Built for mobile-app founders and marketers.
            </p>
            <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <Wand2 className="h-3 w-3 text-[color:var(--brand-indigo)]" /> Your message. Your final say.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
