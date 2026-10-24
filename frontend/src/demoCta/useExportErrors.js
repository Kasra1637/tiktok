import { useCallback, useState } from "react";

/**
 * Export error tracking, one owner.
 *
 * The editor already surfaces the current failure through its error banners;
 * this hook keeps the *history* of what failed, at which stage, so a founder
 * (or a bug report) can tell "save failed twice, encode never ran" from "the
 * encode failed". Recording is observability only: it never throws, never
 * blocks the export, and happy paths leave it untouched. The list is capped
 * so a long session cannot grow it without bound.
 */
export function useExportErrors() {
  const [exportErrors, setExportErrors] = useState([]);

  const recordExportError = useCallback((stage, err) => {
    const entry = {
      stage,
      message:
        (err && err.message) || String(err ?? "The export failed."),
      at: new Date().toISOString(),
    };
    // The log half of the surfacing: banners show the current failure, the
    // console keeps which stage failed and when for a bug report.
    console.warn("[HookForge] Export failed:", entry.stage, entry.message);
    setExportErrors((prev) => [...prev.slice(-9), entry]);
    return entry;
  }, []);

  const clearExportErrors = useCallback(() => setExportErrors([]), []);

  return { exportErrors, recordExportError, clearExportErrors };
}
