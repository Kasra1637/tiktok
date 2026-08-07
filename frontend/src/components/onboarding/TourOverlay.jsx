import { useEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Button } from "../ui/button";
import { useOnboarding } from "./OnboardingProvider";
import { X, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";

const VIEWPORT_MARGIN = 12;
const TOOLTIP_WIDTH = 320;
const SPOTLIGHT_PADDING = 8;
const FIND_INTERVAL_MS = 120;
const FIND_TIMEOUT_REQUIRED_MS = 3500;
const FIND_TIMEOUT_OPTIONAL_MS = 1200;

/**
 * Locate the DOM element for a step's `target` selector. `target` may be a
 * comma-separated list of alternative selectors (only one of which is
 * typically present at a time, e.g. two mutually-exclusive conditional
 * buttons) — the browser's own comma-selector semantics handle that.
 * Returns null if not found or has no visible box yet.
 */
function findTargetElement(selector) {
  if (!selector) return null;
  let el;
  try {
    el = document.querySelector(selector);
  } catch {
    return null;
  }
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return null;
  return el;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/**
 * Compute a fixed-position tooltip box near `rect`, preferring below,
 * flipping above if there isn't room, and clamping horizontally so it never
 * runs off-screen.
 */
function computeTooltipPosition(rect, preferredPlacement) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const estimatedHeight = 190; // rough card height before layout; good enough for placement math

  const spaceBelow = vh - rect.bottom;
  const spaceAbove = rect.top;
  let placement = preferredPlacement || "bottom";
  if (placement === "bottom" && spaceBelow < estimatedHeight + VIEWPORT_MARGIN && spaceAbove > spaceBelow) {
    placement = "top";
  } else if (placement === "top" && spaceAbove < estimatedHeight + VIEWPORT_MARGIN && spaceBelow > spaceAbove) {
    placement = "bottom";
  }

  const centerX = rect.left + rect.width / 2;
  const left = clamp(centerX - TOOLTIP_WIDTH / 2, VIEWPORT_MARGIN, vw - TOOLTIP_WIDTH - VIEWPORT_MARGIN);

  let top;
  if (placement === "bottom") {
    top = clamp(rect.bottom + SPOTLIGHT_PADDING + 6, VIEWPORT_MARGIN, vh - estimatedHeight - VIEWPORT_MARGIN);
  } else {
    top = clamp(rect.top - estimatedHeight - SPOTLIGHT_PADDING - 6, VIEWPORT_MARGIN, vh - estimatedHeight - VIEWPORT_MARGIN);
  }

  return { top, left, placement };
}

export default function TourOverlay() {
  const { activeTour, currentStep, stepIndex, totalSteps, next, back, skip } = useOnboarding();
  const reduceMotion = useReducedMotion();

  const [rect, setRect] = useState(null);
  const [tooltipPos, setTooltipPos] = useState(null);
  const [searching, setSearching] = useState(true);

  const pollRef = useRef(null);
  const timeoutRef = useRef(null);
  const rafRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => () => {
    mountedRef.current = false;
  }, []);

  const clearTimers = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    pollRef.current = null;
    timeoutRef.current = null;
  }, []);

  const measure = useCallback(() => {
    if (!currentStep) return;
    if (!currentStep.target) {
      setRect(null);
      setTooltipPos(null);
      return;
    }
    const el = findTargetElement(currentStep.target);
    if (!el) return;
    const r = el.getBoundingClientRect();
    const padded = {
      top: r.top - SPOTLIGHT_PADDING,
      left: r.left - SPOTLIGHT_PADDING,
      width: r.width + SPOTLIGHT_PADDING * 2,
      height: r.height + SPOTLIGHT_PADDING * 2,
      bottom: r.bottom + SPOTLIGHT_PADDING,
      right: r.right + SPOTLIGHT_PADDING,
    };
    setRect(padded);
    setTooltipPos(computeTooltipPosition(padded, currentStep.placement));
  }, [currentStep]);

  // (Re)start the search for this step's target whenever the step changes.
  useEffect(() => {
    clearTimers();
    setSearching(true);
    setRect(null);
    setTooltipPos(null);

    if (!currentStep) return;

    // Centered/welcome steps have no target to find.
    if (!currentStep.target) {
      setSearching(false);
      return;
    }

    const timeoutMs = currentStep.optional ? FIND_TIMEOUT_OPTIONAL_MS : FIND_TIMEOUT_REQUIRED_MS;
    let resolved = false;

    const tryFind = () => {
      const el = findTargetElement(currentStep.target);
      if (el) {
        resolved = true;
        clearTimers();
        el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center", inline: "nearest" });
        // Let the smooth scroll settle a beat before measuring final position.
        setTimeout(() => {
          if (!mountedRef.current) return;
          measure();
          setSearching(false);
        }, reduceMotion ? 0 : 260);
      }
    };

    tryFind();
    if (!resolved) {
      pollRef.current = setInterval(tryFind, FIND_INTERVAL_MS);
      timeoutRef.current = setTimeout(() => {
        if (resolved || !mountedRef.current) return;
        clearTimers();
        // Target never appeared (state-dependent UI not on screen right now).
        // Skip forward rather than stranding the user on a dead step.
        setSearching(false);
        next();
      }, timeoutMs);
    }

    return clearTimers;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, stepIndex]);

  // Track the target's position across resize/scroll while a step is showing.
  useEffect(() => {
    if (!currentStep?.target || searching) return;
    const onChange = () => {
      if (rafRef.current) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        measure();
      });
    };
    window.addEventListener("resize", onChange);
    window.addEventListener("scroll", onChange, true);
    return () => {
      window.removeEventListener("resize", onChange);
      window.removeEventListener("scroll", onChange, true);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [currentStep, searching, measure]);

  // Keyboard shortcuts: Escape to skip, arrow keys to navigate.
  useEffect(() => {
    if (!activeTour) return;
    const onKey = (e) => {
      if (e.key === "Escape") skip();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeTour, next, back, skip]);

  if (!activeTour || !currentStep || searching) return null;

  const isLast = stepIndex === totalSteps - 1;
  const isFirst = stepIndex === 0;
  const isCentered = !currentStep.target || !rect;

  const tooltipStyle = isCentered
    ? {
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
      }
    : {
        top: tooltipPos?.top ?? 80,
        left: tooltipPos?.left ?? 80,
      };

  return createPortal(
    <AnimatePresence>
      <motion.div
        key={`tour-backdrop-${activeTour.id}`}
        className="fixed inset-0 z-[100]"
        initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18 }}
        data-testid="onboarding-tour-overlay"
      >
        {/* Dimming layer — click outside the card to skip the tour */}
        <div
          className="absolute inset-0 bg-black/55"
          onClick={skip}
          data-testid="onboarding-tour-backdrop"
        />

        {/* Spotlight ring around the current target, cut out of the dim layer via box-shadow */}
        {rect && (
          <motion.div
            key={`spotlight-${stepIndex}`}
            className="absolute rounded-xl pointer-events-none border-2 border-[color:var(--brand-teal)]"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            style={{
              top: rect.top,
              left: rect.left,
              width: rect.width,
              height: rect.height,
              boxShadow: "0 0 0 9999px rgba(0,0,0,0.55), 0 0 0 3px rgba(13,148,136,0.25)",
            }}
          />
        )}

        {/* Tooltip / welcome card */}
        <motion.div
          key={`tour-card-${stepIndex}`}
          className="fixed z-[101] rounded-2xl border border-border bg-card shadow-2xl p-4"
          style={{ width: isCentered ? 360 : TOOLTIP_WIDTH, ...tooltipStyle }}
          initial={reduceMotion ? { opacity: 1 } : { opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          onClick={(e) => e.stopPropagation()}
          data-testid="onboarding-tour-tooltip"
        >
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[color:rgba(13,148,136,0.12)] text-[color:var(--brand-teal)] shrink-0">
                <Sparkles className="h-2.5 w-2.5" />
              </span>
              <h3 className="font-display text-sm font-semibold leading-snug truncate">{currentStep.title}</h3>
            </div>
            <button
              onClick={skip}
              aria-label="Close tour"
              className="text-muted-foreground hover:text-foreground shrink-0 -mt-0.5 -mr-0.5"
              data-testid="onboarding-tour-close-button"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">{currentStep.body}</p>

          <div className="flex items-center justify-between mt-3.5">
            <div className="flex items-center gap-1" data-testid="onboarding-tour-progress">
              {activeTour.steps.map((_, i) => (
                <span
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    i === stepIndex ? "w-4 bg-[color:var(--brand-teal)]" : "w-1.5 bg-border"
                  }`}
                />
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              {!isFirst && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={back}
                  className="h-7 px-2 gap-1 text-xs"
                  data-testid="onboarding-tour-back-button"
                >
                  <ChevronLeft className="h-3 w-3" /> Back
                </Button>
              )}
              <Button
                size="sm"
                onClick={next}
                className="h-7 px-2.5 gap-1 text-xs bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
                data-testid="onboarding-tour-next-button"
              >
                {isLast ? "Done" : "Next"} {!isLast && <ChevronRight className="h-3 w-3" />}
              </Button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
