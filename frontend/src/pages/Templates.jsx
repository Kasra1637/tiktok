import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage } from "../lib/api";
import {
  LayoutTemplate, Loader2, AlertTriangle, Search, Star, Clock, Layers,
  ArrowRight, Archive,
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

export default function Templates() {
  const [templates, setTemplates] = useState([]);
  const [facets, setFacets] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [objective, setObjective] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);

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
    </div>
  );
}
