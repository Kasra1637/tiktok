import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import {
  Briefcase, Loader2, AlertTriangle, ArrowLeft, Sparkles, Target,
  ShieldAlert, Lightbulb, ChevronRight, Video,
} from "lucide-react";

/** Read an array-or-empty field into a clean list. */
function list(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "string" && value.trim()) {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch {
      return [];
    }
  }
  return [];
}

function ListBlock({ label, items, tone = "default" }) {
  if (!items.length) return null;
  const toneClass =
    tone === "banned"
      ? "border-[color:var(--hairline-strong)] bg-secondary/30"
      : tone === "review"
        ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
        : "border-[color:var(--hairline)] bg-secondary/20";
  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <span className="eyebrow block">{label}</span>
      <ul className="mt-2 space-y-1.5 text-sm text-foreground/90">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[color:var(--brand-indigo)]" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({ label, value }) {
  if (!value) return null;
  return (
    <div>
      <span className="eyebrow block">{label}</span>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{value}</p>
    </div>
  );
}

function ClaimPanel({ profile }) {
  const approved = list(profile.claims_approved);
  const review = list(profile.claims_review);
  const banned = list(profile.claims_banned);
  if (!approved.length && !review.length && !banned.length) return null;
  return (
    <div className="space-y-3">
      <h3 className="font-display text-base font-semibold">Claim guardrails</h3>
      <ListBlock label="Approved — safe to use" items={approved} />
      <ListBlock label="Needs review — verify first" items={review} tone="review" />
      <ListBlock label="Never use" items={banned} tone="banned" />
    </div>
  );
}

