import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage } from "../lib/api";
import {
  LayoutTemplate, Loader2, AlertTriangle, Search, Star, Clock, Layers,
  ArrowRight, Archive, Plus, X,
} from "lucide-react";

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function TemplateCard({ template, onToggleFavorite }) {
  return (
    <Link
      to={`/templates/${template.id}`}
      className="surface group flex flex-col gap-3 rounded-2xl p-5 transition-colors hover:border-[color:var(--indigo-35)]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-display truncate text-base font-semibold">{template.name}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {humanize(template.category)}
            {template.version > 1 ? ` · v${template.version}` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleFavorite(template);
          }}
          aria-label={template.is_favorite ? "Remove from favorites" : "Add to favorites"}
          aria-pressed={template.is_favorite}
          className="shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-[color:var(--brand-indigo)]"
        >
          <Star
            className={`h-4 w-4 ${template.is_favorite ? "fill-[color:var(--brand-indigo)] text-[color:var(--brand-indigo)]" : ""}`}
          />
        </button>
      </div>

      <p className="line-clamp-3 text-sm leading-relaxed text-muted-foreground">
        {template.opening_structure}
      </p>

      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
        <Badge variant="secondary" className="text-[11px]">
          <Clock className="mr-1 h-2.5 w-2.5" />
          {template.default_duration}s
        </Badge>
        <Badge variant="secondary" className="text-[11px]">
          <Layers className="mr-1 h-2.5 w-2.5" />
          {template.hook_seconds}s hook
        </Badge>
        {template.origin !== "curated" && (
          <Badge variant="outline" className="text-[11px]">{humanize(template.origin)}</Badge>
        )}
        {template.archived && (
          <Badge variant="outline" className="text-[11px]">
            <Archive className="mr-1 h-2.5 w-2.5" /> Archived
          </Badge>
        )}
      </div>
    </Link>
  );
}

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function slotRowsFromSlots(slots) {
  const entries = Object.entries(slots || {});
  return entries.length ? entries.map(([key, value]) => ({ key, value: String(value ?? "") })) : [{ key: "", value: "" }];
}

export function templateFormInitial(template = null) {
  return {
    name: template?.name || "",
    category: template?.category || "",
    app_categories: (template?.app_categories || []).join(", "),
    audiences: (template?.audiences || []).join(", "),
    objective: template?.objective || "",
    opening_structure: template?.opening_structure || "",
    hook_seconds: template?.hook_seconds ?? 3,
    continuation_structure: template?.continuation_structure || "",
    cta_pattern: template?.cta_pattern || "",
    visual_style: template?.visual_style || "",
    camera_pacing: template?.camera_pacing || "",
    required_assets: template?.required_assets || [],
    default_duration: template?.default_duration ?? 20,
    slot_rows: slotRowsFromSlots(template?.content_slots),
    example_preview: template?.example_preview || "",
    evidence_note: template?.evidence_note || "",
    notes: template?.notes || "",
  };
}

