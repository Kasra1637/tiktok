/**
 * Real-user timing with no dependency and no backend sink: LCP, INP and CLS
 * via PerformanceObserver, logged in development and exposed on
 * `window.__hookforgeVitals` for manual profiling.
 *
 * The numbers exist to guide the next perf pass, not to surveil founders —
 * nothing leaves the tab. INP here is the standard approximation (worst
 * `event` timing with an interaction id); good enough to rank pages, not
 * analytics-grade. Guards everything: old browsers, prerender and the jsdom
 * test harness simply never start an observer.
 *
 * Thresholds follow the web-vitals defaults: LCP good < 2500ms / poor >=
 * 4000ms, INP good < 200ms / poor >= 500ms, CLS good <= 0.10 / poor > 0.25.
 */

const THRESHOLDS = {
  LCP: [2500, 4000],
  INP: [200, 500],
  CLS: [0.1, 0.25],
};

export function rateMetric(name, value) {
  const [good, poor] = THRESHOLDS[name] || [];
  if (good === undefined || typeof value !== "number" || Number.isNaN(value)) return "unknown";
  if (value <= good) return "good";
  if (value < poor) return "needs-improvement";
  return "poor";
}

let started = false;

function supported() {
  return (
    typeof window !== "undefined" &&
    typeof PerformanceObserver !== "undefined" &&
    typeof document !== "undefined" &&
    !document.prerendering
  );
}

function emit(store, report) {
  const snapshot = { ...store };
  try {
    window.__hookforgeVitals = snapshot;
  } catch {
    // Ignore: storage-less contexts still get the console report below.
  }
  if (process.env.NODE_ENV !== "production" && typeof console !== "undefined") {
    const line = Object.entries(snapshot)
      .map(([name, v]) => `${name}=${Math.round(v * 100) / 100} (${rateMetric(name, v)})`)
      .join(" ");
    console.info(`[vitals] ${line}`);
  }
  if (typeof report === "function") {
    try {
      report(snapshot);
    } catch {
      // A reporting callback must never break the app it measures.
    }
  }
}

export function initVitals(report) {
  if (started || !supported()) return () => {};
  started = true;
  const store = {};
  const seen = new Set();
  const observers = [];

  const observe = (type, buffered, onEntry) => {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) onEntry(entry);
        emit(store, report);
      });
      observer.observe({ type, buffered });
      observers.push(observer);
    } catch {
      // Ignore: an entry type this browser does not know is not a failure.
    }
  };

  // LCP: the last largest-contentful-paint wins — earlier candidates are
  // replaced as larger content arrives.
  observe("largest-contentful-paint", true, (entry) => {
    if (entry.startTime) store.LCP = entry.startTime;
  });

  // CLS: session-windowed sum, ignoring shifts right after input (those are
  // the founder's own doing, not jank).
  observe("layout-shift", true, (entry) => {
    if (!entry.hadRecentInput && typeof entry.value === "number") {
      store.CLS = (store.CLS || 0) + entry.value;
    }
  });

  // INP approximation: the worst interaction-anchored event timing so far.
  observe("event", true, (entry) => {
    if (!entry.interactionId || seen.has(entry.interactionId)) return;
    seen.add(entry.interactionId);
    if (typeof entry.duration === "number") {
      store.INP = Math.max(store.INP || 0, entry.duration);
    }
  });

  return () => {
    observers.forEach((observer) => {
      try {
        observer.disconnect();
      } catch {
        // Ignore: teardown must not throw either.
      }
    });
  };
}
