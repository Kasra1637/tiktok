import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import { TemplateForm } from "./Templates";
import { api, getErrorMessage } from "../lib/api";
import {
  LayoutTemplate, Loader2, AlertTriangle, ArrowLeft, Star, Copy, Archive,
  CheckCircle2, Info, Clock, Layers, Film, Camera, Package, Type, Target,
} from "lucide-react";

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function Section({ icon: Icon, label, children }) {
  if (!children) return null;
  return (
    <div className="space-y-1.5">
      <span className="eyebrow flex items-center gap-1.5">
        {Icon && <Icon className="h-3 w-3" />}
        {label}
      </span>
      <div className="text-sm leading-relaxed text-foreground/90">{children}</div>
    </div>
  );
}

export default function TemplateDetail() {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const [template, setTemplate] = useState(null);
  const [facets, setFacets] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [data, facetData] = await Promise.all([
        api.getTemplate(templateId),
        api.getTemplateFacets().catch(() => null),
      ]);
      setTemplate(data);
      setFacets(facetData);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const handleToggleFavorite = async () => {
    setBusy(true);
    try {
      const res = await api.toggleTemplateFavorite(templateId);
      setTemplate((t) => ({ ...t, is_favorite: res.is_favorite }));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleDuplicate = async () => {
    setBusy(true);
    try {
      const copy = await api.duplicateTemplate(templateId);
      navigate(`/templates/${copy.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleArchive = async () => {
    setBusy(true);
    try {
      const updated = await api.archiveTemplate(templateId, !template.archived);
      setTemplate(updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handlePublish = async () => {
    setBusy(true);
    try {
      setTemplate(await api.publishTemplate(templateId));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async (payload) => {
    setBusy(true);
    setSaveError(null);
    try {
      setTemplate(await api.updateTemplate(templateId, payload));
      setEditing(false);
    } catch (err) {
      setSaveError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading template...
      </p>
    );
  }

  if (error && !template) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Could not load this template</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const slots = template.content_slots || {};
  const slotEntries = Object.entries(slots);

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to="/templates">
          <ArrowLeft className="h-3.5 w-3.5" /> All templates
        </Link>
      </Button>

      <PageHeader
        icon={LayoutTemplate}
        title={template.name}
        description={`${humanize(template.category)} · ${template.default_duration}s default`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleToggleFavorite}
              disabled={busy}
              aria-pressed={template.is_favorite}
            >
              <Star className={`h-3.5 w-3.5 ${template.is_favorite ? "fill-current" : ""}`} />
              {template.is_favorite ? "Favorited" : "Favorite"}
            </Button>
            <Button variant="secondary" size="sm" onClick={handleDuplicate} disabled={busy}>
              <Copy className="h-3.5 w-3.5" /> Duplicate
            </Button>
            {template.review_status !== "approved" && (
              <Button variant="brand" size="sm" onClick={handlePublish} disabled={busy}>
                <CheckCircle2 className="h-3.5 w-3.5" /> Publish
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={handleArchive} disabled={busy}>
              <Archive className="h-3.5 w-3.5" />
              {template.archived ? "Restore" : "Archive"}
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

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">v{template.version}</Badge>
        <Badge variant="outline">{humanize(template.origin)}</Badge>
        <Badge variant="secondary">
          <Clock className="mr-1 h-2.5 w-2.5" /> {template.hook_seconds}s hook
        </Badge>
        <Badge variant="secondary">
          <Layers className="mr-1 h-2.5 w-2.5" /> {template.default_duration}s total
        </Badge>
        {template.objective && <Badge variant="outline">{humanize(template.objective)}</Badge>}
        {template.archived && <Badge variant="outline">Archived</Badge>}
        {template.review_status !== "approved" && (
          <Badge variant="outline">Unpublished draft</Badge>
        )}
      </div>

      {template.evidence_note && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{template.evidence_note}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="surface space-y-5 rounded-2xl p-5 lg:col-span-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-display text-base font-semibold">
              {editing ? "Customize every field" : "Structure"}
            </h3>
            {!editing && (
              <Button size="sm" variant="secondary" onClick={() => { setSaveError(null); setEditing(true); }}>
                Edit
              </Button>
            )}
          </div>

          {editing ? (
            <TemplateForm
              facets={facets}
              initial={template}
              submitLabel="Save template"
              busy={busy}
              error={saveError}
              onCancel={() => setEditing(false)}
              onSubmit={handleSave}
            />
          ) : (
            <div className="space-y-4">
              <Section icon={Film} label="Opening structure">
                {template.opening_structure}
              </Section>
              <Section icon={Layers} label="Continuation structure">
                {template.continuation_structure}
              </Section>
              <Section icon={Camera} label="Camera & pacing">
                {template.camera_pacing}
              </Section>
              <Section icon={Type} label="CTA pattern">
                {template.cta_pattern}
              </Section>
              <Section icon={Target} label="Example preview">
                {template.example_preview}
              </Section>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="surface space-y-4 rounded-2xl p-5">
            <h3 className="font-display text-base font-semibold">Production</h3>
            <Section icon={Film} label="Visual style">{template.visual_style}</Section>
            <Section icon={Package} label="Required assets">
              {(template.required_assets || []).length ? (
                <div className="flex flex-wrap gap-1.5">
                  {template.required_assets.map((a) => (
                    <Badge key={a} variant="secondary" className="text-[11px]">
                      {humanize(a)}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </Section>
            <Section icon={Clock} label="Default duration">
              {template.default_duration} seconds
            </Section>
            <Section icon={Target} label="Best for">
              {template.audiences?.length
                ? template.audiences.map(humanize).join(", ")
                : null}
            </Section>
          </div>

          {slotEntries.length > 0 && (
            <div className="surface space-y-3 rounded-2xl p-5">
              <h3 className="font-display text-base font-semibold">Content slots</h3>
              <p className="text-xs text-muted-foreground">
                These are the parts the creative plan fills in for a specific app.
              </p>
              <div className="space-y-2">
                {slotEntries.map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-[color:var(--hairline)] p-3">
                    <span className="eyebrow block">{humanize(key)}</span>
                    <p className="mt-1 text-sm text-foreground/90">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(template.usage_history || []).length > 0 && (
            <div className="surface space-y-3 rounded-2xl p-5">
              <h3 className="font-display text-base font-semibold">Usage history</h3>
              <div className="space-y-1.5">
                {template.usage_history.map((g) => (
                  <div key={g.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate text-muted-foreground">
                      {g.brand_name || "Unassigned"}
                    </span>
                    <Badge variant="outline" className="shrink-0 text-[11px]">
                      {g.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