function AngleCard({ angle, onDelete, busy }) {
  return (
    <div className="surface rounded-2xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-display text-sm font-semibold">{angle.label || angle.kind}</h4>
          <Badge variant="secondary" className="mt-1 text-[11px]">
            {String(angle.kind || "").replace(/_/g, " ")}
          </Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete(angle.id)}
          disabled={busy}
          aria-label={`Delete ${angle.label || "angle"}`}
        >
          Delete
        </Button>
      </div>

      <dl className="mt-3 space-y-2 text-sm">
        {angle.target_audience && (
          <div>
            <dt className="eyebrow">Audience</dt>
            <dd className="text-foreground/90">{angle.target_audience}</dd>
          </div>
        )}
        {angle.user_problem && (
          <div>
            <dt className="eyebrow">Problem</dt>
            <dd className="text-foreground/90">{angle.user_problem}</dd>
          </div>
        )}
        {angle.hook_promise && (
          <div>
            <dt className="eyebrow">Hook promise</dt>
            <dd className="text-foreground/90">{angle.hook_promise}</dd>
          </div>
        )}
        {angle.app_feature && (
          <div>
            <dt className="eyebrow">Feature shown</dt>
            <dd className="text-foreground/90">{angle.app_feature}</dd>
          </div>
        )}
        {angle.desired_emotion && (
          <div>
            <dt className="eyebrow">Desired emotion</dt>
            <dd className="text-foreground/90">{angle.desired_emotion}</dd>
          </div>
        )}
        {angle.recommended_cta && (
          <div>
            <dt className="eyebrow">CTA</dt>
            <dd className="text-foreground/90">{angle.recommended_cta}</dd>
          </div>
        )}
      </dl>

      {list(angle.claims_to_respect).length > 0 && (
        <div className="mt-3 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-3">
          <span className="eyebrow block">Respect these claims</span>
          <ul className="mt-1.5 space-y-1 text-sm text-foreground/90">
            {list(angle.claims_to_respect).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function AppProfileDetail() {
  const { profileId } = useParams();
  const [profile, setProfile] = useState(null);
  const [angles, setAngles] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [recError, setRecError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [whatWorks, setWhatWorks] = useState(null);

  const load = useCallback(async () => {
    try {
      const [p, a, d, w] = await Promise.all([
        api.getAppProfile(profileId),
        api.getContentAngles(profileId).catch(() => ({ angles: [] })),
        // A profile is reusable for as many videos as you want, so the page
        // shows the drafts already built on it. Scoped by brand_profile_id, and
        // the backend filters on the caller's user_id too.
        api.getStudioProjects({ brand_profile_id: profileId }).catch(() => ({ projects: [] })),
        // Aggregate only, and manual entries only. A missing signal is the
        // expected case for a new profile, so it is not an error.
        api.getProfileWhatWorks(profileId).catch(() => null),
      ]);
      setProfile(p);
      setAngles(a.angles || []);
      setDrafts(d.projects || []);
      setWhatWorks(w);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const loadRecommendations = useCallback(
    async (angleId) => {
      // Drafts are not ranked at all now: the endpoint refuses them, and the
      // page already says recommendations appear after approval. Requesting
      // anyway would only produce a 409 that then has to be hidden again.
      if (profile?.status !== "approved") {
        setRecommendations([]);
        return;
      }
      try {
        const rec = await api.getTemplateRecommendations(profileId, {
          angle_id: angleId || undefined,
          limit: 6,
        });
        setRecommendations(rec.recommendations || []);
        setRecError(null);
      } catch (err) {
        // Same rule as the wizard: an empty list must not absorb a failure.
        // Drafts never reach this branch (they return above), so anything
        // caught here is a real error worth naming.
        setRecommendations([]);
        setRecError(getErrorMessage(err));
      }
    },
    [profileId, profile?.status]
  );

  useEffect(() => {
    if (profile) loadRecommendations();
  }, [profile, loadRecommendations]);

  const handleGenerateAngles = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await api.generateContentAngles(profileId);
      setAngles(data.angles || []);
      setNotice(`Generated ${data.angles?.length || 0} content angles.`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleDeleteAngle = async (angleId) => {
    setDeleting(true);
    try {
      await api.deleteContentAngle(profileId, angleId);
      setAngles((prev) => prev.filter((a) => a.id !== angleId));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading profile...
      </p>
    );
  }

  if (error && !profile) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Could not load this profile</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const approved = profile?.status === "approved";

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        {/* Was "All profiles" -> /app-profiles. There is no list page any
            more, and the editor is where an app is created, approved and
            switched between, so that is the honest way back. */}
        <Link to="/brand">
          <ArrowLeft className="h-3.5 w-3.5" /> Your app
        </Link>
      </Button>

      <PageHeader
        icon={Briefcase}
        title={profile?.brand_name || "Untitled app"}
        description={profile?.brand_description || undefined}
        actions={
          <div className="flex items-center gap-2">
            {approved ? (
              <Badge variant="indigo" className="px-3 py-1">Approved</Badge>
            ) : (
              <Badge variant="secondary" className="px-3 py-1">Draft — needs review</Badge>
            )}
            <Button variant="secondary" size="sm" asChild>
              <Link to="/brand">Edit</Link>
            </Button>
            {/* An App Profile is not consumed by making a video: the same
                approved profile backs every video, and the studio reuses its
                angles, assets and templates. This is the way back in, on the
                page where someone is looking at the app itself. */}
            <Button variant="brand" size="sm" asChild>
              <Link
                to={`/create?profile=${encodeURIComponent(profileId)}`}
                onClick={(e) => {
                  if (!approved) {
                    e.preventDefault();
                    setNotice("Approve this profile first — the studio only accepts approved apps.");
                  }
                }}
              >
                <Sparkles className="h-3.5 w-3.5" />
                New video
              </Link>
            </Button>
          </div>
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert>
          <Lightbulb className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {!approved && (
        <Alert>
          <ShieldAlert className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>Review and approve before generating</AlertTitle>
          <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <span className="text-muted-foreground">
              Content angles and template recommendations need an approved, verified profile.
            </span>
            <Button variant="secondary" size="sm" className="shrink-0" asChild>
              <Link to="/brand">Open profile editor</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="surface space-y-4 rounded-2xl p-5">
            <h3 className="font-display text-base font-semibold">Product facts</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Category" value={profile?.app_category || profile?.niche} />
              <Field label="Platforms" value={list(profile?.platforms).join(", ")} />
              <Field label="Tone / voice" value={profile?.tone_voice} />
            </div>
            <ListBlock label="Core features" items={list(profile?.core_features)} />
            <ListBlock label="Primary use cases" items={list(profile?.primary_use_cases)} />
            <ListBlock label="Problems solved" items={list(profile?.problems_solved)} />
            <ListBlock label="Desired outcomes" items={list(profile?.desired_outcomes)} />
            <ListBlock label="Competitor apps" items={list(profile?.competitors)} />
            <Field label="Differentiators" value={profile?.differentiation} />
            <Field label="Known limitations" value={profile?.known_limitations} />
            {/* Labelled as enforced because it is: this list is attached to
                every video prompt, so it is an instruction to the model rather
                than context it may use or ignore. The wording matters — the old
                label promised the same enforcement over a field that had none. */}
            <ListBlock
              label="Never show in the video (enforced)"
              items={list(profile?.must_not_show)}
            />
            <ListBlock label="When the app is reached for" items={list(profile?.usage_moments)} />
            <Field label="The proof moment" value={profile?.proof_moment} />
            {Array.isArray(profile?.viewer_objections) && profile.viewer_objections.length > 0 && (
              <div className="space-y-2">
                <span className="eyebrow block">Why they would not download</span>
                {profile.viewer_objections.map((o, i) => (
                  <div
                    key={`${o.objection}-${i}`}
                    className="rounded-xl border border-[color:var(--hairline)] p-3 text-sm"
                  >
                    <p className="font-medium">{o.objection}</p>
                    {o.what_they_do_now && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Does now: {o.what_they_do_now}
                      </p>
                    )}
                    {o.honest_answer && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Answer: {o.honest_answer}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* The only part of the profile that improves with use. Everything
              above was scraped once from the URL; this is the founder's own
              numbers on their own videos, and the next strategy prompt reads
              it. Aggregate per template, so it is evidence of what carried
              views rather than a ranking of hooks. */}
          <div className="surface space-y-3 rounded-2xl p-5">
            <span className="eyebrow flex items-center gap-1.5">
              <Target className="h-3 w-3" /> What has worked here
            </span>
            {!whatWorks || !whatWorks.has_signal ? (
              <p className="text-sm text-muted-foreground">
                Nothing recorded yet. Add view numbers to a finished video and the next strategy
                will know which of this app&apos;s openings actually carried them.
              </p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">
                  Across {whatWorks.videos} recorded video(s). View counts only — not proof that one
                  template is better.
                </p>
                <dl className="space-y-1.5 text-sm">
                  {(whatWorks.top || []).map((row) => (
                    <div key={row.template_id} className="flex items-baseline justify-between gap-3">
                      <dt className="min-w-0 truncate">{row.template_id}</dt>
                      <dd className="shrink-0 text-muted-foreground">
                        {row.views.toLocaleString()} views · save {Math.round(row.save_rate * 100)}%
                      </dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </div>

          <div className="surface space-y-4 rounded-2xl p-5">
            <h3 className="font-display text-base font-semibold">Audiences</h3>
            <Field label="Primary audience" value={profile?.target_audience} />
            <Field label="Ideal customer" value={profile?.ideal_customer_profile} />
            <ListBlock label="Segments" items={list(profile?.icp_segments)} />
          </div>

          <ClaimPanel profile={profile || {}} />
        </div>

        <div className="space-y-4">
          <div className="surface space-y-3 rounded-2xl p-5">
            <div className="flex items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 font-display text-base font-semibold">
                <Video className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                Videos from this app
              </h3>
              <span className="text-xs text-muted-foreground">
                {drafts.length ? `${drafts.length} draft${drafts.length === 1 ? "" : "s"}` : ""}
              </span>
            </div>

            {drafts.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {approved
                  ? "Nothing built on this app yet. The profile, its angles and its templates stay here and can be reused for every video you make."
                  : "Approve this profile to start building videos on it. It can be reused as often as you like."}
              </p>
            ) : (
              <div className="space-y-2">
                {drafts.map((d) => (
                  <Link
                    key={d.id}
                    to={`/create?profile=${encodeURIComponent(profileId)}&project=${encodeURIComponent(d.id)}`}
                    className="block rounded-xl border border-[color:var(--hairline)] p-3 transition-colors hover:border-[color:var(--indigo-35)]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">
                        {d.hook_line || d.objective || "Untitled draft"}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {d.script_version > 0
                        ? "Plan ready — resume in the studio"
                        : "Setup started — still needs a hook and assets"}
                    </p>
                  </Link>
                ))}
                <p className="pt-1 text-xs text-muted-foreground">
                  Each draft is independent, so you can start a fresh video on this app at any time.
                </p>
              </div>
            )}
          </div>

          <div className="surface space-y-3 rounded-2xl p-5">
            <div className="flex items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 font-display text-base font-semibold">
                <Target className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                Content angles
              </h3>
              <Button
                variant="brand"
                size="sm"
                onClick={handleGenerateAngles}
                disabled={generating || !approved}
                title={approved ? undefined : "Approve the profile first"}
              >
                {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                {angles.length ? "Regenerate" : "Generate"}
              </Button>
            </div>

            {angles.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {approved
                  ? "Generate angles to see which problems, benefits, and features to lead with."
                  : "Approve this profile to generate content angles."}
              </p>
            ) : (
              <div className="space-y-3">
                {angles.map((a) => (
                  <AngleCard
                    key={a.id}
                    angle={a}
                    onDelete={handleDeleteAngle}
                    busy={deleting}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="surface space-y-3 rounded-2xl p-5">
            <h3 className="font-display text-base font-semibold">Suggested templates</h3>
            {recError && (
              <p className="text-xs text-muted-foreground">
                Could not load suggestions ({recError}).
              </p>
            )}
            {recommendations.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Recommendations appear once the profile is approved.
              </p>
            ) : (
              <div className="space-y-2">
                {recommendations.map((r) => (
                  <Link
                    key={r.template.id}
                    to={`/create?profile=${profileId}&template=${r.template.id}`}
                    className="block rounded-xl border border-[color:var(--hairline)] p-3 transition-colors hover:border-[color:var(--indigo-35)]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{r.template.name}</span>
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                    </div>
                    {r.why_it_fits?.[0] && (
                      <p className="mt-1 text-xs text-muted-foreground">{r.why_it_fits[0]}</p>
                    )}
                  </Link>
                ))}
                <Link
                  to={`/create?profile=${profileId}`}
                  className="block pt-1 text-center text-xs font-medium text-[color:var(--brand-indigo)] hover:underline"
                >
                  Pick one in the studio
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
