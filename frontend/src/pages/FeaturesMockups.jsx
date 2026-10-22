import {
  Check,
  ShieldCheck,
  BadgeCheck,
  Star,
  CopyPlus,
  Film,
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
      <ul className="mt-4 space-y-3">
        {["What it does, in your words", "Who it is for", "Proof moment"].map((line) => (
          <li key={line} className="inset-panel flex items-center gap-2.5">
            <Check className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
            <span className="text-sm text-muted-foreground">{line}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TemplatesMockup() {
  return (
    <div className="grid gap-3 sm:grid-cols-2" aria-hidden="true">
      {[
        { name: "Cold open", fit: 92, picked: true },
        { name: "Myth vs fact", fit: 84, picked: false },
      ].map((t) => (
        <div
          key={t.name}
          className={`rounded-xl border p-3.5 ${
            t.picked
              ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
              : "border-[color:var(--hairline)] bg-card/70"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold">{t.name}</span>
            <span className="font-mono text-xs font-semibold text-[color:var(--brand-indigo)]">{t.fit}</span>
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
            {t.picked ? "Fits a demo-first story." : "Strong hook, needs your proof."}
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">Caveat: needs a clear photo.</p>
        </div>
      ))}
    </div>
  );
}

function ScriptMockup() {
  return (
    <div className="surface" aria-hidden="true">
      <span className="eyebrow">Script plan</span>
      <div className="mt-4 space-y-2.5">
        <p className="inset-panel text-sm leading-relaxed">Hook: the line your viewer reads first.</p>
        <p className="inset-panel text-sm leading-relaxed text-muted-foreground">Story: three beats, your words.</p>
        <p className="inset-panel flex items-start gap-2 text-sm leading-relaxed">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--brand-coral)]" />
          <span className="text-muted-foreground">One claim flagged — reword before rendering.</span>
        </p>
      </div>
    </div>
  );
}

function RenderMockup() {
  return (
    <div className="surface" aria-hidden="true">
      <div className="mx-auto w-fit rounded-2xl border border-[color:var(--hairline)] bg-black/60 px-5 py-4">
        <p className="rounded-lg bg-white/95 px-3 py-1.5 text-center text-xs font-semibold uppercase tracking-wide text-black">
          Your hook, on screen
        </p>
        <div className="mx-auto mt-3 flex h-24 w-14 items-end justify-center rounded-lg border border-[color:var(--hairline)] bg-[color:var(--indigo-6)]">
          <Star className="mb-3 h-4 w-4 text-[color:var(--brand-indigo)]" />
        </div>
        <p className="mt-3 text-center text-xs text-muted-foreground">One clip: hook + story</p>
      </div>
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
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex gap-4 font-mono text-xs tabular-nums text-muted-foreground">
            <span>1.2k views</span>
            <span>84 likes</span>
            <span>12 saves</span>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">Logged by hand, not synced — your verdict decides the next draft.</p>
        </div>
      </div>
    </div>
  );
}

function DemoMockup() {
  return (
    <div className="surface" aria-hidden="true">
      <span className="eyebrow">Demo + CTA</span>
      <div className="mt-4 flex items-center gap-3">
        <div className="flex h-20 w-11 shrink-0 items-center justify-center rounded-lg border border-[color:var(--hairline)] bg-black/60">
          <Film className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        </div>
        <div className="min-w-0 flex-1 space-y-2.5">
          <div className="h-2 rounded-full bg-secondary/70">
            <div className="h-2 w-2/3 rounded-full bg-[color:var(--brand-indigo)]" />
          </div>
          <div className="flex items-center gap-1.5">
            {["#c8ff2e", "#ff4d8d", "#4dd8ff", "#ffffff"].map((c) => (
              <span
                key={c}
                className="h-5 w-5 rounded-full border border-[color:var(--hairline)]"
                style={{ background: c }}
              />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">Framing, zoom, hook text, end card.</p>
        </div>
      </div>
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
