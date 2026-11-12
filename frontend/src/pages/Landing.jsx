import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AuthedOnly,
  UnauthedOnly,
  SignInTrigger,
  SignUpTrigger,
  AccountButton,
} from "../components/auth/AuthControls";
import {
  Sparkles, Clapperboard, Film, Target,
  FileText, X, Check, Briefcase, LayoutTemplate, ShieldCheck, Video, Gauge,
  Pause, Play,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { EyebrowPill, MarketingHeader, MarketingFooter, FinalCta } from "../components/Marketing";

const FEATURES = [
  {
    icon: Briefcase,
    title: "Your facts first, every single time",
    description:
      "Your website and store listing become an App Profile you review and approve once — then reuse on every video, so the story never drifts from the product itself.",
  },
  {
    icon: Target,
    title: "Every video has one clear job to do",
    description:
      "A required audience angle and video goal you set steer the templates and the script, so each post aims at one viewer and one outcome — not everyone and nothing.",
  },
  {
    icon: LayoutTemplate,
    title: "The opening built to earn the watch",
    description:
      "Templates are ranked by fit to your angle and your goal, with reasons and caveats up front. Pick the opening built to hold your first three seconds, every time.",
  },
  {
    icon: FileText,
    title: "A script that sounds just like you.",
    description:
      "Review the free script plan: a hook and story in plain words — a real person talking to a phone, never ad copy. Edit and save every line before the paid render.",
  },
  {
    icon: Clapperboard,
    title: "One photo, and zero shoot days ever",
    description:
      "Your approved plan and one presenter photo render into a finished Hook + Story clip. No camera, no crew, no reshoot when a line changes — edit and render again.",
  },
  {
    icon: Gauge,
    title: "A craft grade before you pay a cent",
    description:
      "Every plan is graded on craft before you pay: the score names the weakest line and the next rewrite to try. It advises only — no grade ever blocks your renders.",
  },
  {
    icon: Film,
    title: "Your demo, finished like your posts",
    description:
      "Bring your real footage to Demo + CTA: phone mockups, framing and zoom, a second clip or a live overlay, hook text and an end card — exported as one TikTok MP4.",
  },
  {
    icon: Video,
    title: "Results that teach your next video.",
    description:
      "Post it, paste the link and the numbers — views, 3-second retention, average watch, saves, shares. After three posted clips, the lessons steer your next videos.",
  },
];

/**
 * Custom step illustrations: one small line scene per step, all sharing
 * the same 200x150 canvas, stroke weight, and indigo tokens. Every scene
 * is built on the step-3 chassis Kasra picked out — three stacked square
 * cards (faint, mid, front) forming one piece — and only the glyph on the
 * front card changes: 1) an app tile and its approved check; 2) a target
 * and the one viewer; 3) a play mark and its fit bar; 4) script lines
 * becoming a render; 5) a phone playing your real demo.
 */
const STEP_ART = {
  "1": (
    <svg viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="30" width="108" height="68" rx="10" opacity="0.35" />
      <rect x="50" y="42" width="108" height="68" rx="10" opacity="0.6" />
      <rect x="66" y="54" width="108" height="68" rx="10" fill="var(--indigo-10)" />
      <rect x="82" y="72" width="30" height="30" rx="8" fill="var(--indigo-25)" fillOpacity="0.35" />
      <line x1="124" y1="82" x2="160" y2="82" opacity="0.55" />
      <line x1="124" y1="98" x2="146" y2="98" opacity="0.55" />
      <circle cx="158" cy="112" r="12" fill="var(--brand-indigo)" stroke="none" />
      <path d="M151.5 112 l4.5 4.5 l8.5 -9.5" stroke="#fff" strokeWidth="4" />
    </svg>
  ),
  "2": (
    <svg viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="30" width="108" height="68" rx="10" opacity="0.35" />
      <rect x="50" y="42" width="108" height="68" rx="10" opacity="0.6" />
      <rect x="66" y="54" width="108" height="68" rx="10" fill="var(--indigo-10)" />
      <circle cx="102" cy="88" r="16" />
      <circle cx="102" cy="88" r="8" />
      <circle cx="102" cy="88" r="2.5" fill="var(--brand-indigo)" stroke="none" />
      <circle cx="146" cy="79" r="7.5" />
      <path d="M133 105 a13 9.5 0 0 1 26 0" />
    </svg>
  ),
  "3": (
    <svg viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="30" width="108" height="68" rx="10" opacity="0.35" />
      <rect x="50" y="42" width="108" height="68" rx="10" opacity="0.6" />
      <rect x="66" y="54" width="108" height="68" rx="10" fill="var(--indigo-10)" />
      <path d="M86 76 l16 9 l-16 9 Z" fill="var(--brand-indigo)" stroke="none" />
      <line x1="114" y1="80" x2="162" y2="80" opacity="0.3" strokeWidth="6" />
      <line x1="114" y1="80" x2="148" y2="80" strokeWidth="6" />
      <line x1="114" y1="100" x2="150" y2="100" opacity="0.5" />
      <circle cx="162" cy="64" r="5" fill="var(--brand-indigo)" stroke="none" />
    </svg>
  ),
  "4": (
    <svg viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="30" width="108" height="68" rx="10" opacity="0.35" />
      <rect x="50" y="42" width="108" height="68" rx="10" opacity="0.6" />
      <rect x="66" y="54" width="108" height="68" rx="10" fill="var(--indigo-10)" />
      <line x1="84" y1="74" x2="118" y2="74" opacity="0.55" />
      <line x1="84" y1="90" x2="118" y2="90" opacity="0.55" />
      <line x1="84" y1="106" x2="104" y2="106" opacity="0.55" />
      <circle cx="145" cy="90" r="15" fill="var(--brand-indigo)" stroke="none" />
      <path d="M140.5 81 l11 9 l-11 9 Z" fill="#fff" stroke="none" />
    </svg>
  ),
  "5": (
    <svg viewBox="0 0 200 150" fill="none" stroke="var(--brand-indigo)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="34" y="30" width="108" height="68" rx="10" opacity="0.35" />
      <rect x="50" y="42" width="108" height="68" rx="10" opacity="0.6" />
      <rect x="66" y="54" width="108" height="68" rx="10" fill="var(--indigo-10)" />
      <rect x="86" y="66" width="34" height="44" rx="7" />
      <path d="M98 80 l12 7 l-12 7 Z" fill="var(--brand-indigo)" stroke="none" />
      <rect x="93" y="99" width="20" height="6" rx="3" fill="var(--brand-indigo)" fillOpacity="0.85" stroke="none" />
      <line x1="134" y1="76" x2="160" y2="76" opacity="0.55" />
      <line x1="134" y1="90" x2="152" y2="90" opacity="0.55" />
    </svg>
  ),
};

/**
 * The five steps as a visual strip. Kasra rejected screenshot stills for
 * this section, so each step carries a custom branded illustration from
 * STEP_ART below — one line family, the app's indigo tokens, each scene
 * drawn to show what the step does. Titles, lines, and outcomes are the
 * copy Kasra approved; the strip sits on the plain section background
 * (he also rejected the band that used to sit behind the five cards).
 */
const FLOW_STEPS = [
  {
    step: "1",
    label: "Introduce your app",
    line: "Add your store or website URL, review the draft, and approve the facts — every video starts from them.",
    outcome: "Built from your facts",
  },
  {
    step: "2",
    label: "Pick goal + viewer",
    line: "Pick an audience angle and set a goal — both are required before anything downstream is written.",
    outcome: "One viewer, one outcome",
  },
  {
    step: "3",
    label: "Pick your template",
    line: "Compare the ranked templates and their caveats, then add a clear presenter photo.",
    outcome: "Openings that earn the watch",
  },
  {
    step: "4",
    label: "Review then render",
    line: "The plan is free: review it, edit and save it, check the craft grade — only the render is paid.",
    outcome: "A clip worth posting",
  },
  {
    step: "5",
    label: "Add your real demo",
    line: "Style a base clip, add a Second clip or a phone overlay, export one MP4, and publish them yourself.",
    outcome: "Your demo stays yours",
  },
];

/**
 * The hero loop: the five steps, cycling in the frame beside the headline.
 * Kasra replaced the recorded tour footage with this — the same STEP_ART
 * illustrations the How it works strip uses, one at a time, so the whole
 * flow plays in one place with no video bytes at all. The pace is set to
 * stay comfortable: four seconds a step with a slow crossfade, a pause
 * while the pointer rests on the frame, and a pause control beside the
 * dots (an autoplaying loop needs a way to stop it). Under reduced motion
 * the loop never starts — the first step sits still and the dots step
 * through by hand.
 */
const HERO_FLOW_MS = 4000;

function HeroFlow() {
  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(!reduceMotion);
  const [hovering, setHovering] = useState(false);

  useEffect(() => {
    if (!playing || hovering) return undefined;
    const id = window.setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      setActive((i) => (i + 1) % FLOW_STEPS.length);
    }, HERO_FLOW_MS);
    return () => window.clearInterval(id);
  }, [playing, hovering]);

  const toggleLabel = playing ? "Pause the step loop" : "Play the step loop";

  return (
    <div
      className="hero-flow"
      role="group"
      aria-label="How HookForge works, in five steps"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div className="hero-flow-slides">
        {FLOW_STEPS.map((s, i) => (
          <div
            key={s.step}
            className={`hero-flow-slide${i === active ? " is-active" : ""}`}
            aria-hidden={i !== active}
          >
            <div className="hero-flow-art">{STEP_ART[s.step]}</div>
            <div className="hero-flow-caption">
              <span className="how-badge font-display" aria-hidden="true">{s.step}</span>
              <span className="hero-flow-title font-display">{s.label}</span>
            </div>
            <p className="hero-flow-line">{s.line}</p>
          </div>
        ))}
      </div>
      <div className="hero-flow-nav">
        <div className="hero-flow-dots">
          {FLOW_STEPS.map((s, i) => (
            <button
              key={s.step}
              type="button"
              className={`hero-flow-dot${i === active ? " is-active" : ""}`}
              aria-label={`Show step ${s.step}: ${s.label}`}
              aria-current={i === active ? "true" : undefined}
              onClick={() => setActive(i)}
            />
          ))}
        </div>
        {!reduceMotion && (
          <button
            type="button"
            className="hero-flow-toggle"
            aria-label={toggleLabel}
            title={toggleLabel}
            data-testid="hero-flow-toggle"
            onClick={() => setPlaying((p) => !p)}
          >
            {playing ? (
              <Pause className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Play className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Problem / solution contrast. Left is the manual path, right is the product.
 *
 * The two lists are written to similar lengths on purpose. The cards sit side by
 * side in a two-column grid, and unbalanced bullets wrap to a ragged second line
 * on one side only — which makes the slow path look busier than it is and
 * quietly flatters the product.
 */
const WEEK_WITHOUT = [
  "Rewrite your app’s story from memory for every single script.",
  "Guess which opening your audience might sit through.",
  "Stare at a blank page and call it a content strategy.",
  "Dig through folders hunting last month’s clips, links, and numbers.",
];

const WEEK_WITH = [
  "Start every video from the App Profile you already approved.",          "Compare openings by fit scores, reasons, limitations.",
  "Edit a finished script draft instead of inventing one.",
  "Find every clip beside its posted link and real results in History.",
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
    title: "The opening, written to hold",
    body: "Create one AI-generated clip: an opening hook built to stop the scroll, followed by the story that earns the click. Your real app demo and closing message are not generated footage. Record the demo yourself, using the separate brief as a guide.",
  },
  {
    icon: Film,
    tone: "indigo",
    kicker: "Demo + CTA",
    title: "Your footage, centre stage",
    body: "Style a base clip — your own recording or a finished Hook + Story. Add a Second clip to play after it, or use Real Video to put a separate recording in a phone over the base. Choose each clip's look, framing and zoom, plus hook text and an end card you write. Export the result as one TikTok MP4.",
  },
  {
    icon: ShieldCheck,
    tone: "indigo",
    kicker: "Your review",
    title: "Nothing ships without your yes",
    body: "Approve your app profile and review the script before rendering. A craft grade scores the words and names the weakest line, so you know what to fix first. Review the finished clip, download it, and choose where and when to publish.",
  },
];

const QUESTIONS = [
  {
    question: "Can I use footage I already have?",
    answer: "Yes. Open Demo + CTA with your own video, including a screen recording. You don’t need to generate a Hook + Story first — the studio finishes what you bring.",
  },
  {
    question: "Can I change the script before generating?",
    answer: "That is the point. Edit the hook, script, tone, and creative directions, then save them and review the craft grade — all before you pay for a render, never after.",
  },
  {
    question: "Does the video use my real face and voice?",
    answer: "Your photo guides the AI presenter; it is not a recording of you or a clone of your voice. Check the likeness and delivery in the finished clip before using it.",
  },
  {
    question: "Will my clip have sound, and how can I export it?",
    answer: "Audio depends on the video model you choose; some models produce silent clips. Demo + CTA exports one 1080×1920 MP4 at 30 fps. Use a current Chrome or Edge browser; unsupported encoding is reported, not silently replaced with another format.",
  },
  {
    question: "Does HookForge post or track results for me?",
    answer: "No. Download your videos and publish them yourself. In History, add the posted TikTok link and paste back the results — views, 3-second retention, average watch, saves, and shares. Analytics lines those numbers up against each clip’s craft score, and from three posted clips the patterns start steering your next videos. Views are manually logged, not synced from TikTok, and do not prove conversions.",
  },
];


function SectionHeading({ eyebrow, title, lede, id }) {
  return (
    <div className="mx-auto mb-12 max-w-2xl scroll-mt-24 text-center" id={id}>
      {eyebrow && <EyebrowPill className="mb-3">{eyebrow}</EyebrowPill>}
      <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h2>
      {lede && <p className="mt-3.5 text-base leading-relaxed text-muted-foreground">{lede}</p>}
    </div>
  );
}

export default function Landing() {
  return (
    <div className="relative min-h-screen hero-wash">
      <div className="noise-overlay" />

      <MarketingHeader
        navLabel="Landing page"
        links={[{ to: "/features", label: "Features" }, ...NAV_LINKS]}
      />

      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden" data-testid="landing-hero">
        <Aurora />
        <div className="grid-overlay" />
        <div className="relative z-10 mx-auto max-w-6xl px-5 pb-24 pt-20 text-center sm:pt-28 lg:grid lg:grid-cols-[1.02fr_1fr] lg:items-center lg:gap-14 lg:text-left">
        <div className="min-w-0">
          <h1
            className="animate-fade-up font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl"
            style={{ animationDelay: "60ms" }}
          >
            <span className="text-shine">One photo in,</span>
            <br />
            <span className="text-gradient-brand">a posted TikTok out.</span>
          </h1>

          <p
            className="animate-fade-up mx-auto mt-7 max-w-2xl text-base leading-relaxed text-muted-foreground"
            style={{ animationDelay: "120ms" }}
          >
            HookForge turns your app’s facts into a hook that holds, a story that lands, and a
            finished clip — then your posted results steer the next one, so every video starts
            smarter than the last.
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
            className="animate-fade-up mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm text-muted-foreground lg:justify-start"
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
          {/* The flow itself, beside the pitch: the five step illustrations
              from the How it works strip, cycling in one frame — Kasra
              replaced the recorded tour footage with this loop, so the hero
              carries no video bytes at all. The frame keeps the portrait
              card the footage used (gradient hairline, soft indigo glow);
              inside, HeroFlow crossfades the steps at four seconds each,
              with dots and a pause control along the bottom. Under reduced
              motion the loop never starts and the dots step through by
              hand. */}
          <figure
            className="animate-fade-up mx-auto mt-12 w-full max-w-[360px] lg:mx-0 lg:mt-0 lg:max-w-[400px]"
            style={{ animationDelay: "280ms" }}
            data-testid="landing-hero-shot"
          >
            <div className="border-gradient relative rounded-2xl p-[1px]">
              <div className="hero-screen overflow-hidden rounded-2xl">
                <div className="relative aspect-[471/710] w-full">
                  <HeroFlow />
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
          title="From app facts to a video worth posting"
          lede="Five steps, one flow — your facts in, a finished Hook + Story out, and a demo that stays unmistakably yours."
        />

        {/* Visual strip: one branded illustration per step, a badge, one
            short line, and an outcome label, on the plain section
            background — no band behind the five. On phones the strip
            scrolls sideways with a faded edge; on wide screens it is a
            five-column grid. Layout lives in index.css (.how-*). */}
        <div>
          <ol className="how-steps">
            {FLOW_STEPS.map((s) => (
              <li
                key={s.step}
                className="how-step surface-interactive animate-fade-up"
                style={{ animationDelay: `${Number(s.step) * 60}ms` }}
              >
                <div className="how-art">
                  {STEP_ART[s.step]}
                </div>
                <div className="how-head">
                  <span className="how-badge font-display" aria-hidden="true">{s.step}</span>
                  <h3 className="font-display text-base font-semibold">{s.label}</h3>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.line}</p>
                <span className="how-outcome">{s.outcome}</span>
              </li>
            ))}
          </ol>
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
          title="Your week, with the blank page removed"
          lede="Founders don’t stop posting because they run out of ideas. They stop because every video starts at zero — HookForge makes sure it never does."
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
              <span className="eyebrow eyebrow-accent">With HookForge</span>
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
          title="Everything between idea and posted"
          lede="Not a video generator with a text box. A working studio that remembers your app, your choices, and what your audience actually watched."
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
          title="You direct. HookForge produces."
          lede="The AI writes and renders the opening. Your product, your footage, and your judgment stay exactly where they belong — with you."
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
                    <h3 className="font-display mt-1 text-base font-semibold">{block.title}</h3>
                    <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground sm:text-base">
                      {block.body}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}

          <div className="surface rounded-2xl" data-testid="landing-questions">
            <h3 className="font-display text-base font-semibold">A few things worth knowing</h3>
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

      <FinalCta testId="landing-final-cta" secondary />

      <MarketingFooter
        productLinks={[
          { to: "/features", label: "Features" },
          { to: "/create", label: "Create Video" },
          { to: "/history", label: "Generation History" },
          { to: "/brand", label: "App Profile" },
          { to: "/demo-cta", label: "Demo + CTA" },
        ]}
      />
    </div>
  );
}
