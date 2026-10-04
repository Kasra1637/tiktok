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
  TrendingUp, ArrowRight, Zap, Target, Layers,
  FileText, BadgeAlert, MessageSquareQuote, ChartLine,
  X, Check, Wand2, Briefcase, LayoutTemplate, ShieldCheck, Video,
} from "lucide-react";
import { Button } from "../components/ui/button";

const FEATURES = [
  {
    icon: Briefcase,
    title: "Every video starts from your app",
    description:
      "Paste your links in once. We read what your app does and who it is really for, so that no video starts as a template with your name typed in.",
  },
  {
    icon: Target,
    title: "One choice steers everything",
    description:
      "Say who you're talking to and what you want them to do. That single choice shapes the hook, the promise and the middle.",
  },
  {
    icon: LayoutTemplate,
    title: "Ten curated openers, one already picked",
    description:
      "The best fit for your app and goal is preselected. Swap in one click, and every card says why it fits and where it falls short.",
  },
  {
    icon: Wand2,
    title: "No blind picks",
    description:
      "Each one shows its score, why it fits your app, and its limits. I never ask you to take my word for it.",
  },
  {
    icon: FileText,
    title: "Free until the render",
    description:
      "The script, the shot plan and the strategy cost nothing. Read all three, rewrite any word, and the first thing that costs you money is the render.",
  },
  {
    icon: Clapperboard,
    title: "A hook, and a middle",
    description:
      "The first seconds stop the scroll. The middle makes the case, and stops right where your demo takes over. One render, no seams or assembly.",
  },
  {
    icon: MessageSquareQuote,
    title: "Answers why they haven't downloaded",
    description:
      "The middle works through the objections you get in the comments, one at a time, and never cramming two answers into one breath.",
  },
  {
    icon: Film,
    title: "No fake screenshots. Ever.",
    description:
      "No drawn interfaces, no made-up numbers, no generated demo. Captions come only from the script you approved.",
  },
  {
    icon: ShieldCheck,
    title: "Your banned list is law",
    description:
      "Your script is re-checked on every edit and again at the render. Anything on your never-use list blocks the paid click, so it cannot slip through a revision.",
  },
  {
    icon: Layers,
    title: "The presenter is you",
    description:
      "One photo carries the entire piece. No avatar, no voice clone, no stand-in, and just the one photo, so nobody is ever in doubt whose face it is.",
  },
  {
    icon: ChartLine,
    title: "Every post teaches the next one",
    description:
      "Log what each video has actually done. What worked for this app shows up beside the next one we recommend.",
  },
  {
    icon: TrendingUp,
    title: "See what each video cost and earned",
    description:
      "Success rate, failures, spend and rework, broken down by app, opening, model, and audience.",
  },
  {
    icon: Check,
    title: "Skip it and it sinks",
    description:
      "Swap away from an opening and it slides down the list. Use one and it keeps climbing. Your taste becomes our ranking.",
  },
  {
    icon: BadgeAlert,
    title: "Receipts on every render",
    description:
      "The exact prompt sent, the claim check as it stands, the model, the cost and where it came from, plus any error. Audit it all.",
  },
  {
    icon: Zap,
    title: "Where your openings come from",
    description:
      "Ten structures we wrote by ourselves, ranked by what your own posts actually did. No scraping of creators, no borrowed faces, no invented results.",
  },
  {
    icon: Video,
    title: "You finish the video",
    description:
      "Download the hook and the middle. Record your demo, add your close and post it. We never touch your account.",
  },
];




