import {
  Check,
  ShieldCheck,
  BadgeCheck,
  CopyPlus,
  Play,
  Video,
} from "lucide-react";

/**
 * Code-built stand-ins for app UI on the Features page. Simplified panels
 * in the same tokens (.surface, .inset-panel, .eyebrow, hairlines) —
 * schematic, not clones. One owner for all six mockups; the page keeps
 * row data and layout, and picks a mockup per row id from MOCKUPS.
 */

function ProfileMockup() {
  return (
    <div className="surface" aria-hidden="true">
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow">App profile</span>
        <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] px-2 py-0.5 text-xs font-semibold text-[color:var(--brand-indigo)]">
          <BadgeCheck className="h-3 w-3" /> Approved
        </span>
      </div>
      <ul className="mt-4 space-y-2.5">
        {["What it does, in your words", "Who it is for", "Proof moment"].map((line) => (
          <li key={line} className="inset-panel flex items-center gap-2.5">
            <Check className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
            <span className="text-base text-muted-foreground">{line}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TemplatesMockup() {
  return (
    // The one row whose mockup skipped the .surface shell: without it this
    // column sat lighter and shallower than the other five. The two options
    // are .inset-panel asides, never nested cards, so the shared 20px gutter
    // and 12px radius come from the token, not a local p-3.5.
    <div className="surface" aria-hidden="true">
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          { name: "Cold open", fit: 92, picked: true },
          { name: "Myth vs fact", fit: 84, picked: false },
        ].map((t) => (
          <div
            key={t.name}
            className={`inset-panel ${
              t.picked
                ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                : ""
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-base font-semibold">{t.name}</span>
              <span className="font-mono text-xs font-semibold text-[color:var(--brand-indigo)]">{t.fit}</span>
            </div>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
              {t.picked ? "Fits a demo-first story." : "Strong hook, needs your proof."}
            </p>
            <p className="mt-1.5 text-sm text-muted-foreground">Caveat: needs a clear photo.</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScriptMockup() {
  // The words wear the app's real generated-text treatment (ADR 0258):
  // plain text on the one light indigo highlight, never a framed box —
  // the mockup follows the product, so the retired .spoken-line-frame
  // stays retired here too. The story shows its two beats, the shape
  // the strategy writes.
  const lines = [
    { label: "Hook", text: "the line your presenter says first." },
    { label: "Beat 1", text: "the moment your viewer recognises as their own." },
    { label: "Beat 2", text: "the turn that hands off to your demo." },
  ];
  return (
    <div className="surface" aria-hidden="true">
      <span className="eyebrow">Script plan</span>
      <div className="mt-4 space-y-2.5">
        {lines.map((line) => (
          <p key={line.label} className="flex items-baseline gap-2.5 text-base leading-relaxed">
            <span className="w-14 shrink-0 text-sm font-semibold text-muted-foreground">{line.label}</span>
            <span className="generated-highlight">{line.text}</span>
          </p>
        ))}
        <p className="inset-panel flex items-start gap-2 text-base leading-relaxed">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--brand-coral)]" />
          <span className="text-muted-foreground">Craft check: grade B — one line to tighten.</span>
        </p>
      </div>
    </div>
  );
}

function RenderMockup() {
  // The finished clip, not a placeholder: the presenter stands filled
  // in her scene, and the two platforms' safe zones ride over the frame
  // as dashed guides — annotations on the mockup, never a text banner
  // burned into the clip itself.
  return (
    <div className="surface" aria-hidden="true">
      <div className="relative mx-auto aspect-[9/16] w-44 overflow-hidden rounded-2xl border border-[color:var(--hairline)] bg-gradient-to-b from-[color:var(--indigo-15)] via-[color:var(--indigo-8)] to-black/70">
        <div className="absolute inset-x-6 top-[10%] h-[46%] rounded-t-full bg-white/5" />
        <div className="absolute inset-x-0 bottom-0 top-[18%]">
          <div className="mx-auto h-[36%] w-[36%] rounded-full bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] opacity-90" />
          <div className="mx-auto -mt-[3%] h-[64%] w-[76%] rounded-t-full bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] opacity-70" />
        </div>
        <div className="absolute left-1/2 top-1/2 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-black/45">
          <Play className="ml-0.5 h-4 w-4 text-white" />
        </div>
        <div
          data-testid="render-mock-safe-tiktok"
          className="pointer-events-none absolute bottom-[20%] left-[6%] right-[16%] top-[10%] rounded-md border border-dashed border-white/40"
        >
          <span className="absolute right-1 top-0.5 text-xs font-semibold text-muted-foreground">TikTok</span>
        </div>
        <div
          data-testid="render-mock-safe-instagram"
          className="pointer-events-none absolute bottom-[16%] left-[6%] right-[6%] top-[13%] rounded-md border border-dashed border-[color:var(--indigo-35)]"
        >
          <span className="absolute bottom-0.5 left-1 text-xs font-semibold text-[color:var(--brand-indigo)]">Instagram</span>
        </div>
      </div>
      <p className="mt-3 text-center text-sm text-muted-foreground">One clip: hook + story</p>
    </div>
  );
}

function OutcomesMockup() {
  return (
    <div className="surface" aria-hidden="true">
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow">History</span>
        <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--hairline)] px-2 py-0.5 text-xs font-semibold text-muted-foreground">
          <CopyPlus className="h-3 w-3" /> Draft variation
        </span>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <div className="flex h-20 w-11 shrink-0 items-center justify-center rounded-lg border border-[color:var(--hairline)] bg-black/60">
          <Video className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        </div>
        <div className="min-w-0 flex-1 space-y-2.5">
          <div className="flex gap-4 font-mono text-xs tabular-nums text-muted-foreground">
            <span>1.2k views</span>
            <span>Posted</span>
            <span>Your vote: Good</span>
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground">Logged by hand, not synced — your verdict decides the next draft.</p>
        </div>
      </div>
    </div>
  );
}

function DemoMockup() {
  // A browser frame on top — the web-app demo ADR 0256 made first-class —
  // and the export's sequence as a timeline under it: the generated
  // Hook + Story, the founder's own demo, then the end card.
  const steps = [
    { label: "Hook + Story", width: "w-[30%]", tone: "bg-[color:var(--brand-indigo)]" },
    { label: "Your demo", width: "w-[46%]", tone: "bg-white/25" },
    { label: "End card", width: "w-[24%]", tone: "bg-[color:var(--indigo-35)]" },
  ];
  return (
    <div className="surface" aria-hidden="true">
      <span className="eyebrow">Demo + CTA</span>
      <div className="mt-4 overflow-hidden rounded-xl border border-[color:var(--hairline)] bg-black/60">
        <div className="flex items-center gap-1.5 border-b border-[color:var(--hairline)] bg-white/5 px-3 py-2">
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
            <span key={c} className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />
          ))}
          <span className="ml-2 h-4 flex-1 rounded bg-white/10" />
        </div>
        <div className="space-y-2 px-3 py-3">
          <div className="h-2 w-2/3 rounded bg-[color:var(--indigo-35)]" />
          <div className="h-2 w-1/2 rounded bg-white/15" />
          <div className="h-2 w-3/5 rounded bg-white/10" />
        </div>
      </div>
      <div className="mt-4" data-testid="demo-mock-timeline">
        <div className="flex gap-1">
          {steps.map((step) => (
            <div key={step.label} className={`h-2 rounded-full ${step.width} ${step.tone}`} />
          ))}
        </div>
        <div className="mt-1.5 flex gap-1">
          {steps.map((step) => (
            <span key={step.label} className={`truncate text-xs text-muted-foreground ${step.width}`}>
              {step.label}
            </span>
          ))}
        </div>
      </div>
      <p className="mt-3 text-sm text-muted-foreground">Framing, zoom, hook text, end card.</p>
    </div>
  );
}

export const MOCKUPS = {
  profile: ProfileMockup,
  templates: TemplatesMockup,
  script: ScriptMockup,
  render: RenderMockup,
  demo: DemoMockup,
  outcomes: OutcomesMockup,
};
