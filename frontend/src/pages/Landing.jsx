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
  FileText, X, Check, Briefcase, LayoutTemplate, ShieldCheck, Video,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { LazyHeroVideo } from "../components/LazyHeroVideo";
import { EyebrowPill, MarketingHeader, MarketingFooter, FinalCta } from "../components/Marketing";

const FEATURES = [
  {
    icon: Briefcase,
    title: "Start with your app’s facts",
    description:
      "Research an App Store or Google Play listing, then correct and approve the draft. Reuse that profile across your videos.",
  },
  {
    icon: Target,
    title: "Make your message specific",
    description:
      "Pick a required audience angle and video goal. Tone is optional. These guide template suggestions and the free script plan.",
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
      "Revisit clips in History, record posted links, views, and votes, then compare them in Analytics. Reuse a saved draft for another take; views do not prove conversions.",
  },
];

const FLOW_STEPS = [
  {
    step: "1",
    label: "Introduce your app",
    detail: "Add an App Store or Google Play URL, with optional support links. Research the draft, correct it, then save, review, and approve the facts.",
  },
  {
    step: "2",
    label: "Choose a goal and audience",
    detail: "Pick an audience angle and set a goal for the video; both are required. Tone is optional. These choices share the Audience & template step.",
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
    detail: "Record your demo separately. In Demo + CTA, style a base clip, optionally add a Second clip after it or a phone overlay in Real Video, then export and publish them yourself.",
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
    body: "Style a base clip—your own recording or a finished Hook + Story. Add a Second clip to play after it, or use Real Video to put a separate recording in a phone over the base. Choose each clip's look, framing and zoom, plus hook text and an end card you write. Export the result as one TikTok MP4.",
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
    answer: "Audio depends on the video model you choose; some models produce silent clips. Demo + CTA exports one 1080×1920 MP4 at 30 fps. Use a current Chrome or Edge browser; unsupported encoding is reported, not silently replaced with another format.",
  },
  {
    question: "Does HookForge post or track results for me?",
    answer: "No. Download your videos and publish them yourself. In History, add the posted TikTok link, paste back views, and rate the clip. Compare those saved results in Analytics. Views are manually logged, not synced from TikTok, and do not prove conversions.",
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
            <span className="text-shine">Give your app a story</span>
            <br />
            <span className="text-gradient-brand">Worth watching.</span>
          </h1>

          <p
            className="animate-fade-up mx-auto mt-7 max-w-2xl text-base leading-relaxed text-muted-foreground"
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
          {/* The app itself, beside the pitch: the real three-step Create
              Video journey (App Profile → Audience & template, with the
              Review & submit gate naming what's missing) plus the editable
              Demo + CTA canvas and an expanded History tile, recorded from
              the running app. A minimal floating card frames it: gradient
              hairline and a portrait viewport at the capture's exact aspect
              (471:710) with the footage contained, so the whole interface
              shows with no cropping and no letterbox gap. The card grows on
              wide screens and sits on a soft indigo glow so it holds its
              own next to the headline. Autoplay is silent and loops; the
              footage loads lazily as the frame nears the viewport, and under
              reduced motion it stays a poster frame that never loads. */}
          <figure
            className="animate-fade-up mx-auto mt-12 w-full max-w-[360px] lg:mx-0 lg:mt-0 lg:max-w-[400px]"
            style={{ animationDelay: "280ms" }}
            data-testid="landing-hero-shot"
          >
            <div className="border-gradient relative rounded-2xl p-[1px] shadow-[0_24px_80px_-24px_rgb(0_0_0/0.8)]">
              <div className="overflow-hidden rounded-2xl bg-black">
                <div className="relative aspect-[471/710] w-full">
                  <LazyHeroVideo
                    className="absolute inset-0 block h-full w-full object-contain"
                    poster={`${process.env.PUBLIC_URL}/hero-demo-poster.jpg`}
                    sources={[
                      { src: `${process.env.PUBLIC_URL}/hero-demo.webm`, type: "video/webm" },
                      { src: `${process.env.PUBLIC_URL}/hero-demo.mp4`, type: "video/mp4" },
                    ]}
                    ariaLabel="Screen recording: the three-step Create Video wizard, the Demo plus CTA canvas, and an expanded History tile — full interface with no page header or footer"
                  />
                </div>
              </div>
            </div>
            <div aria-hidden="true" className="mx-auto -mt-3 h-12 w-3/4 rounded-[100%] bg-[color:var(--brand-indigo)] opacity-25 blur-2xl" />
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
                <div className="relative mx-auto mb-5 flex h-[52px] w-[52px] items-center justify-center rounded-2xl bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] font-semibold text-white shadow-[var(--glow-indigo)]">
                  <span className="font-display text-base">{s.step}</span>
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