const FLOW_STEPS = [
  {
    step: "1",
    label: "Paste",
    icon: Briefcase,
    detail: "Your links. We read what your app does, then write the profile for you to approve.",
  },
  {
    step: "2",
    label: "Choose",
    icon: Target,
    detail: "Who you're talking to, and what you want them to do. I rank openings to match.",
  },
  {
    step: "3",
    label: "Read",
    icon: FileText,
    detail: "Your photo. Read the script, the shot plan and the strategy. Edit any line, spend nothing at all.",
  },
  {
    step: "4",
    label: "Render",
    icon: Layers,
    detail: "One render: the hook, then a middle that stops where you reach for the phone.",
  },
  {
    step: "5",
    label: "Finish",
    icon: Video,
    detail: "Record your demo and add your close, then post it wherever your audience is.",
  },
];

/**
 * Problem / solution contrast. Left is the manual path, right is the product.
 *
 * The two lists are written to matching character counts on purpose. The cards
 * sit side by side in a two-column grid, and unbalanced bullets wrap to a ragged
 * second line on one side only — which makes the slow path look busier than it
 * is and quietly flatters the product. `check-render-smoke.cjs` asserts the
 * match, so editing one line without the other fails the gate instead of
 * shipping a lopsided card.
 */
const WEEK_WITHOUT = [
  "Book the shoot. Lose an afternoon, and hope the light was good.",
  "Write the script yourself, then read it back and hate how it sounds.",
  "Film it four times because the first one had you squinting.",
  "Pay someone to edit it, then wonder all night about those 3 seconds.",
  "Post it, get 400 views, and blame the algorithm for all of it.",
  "Do the whole thing again next week, from scratch, on one hook.",
];

const WEEK_WITH = [
  "Paste the link. We read your app and write the profile for you.",
  "Pick who is watching. We write six openings, then you take the best.",
  "Read it, change any line you like, and nothing is charged.",
  "Render the hook and the middle, then add your own demo and a close.",
  "Post it, log the views, and let them shape the very next one.",
  "Next week it is the same profile, already knowing what worked.",
];


const NAV_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#your-week", label: "Your week" },
  { href: "#features", label: "What you get" },
  { href: "#pipeline", label: "How it's made" },
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
    title: "Read Before We Write",
    body: (
      <>
        Your links become a profile: what the app does, who it is for, and what you may claim.
        You approve it before anything is generated, and no refresh quietly overwrites wording.
      </>
    ),
  },
  {
    icon: Clapperboard,
    tone: "coral",
    kicker: "Generation",
    title: "Two Sections, One Render",
    body: (
      <>
        The hook is the first few seconds. The middle develops it, then ends at the moment the
        presenter would reach for their phone, which is exactly where your own demo picks up.
        One job, one file, with sound wherever the model supports it.
      </>
    ),
  },
  {
    icon: Layers,
    tone: "coral",
    kicker: "The Handoff",
    title: "The Middle Is Built to Stop",
    body: (
      <>
        There is no product demo and no closing card in the generated footage, on purpose: the
        plan works out what you should record and hands it to you as a note, and the video ends
        on the frame your demo continues from. You attach the demo, add your close, and post it.
      </>
    ),
  },
  {
    icon: Film,
    tone: "indigo",
    kicker: "Finishing",
    title: "The Scene Is Built Around You",
    body: (
      <>
        Your photograph is the only visual input, and the room, the light, and the framing get
        locked once for the whole piece, so the hook and the middle cannot disagree about where
        this is happening. Captions layer on afterwards, taken from the script you approved.
      </>
    ),
  },
  {
    icon: Search,
    tone: "indigo",
    kicker: "On trust",
    title: "Curated, Not Proven.",
    body: (
      <>
        Every opening ships as a written structure, not a promise. We tell you plainly when
        we have no numbers behind one yet, so you can judge it on the post you can see.
      </>
    ),
  },
];




