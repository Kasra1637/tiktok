import { useEffect, useState } from "react";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import {
  Settings2, Loader2, AlertTriangle, Cpu, CheckCircle2, XCircle, ShieldCheck, Info,
} from "lucide-react";

function Row({ label, value, ok, note }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-[color:var(--hairline)] py-2 last:border-0">
      <span className="min-w-40 text-sm">{label}</span>
      {ok === undefined ? (
        <span className="text-sm text-muted-foreground">{value}</span>
      ) : ok ? (
        <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-indigo)]" />
      ) : (
        <XCircle className="h-4 w-4 text-muted-foreground" />
      )}
      <span className="ml-auto text-xs text-muted-foreground">{note}</span>
    </div>
  );
}

export default function Settings() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .getSettings()
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading settings...
      </p>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const p = data?.providers || {};
  const i = data?.integrations || {};
  const o = data?.overlays || {};
  const plan = p.thirty_second_request || {};

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Settings2}
        title="Settings"
        description="Configuration, provider capabilities, and what this tool deliberately does not do."
      />

      <div className="space-y-2">
        <h2 className="flex items-center gap-2 font-display text-base font-semibold">
          <Cpu className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          Video provider
        </h2>
        <div className="surface rounded-2xl p-4">
          <Row label="Default" value={p.default} />
          <Row label="Allowed" value={(p.allowlist || []).join(", ")} />
          <Row label="Longest single pass" value={`${p.max_single_pass_seconds}s`} />
          {plan.adjustments?.length > 0 && (
            <div className="mt-2 rounded-lg border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-3">
              <span className="eyebrow block">A 30-second request currently resolves to</span>
              <p className="mt-1 text-sm">
                {plan.primary_seconds}s in one pass
                {plan.needs_extension
                  ? `, plus a ${plan.extension_seconds}s extension`
                  : " with no extension needed"}
                .
              </p>
              {plan.adjustments.map((a, i) => (
                <p key={i} className="text-xs text-muted-foreground">{a}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="font-display text-base font-semibold">Integrations</h2>
        <div className="surface rounded-2xl p-4">
          <Row label="OpenRouter" ok={i.openrouter} note="text, vision, video" />
          <Row label="Apify" ok={i.apify} note="public trend research" />
          <Row label="Cloudflare R2" ok={i.cloudflare_r2} note="durable video storage" />
          <Row label="Turso" ok={i.turso} note="cloud database" />
          <Row label="Modal" ok={i.modal} note="frame extraction offload" />
          <Row label="ffmpeg" ok={o.ffmpeg_available} note="overlay compositing" />
          <Row label="Overlay font" value={o.font || "none found"} ok={!!o.font} />
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="flex items-center gap-2 font-display text-base font-semibold">
          <ShieldCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          What this tool does not do
        </h2>
        <div className="surface space-y-2 rounded-2xl p-4">
          <Badge variant="indigo" className="text-[11px]">Publishing: {data?.publishing}</Badge>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            {(data?.notes || []).map((n, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[color:var(--brand-indigo)]" />
                <span>{n}</span>
              </li>
            ))}
            <li className="flex gap-2">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[color:var(--brand-indigo)]" />
              <span>No automatic posting, scheduling, engagement, or account warming.</span>
            </li>
            <li className="flex gap-2">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[color:var(--brand-indigo)]" />
              <span>No platform credentials are requested, stored, or used.</span>
            </li>
          </ul>
        </div>
      </div>

      <Alert>
        <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        <AlertDescription>
          Changing the video model is an environment change
          (<code className="text-xs">VIDEO_MODEL_DEFAULT</code>,{" "}
          <code className="text-xs">VIDEO_MODEL_ALLOWLIST</code>), not a code change. Nothing
          here needs editing to swap providers.
        </AlertDescription>
      </Alert>
    </div>
  );
}