export function TemplateForm({ facets, initial, submitLabel, busy, error, onCancel, onSubmit }) {
  const [form, setForm] = useState(() => templateFormInitial(initial));

  useEffect(() => {
    setForm(templateFormInitial(initial));
  }, [initial]);

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));
  const setSlot = (index, patch) => {
    setForm((prev) => ({
      ...prev,
      slot_rows: prev.slot_rows.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    }));
  };

  const submit = (event) => {
    event.preventDefault();
    const slots = {};
    form.slot_rows.forEach(({ key, value }) => {
      const slot = key.trim();
      if (slot) slots[slot] = value;
    });
    onSubmit({
      name: form.name.trim(),
      category: form.category || undefined,
      app_categories: splitList(form.app_categories),
      audiences: splitList(form.audiences),
      objective: form.objective || undefined,
      opening_structure: form.opening_structure,
      hook_seconds: Number(form.hook_seconds) || 3,
      continuation_structure: form.continuation_structure,
      cta_pattern: form.cta_pattern,
      visual_style: form.visual_style,
      camera_pacing: form.camera_pacing,
      // Face-only library: the character reference is the single permitted
      // requirement, so the form no longer offers a choice — the backend
      // enforces the same rule on the way in.
      required_assets: ["character_reference"],
      default_duration: Number(form.default_duration) || 20,
      content_slots: slots,
      example_preview: form.example_preview,
      evidence_note: form.evidence_note,
      notes: form.notes,
    });
  };

  const categories = [...new Set([...(facets?.hook_categories || []), ...(facets?.categories_in_use || [])])];
  const durations = facets?.supported_durations?.length ? facets.supported_durations : [10, 15, 20, 30];

  return (
    <form onSubmit={submit} className="space-y-4">
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="space-y-1 sm:col-span-2">
          <span className="text-sm font-medium">Template name</span>
          <Input value={form.name} onChange={(e) => set("name", e.target.value)} required />
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Category</span>
          <select
            value={form.category}
            onChange={(e) => set("category", e.target.value)}
            className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="">Choose a category</option>
            {categories.map((c) => (
              <option key={c} value={c}>{humanize(c)}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Objective</span>
          <select
            value={form.objective}
            onChange={(e) => set("objective", e.target.value)}
            className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="">Choose an objective</option>
            {(facets?.objectives || []).map((o) => (
              <option key={o} value={o}>{humanize(o)}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Suitable app categories, comma-separated</span>
          <Input
            value={form.app_categories}
            onChange={(e) => set("app_categories", e.target.value)}
            placeholder="productivity, finance"
          />
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Suitable audiences, comma-separated</span>
          <Input
            value={form.audiences}
            onChange={(e) => set("audiences", e.target.value)}
            placeholder="busy parents, new users"
          />
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Hook seconds</span>
          <Input
            type="number"
            min="1"
            value={form.hook_seconds}
            onChange={(e) => set("hook_seconds", e.target.value)}
          />
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Default duration</span>
          <select
            value={form.default_duration}
            onChange={(e) => set("default_duration", e.target.value)}
            className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            {durations.map((d) => (
              <option key={d} value={d}>{d} seconds</option>
            ))}
          </select>
        </label>
      </div>

      <label className="block space-y-1">
        <span className="text-sm font-medium">Opening structure</span>
        <Textarea
          value={form.opening_structure}
          onChange={(e) => set("opening_structure", e.target.value)}
          className="min-h-[90px]"
          required
        />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium">Continuation structure</span>
        <Textarea
          value={form.continuation_structure}
          onChange={(e) => set("continuation_structure", e.target.value)}
          className="min-h-[90px]"
        />
      </label>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="space-y-1">
          <span className="text-sm font-medium">CTA pattern</span>
          <Textarea
            value={form.cta_pattern}
            onChange={(e) => set("cta_pattern", e.target.value)}
            className="min-h-[70px]"
          />
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Visual style</span>
          <Textarea
            value={form.visual_style}
            onChange={(e) => set("visual_style", e.target.value)}
            className="min-h-[70px]"
          />
        </label>
      </div>
      <label className="block space-y-1">
        <span className="text-sm font-medium">Camera and pacing</span>
        <Textarea
          value={form.camera_pacing}
          onChange={(e) => set("camera_pacing", e.target.value)}
          className="min-h-[70px]"
        />
      </label>
      <label className="block space-y-1">
        <span className="text-sm font-medium">Example preview</span>
        <Textarea
          value={form.example_preview}
          onChange={(e) => set("example_preview", e.target.value)}
          className="min-h-[70px]"
          placeholder="A concrete example instantiation of this abstract structure."
        />
      </label>

      <div className="space-y-2">
        <span className="text-sm font-medium">Required assets</span>
        <p className="text-xs text-muted-foreground">
          Every template requires the character reference — the face the video
          is generated from. Nothing else can be required.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Content slots</span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => set("slot_rows", [...form.slot_rows, { key: "", value: "" }])}
          >
            <Plus className="h-3.5 w-3.5" /> Add slot
          </Button>
        </div>
        {form.slot_rows.map((row, index) => (
          <div key={index} className="flex gap-2">
            <Input
              value={row.key}
              onChange={(e) => setSlot(index, { key: e.target.value })}
              placeholder="app_feature"
              aria-label={`Content slot ${index + 1} name`}
            />
            <Input
              value={row.value}
              onChange={(e) => setSlot(index, { value: e.target.value })}
              placeholder="What the plan fills in"
              aria-label={`Content slot ${index + 1} description`}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={`Remove content slot ${index + 1}`}
              onClick={() => set("slot_rows", form.slot_rows.filter((_, i) => i !== index))}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="space-y-1">
          <span className="text-sm font-medium">Evidence note</span>
          <Textarea
            value={form.evidence_note}
            onChange={(e) => set("evidence_note", e.target.value)}
            className="min-h-[70px]"
          />
        </label>
        <label className="space-y-1">
          <span className="text-sm font-medium">Internal notes</span>
          <Textarea
            value={form.notes}
            onChange={(e) => set("notes", e.target.value)}
            className="min-h-[70px]"
          />
        </label>
      </div>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="brand" disabled={busy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} {submitLabel}
        </Button>
      </div>
    </form>
  );
}

export default function Templates() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [facets, setFacets] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [objective, setObjective] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getTemplates({
        q: query || undefined,
        category: category || undefined,
        objective: objective || undefined,
        favorites_only: favoritesOnly || undefined,
        include_archived: includeArchived || undefined,
      });
      setTemplates(data.templates || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [query, category, objective, favoritesOnly, includeArchived]);

  useEffect(() => {
    api.getTemplateFacets().then(setFacets).catch(() => setFacets(null));
  }, []);

  // Debounce so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(load, query ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, query]);

  const handleToggleFavorite = async (template) => {
    setTemplates((prev) =>
      prev.map((t) => (t.id === template.id ? { ...t, is_favorite: !t.is_favorite } : t))
    );
    try {
      await api.toggleTemplateFavorite(template.id);
    } catch (err) {
      setError(getErrorMessage(err));
      load();
    }
  };

  const handleCreate = async (payload) => {
    setCreateBusy(true);
    setCreateError(null);
    try {
      const created = await api.createTemplate(payload);
      setShowCreate(false);
      navigate(`/templates/${created.id}`);
    } catch (err) {
      setCreateError(getErrorMessage(err));
    } finally {
      setCreateBusy(false);
    }
  };

  const categoriesInUse = useMemo(() => {
    const fromFacets = facets?.categories_in_use || [];
    const fromData = [...new Set(templates.map((t) => t.category).filter(Boolean))];
    return [...new Set([...fromFacets, ...fromData])].sort();
  }, [facets, templates]);

  const hasFilters = Boolean(query || category || objective || favoritesOnly || includeArchived);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={LayoutTemplate}
        title="Hook Templates"
        description="Reusable creative structures — an opening mechanic, a continuation shape, and a CTA pattern. No source video required, and no template is tied to a specific creator."
        actions={
          <Button variant="brand" size="sm" onClick={() => { setCreateError(null); setShowCreate(true); }}>
            <Plus className="h-3.5 w-3.5" /> New template
          </Button>
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load templates</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="surface space-y-3 rounded-2xl p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search templates and opening structures"
            className="pl-10"
            aria-label="Search templates"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label="Filter by category"
            className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-1.5 text-xs font-medium"
          >
            <option value="">All categories</option>
            {categoriesInUse.map((c) => (
              <option key={c} value={c}>{humanize(c)}</option>
            ))}
          </select>

          <select
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            aria-label="Filter by objective"
            className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-1.5 text-xs font-medium"
          >
            <option value="">All objectives</option>
            {(facets?.objectives || []).map((o) => (
              <option key={o} value={o}>{humanize(o)}</option>
            ))}
          </select>

          <Button
            variant={favoritesOnly ? "brand" : "secondary"}
            size="sm"
            onClick={() => setFavoritesOnly((v) => !v)}
            aria-pressed={favoritesOnly}
          >
            <Star className={`h-3.5 w-3.5 ${favoritesOnly ? "fill-current" : ""}`} />
            Favorites
          </Button>

          <Button
            variant={includeArchived ? "brand" : "secondary"}
            size="sm"
            onClick={() => setIncludeArchived((v) => !v)}
            aria-pressed={includeArchived}
          >
            <Archive className="h-3.5 w-3.5" />
            Show archived
          </Button>

          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setQuery("");
                setCategory("");
                setObjective("");
                setFavoritesOnly(false);
                setIncludeArchived(false);
              }}
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading templates...
        </p>
      ) : templates.length === 0 ? (
        <EmptyState
          icon={LayoutTemplate}
          title={hasFilters ? "No templates match those filters" : "The library is empty"}
          description={
            hasFilters
              ? "Try clearing a filter or searching for a different structure."
              : "Curated templates will appear here."
          }
          action={
            hasFilters ? (
              <Button variant="secondary" onClick={() => {
                setQuery(""); setCategory(""); setObjective("");
                setFavoritesOnly(false); setIncludeArchived(false);
              }}>
                Clear filters
              </Button>
            ) : null
          }
        />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {templates.length} template{templates.length === 1 ? "" : "s"}
          </p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {templates.map((t) => (
              <TemplateCard key={t.id} template={t} onToggleFavorite={handleToggleFavorite} />
            ))}
          </div>
          <p className="flex items-center gap-2 pt-2 text-xs text-muted-foreground">
            <ArrowRight className="h-3 w-3" />
            Templates are curated from recurring high-performing hook mechanics. None are
            described as proven without measured performance data.
          </p>
        </>
      )}

      {showCreate && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Create template"
          onClick={() => setShowCreate(false)}
        >
          <div
            className="surface my-8 w-full max-w-3xl space-y-4 rounded-2xl p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-display text-base font-semibold">Create an internal template</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCreate(false)}
                aria-label="Close template creation"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
            <TemplateForm
              facets={facets}
              initial={null}
              submitLabel="Create template"
              busy={createBusy}
              error={createError}
              onCancel={() => setShowCreate(false)}
              onSubmit={handleCreate}
            />
          </div>
        </div>
      )}
    </div>
  );
}
