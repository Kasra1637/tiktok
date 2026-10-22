import {
  Briefcase,
  LayoutTemplate,
  FileText,
  Clapperboard,
  Film,
  Video,
} from "lucide-react";
import { EyebrowPill, MarketingHeader, MarketingFooter, FinalCta } from "../components/Marketing";
import { MOCKUPS } from "./FeaturesMockups";

/**
 * Public Features showcase. Renders outside AppShell like Landing, so it
 * carries its own header and footer. Six curated highlights from Landing's
 * FEATURES list, each row alternating copy and a code-built mockup — no
 * real screenshots, no pixels to keep fresh. Copy reuses the landing
 * descriptions so the page never promises what the product cannot keep.
 */

const ROWS = [
  {
    id: "profile",
    icon: Briefcase,
    eyebrow: "App profile",
    title: "Start with your app's facts",
    body: "Research your website and store listings, or add the details yourself. Review and approve one profile to use across your videos.",
  },
  {
    id: "templates",
    icon: LayoutTemplate,
    eyebrow: "Templates",
    title: "Find an opening that fits",
    body: "Compare goal-matched templates by fit score, reasons, and caveats. Choose one, then add a clear presenter photo for the generated clip.",
  },
  {
    id: "script",
    icon: FileText,
    eyebrow: "Script",
    title: "Make the script your own",
    body: "Review the free script plan, edit and save the hook, story, and visual directions, then check flagged claims. Render Hook + Story in the final step.",
  },
  {
    id: "render",
    icon: Clapperboard,
    eyebrow: "Hook + Story",
    title: "Start with a photo, not a shoot",
    body: "The final step uses your approved plan and presenter photo to render one Hook + Story clip. It does not include your filmed demo, closing call to action, or on-screen text.",
  },
  {
    id: "demo",
    icon: Film,
    eyebrow: "Demo + CTA",
    title: "Give your footage a polished frame",
    body: "Bring a clip to Demo + CTA. Choose a phone mockup, adjust framing and zoom, and add your own hook text and end card.",
  },
  {
    id: "outcomes",
    icon: Video,
    eyebrow: "Outcomes",
    title: "Keep your next idea within reach",
    body: "Revisit clips in History, make a draft variation, and record results by hand. Review each new draft before generating another video.",
  },
];

export default function Features() {
  return (
    <div className="relative min-h-screen hero-wash">
      <div className="noise-overlay" />

      <MarketingHeader
        navLabel="Features page"
        links={[{ to: "/", label: "Home" }, ...ROWS.map((r) => ({ href: `#feature-${r.id}`, label: r.eyebrow }))]} 
      />

      {/* ---------- Intro ---------- */}
      <section className="relative z-10 mx-auto max-w-6xl px-5 pb-8 pt-20 text-center sm:pt-24" data-testid="features-intro">
        <EyebrowPill className="mb-3">Features</EyebrowPill>
        <h1 className="font-display mx-auto max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Everything between the idea and the clip.
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          Six highlights, each with what it does and what it looks like. Review
          the message before you turn it into video.
        </p>
      </section>

      {/* ---------- Alternating rows ---------- */}
      <main className="relative z-10 mx-auto max-w-6xl space-y-16 px-5 py-12" data-testid="features-page">
        {ROWS.map((row, i) => {
          const Mockup = MOCKUPS[row.id];
          const flip = i % 2 === 1;
          return (
            <section
              key={row.id}
              id={`feature-${row.id}`}
              data-testid={`features-row-${row.id}`}
              className="grid scroll-mt-24 items-center gap-8 lg:grid-cols-2 lg:gap-14"
            >
              <div className={flip ? "lg:order-2" : ""}>
                <span className="eyebrow text-[color:var(--brand-indigo)]">{row.eyebrow}</span>
                <h2 className="font-display mt-2 text-2xl font-bold tracking-tight sm:text-3xl">{row.title}</h2>
                <p className="mt-3 text-base leading-relaxed text-muted-foreground">{row.body}</p>
              </div>
              <div className={flip ? "lg:order-1" : ""}>
                <Mockup />
              </div>
            </section>
          );
        })}
      </main>

      <FinalCta testId="features-final-cta" />

      <MarketingFooter
        tagline={false}
        productLinks={[
          { to: "/", label: "Home" },
          { to: "/features", label: "Features" },
          { to: "/create", label: "Create Video" },
          { to: "/demo-cta", label: "Demo + CTA" },
        ]}
      />
    </div>
  );
}