const MODELS = [
  { label: "Words & analysis", value: "gpt-4o-mini — your profile, angles, openings, scripts, and shot plans" },
  { label: "Video", value: "MiniMax H3 by default — 2K picture, native sound — or H3 Max for sharper prompt adherence at 768p, or Grok for a silent 720p clip at half the price. One render of up to 15 seconds either way; each template declares the length its mechanic suits. Your pick sticks." },
  { label: "Finishing touches", value: "Captions, layered on precisely" },
  { label: "Provenance", value: "No scraped creators, no lifted scripts, no invented numbers. The only face in your video is the one photo that you chose." },
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
      <section className="relative overflow-hidden" data-testid="landing-hero">
        <Aurora />
        <div className="grid-overlay" />
        <div className="relative z-10 mx-auto max-w-5xl px-5 pb-24 pt-20 text-center sm:pt-28">
          <h1
            className="animate-fade-up font-display text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl lg:text-[4.5rem]"
            style={{ animationDelay: "60ms" }}
          >
            <span className="text-shine">I finally made my own launch video.</span>
            <br />
            <span className="text-gradient-brand">Starring you.</span>
          </h1>

          <p
            className="animate-fade-up mx-auto mt-7 max-w-2xl text-lg leading-relaxed text-muted-foreground sm:text-xl"
            style={{ animationDelay: "120ms" }}
          >
            Paste your links. Approve what it found. Read every word. Then film
            the demo and post it tonight.
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
                  <Sparkles className="h-5 w-5" /> Make my first video
                </Button>
              </SignUpTrigger>
              <SignInTrigger>
                <Button
                  size="lg"
                  variant="outline"
                  className="w-full gap-2.5 rounded-xl border-[color:var(--hairline-strong)] bg-[color:var(--indigo-4)] px-8 py-6 text-base font-semibold backdrop-blur-sm hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] sm:w-auto"
                >
                  I already have an account
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

        </div>
      </section>

      {/* ---------- How it works ---------- */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 py-24" data-testid="landing-how-it-works">
        <SectionHeading
          id="how-it-works"
          eyebrow="How it works"
          title="From your link to your own promo"
          lede="Five steps, and only one of them is you on camera. That step is your demo, and I would not hand it to a model."
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

      {/* ---------- Your week: problem / solution ---------- */}
      <section
        className="relative z-10 mx-auto max-w-6xl px-5 pb-24"
        data-testid="landing-your-week"
      >
        <SectionHeading
          id="your-week"
          eyebrow="The difference"
          title="What your week looks like"
          lede="Same app either way. One version cost me a Saturday, the other cost me a coffee."
        />

        <div className="grid gap-5 lg:grid-cols-2">
          <div className="surface rounded-2xl p-6 sm:p-7">
            <span className="eyebrow">The old way</span>
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
            <div className="surface surface-interactive shimmer-on-hover rounded-2xl p-6 sm:p-7">
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
          eyebrow="Everything in between"
          title="You bring a link and a photo"
          lede="We write and then render everything up to the moment you reach for your phone. Every one of those five steps is yours to redo."
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
          title="How it gets made"
          lede="What happens between your link and a post you are happy to make."
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
                Your next promo is one photo away.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                Paste your link. Approve the profile. Pick your goal and opening. You get
                a hook and a middle starring you, then film the demo, add the close and
                post it.
              </p>
              <div className="mt-9 flex flex-col items-center justify-center gap-3.5 sm:flex-row">
                <UnauthedOnly>
                  <SignUpTrigger>
                    <Button
                      size="lg"
                      className="w-full gap-2.5 rounded-xl bg-[color:var(--brand-coral)] px-9 py-6 text-base font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] sm:w-auto"
                    >
                      <Sparkles className="h-5 w-5" /> Make my first video
                    </Button>
                  </SignUpTrigger>
                  <SignInTrigger>
                    <Button
                      size="lg"
                      variant="outline"
                      className="w-full gap-2.5 rounded-xl border-[color:var(--hairline-strong)] bg-[color:var(--indigo-4)] px-8 py-6 text-base font-semibold hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] sm:w-auto"
                    >
                      I already have an account
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
                      <Globe className="h-5 w-5" /> Open your app profile
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
                The hook and the middle, made from a link and a photo. You film the demo, add
                the close, and post it yourself.
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
