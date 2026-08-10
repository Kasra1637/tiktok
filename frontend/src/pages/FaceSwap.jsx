import { useState, useRef, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import GenerationProgress from "../components/GenerationProgress";
import HookStyleSelector from "../components/HookStyleSelector";
import PageHeader from "../components/PageHeader";
import { StepDots, StepBadge } from "../components/Stepper";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import {
  Upload,
  Sparkles,
  AlertTriangle,
  RotateCcw,
  X,
  Download,
  User,
  Check,
  Film,
  Clapperboard,
  Loader2,
  Compass,
  Bookmark,
  Save,
  Trash2,
  Volume2,
  VolumeX,
  Repeat2,
} from "lucide-react";
import { toast } from "sonner";

const ACTIVE_FACE_SWAP_JOB_KEY = "hookforge_active_face_swap_job";

/* ---------- Upload Drop Zone ---------- */
function DropZone({ onFileSelect, accept, label, sublabel, preview, onRemove, testId, icon: Icon = Upload }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e) => { e.preventDefault(); setIsDragging(true); }, []);
  const handleDragLeave = useCallback((e) => { e.preventDefault(); setIsDragging(false); }, []);
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file?.type.startsWith("image/")) onFileSelect(file);
    else toast.error("Please drop an image file (JPEG, PNG, or WEBP).");
  }, [onFileSelect]);

  if (preview) {
    return (
      <div className="group relative overflow-hidden rounded-2xl border border-[color:var(--hairline)]" data-testid={`${testId}-preview`}>
        <img src={preview} alt="Preview" className="aspect-[3/4] w-full object-cover" />
        <button
          onClick={onRemove}
          className="absolute right-2.5 top-2.5 rounded-full bg-black/60 p-1.5 text-white opacity-0 backdrop-blur-sm transition-opacity hover:bg-black/85 group-hover:opacity-100"
          aria-label="Remove"
          data-testid={`${testId}-remove`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div>
      <input ref={inputRef} type="file" accept={accept} className="hidden" onChange={(e) => {
        const file = e.target.files?.[0];
        if (file?.type.startsWith("image/")) onFileSelect(file);
        else if (file) toast.error("Please upload an image file.");
      }} data-testid={`${testId}-input`} />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`flex w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed py-14 transition-[background-color,border-color,transform] duration-200 ${
          isDragging
            ? "scale-[1.01] border-[color:var(--brand-indigo)] bg-[color:var(--indigo-8)]"
            : "border-[color:var(--hairline-strong)] bg-card/40 hover:border-[color:var(--indigo-45)] hover:bg-[color:var(--indigo-4)]"
        }`}
        data-testid={`${testId}-dropzone`}
      >
        <span
          className={`flex h-12 w-12 items-center justify-center rounded-2xl border transition-colors ${
            isDragging
              ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-15)]"
              : "border-[color:var(--hairline)] bg-secondary/50"
          }`}
        >
          <Icon className={`h-5 w-5 ${isDragging ? "text-[color:var(--brand-indigo)]" : "text-muted-foreground"}`} />
        </span>
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-xs text-muted-foreground">{sublabel}</span>
      </button>
    </div>
  );
}

/** Section heading inside the Create Video card. */
function StepLabel({ step, tone = "indigo", title, done }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-white ${
          tone === "coral" ? "bg-[color:var(--brand-coral)]" : "bg-[color:var(--brand-indigo)]"
        }`}
      >
        {step}
      </span>
      <span className="text-xs font-semibold">{title}</span>
      {done && <Check className="h-3.5 w-3.5 text-emerald-400" />}
    </div>
  );
}

/* ---------- Main Component ---------- */
export default function FaceSwap() {
  const [searchParams] = useSearchParams();

  // Upload state
  const [targetFile, setTargetFile] = useState(null);
  const [targetPreview, setTargetPreview] = useState(null);
  const [targetFrameUrl, setTargetFrameUrl] = useState(null);
  const [sourceFile, setSourceFile] = useState(null);
  const [sourcePreview, setSourcePreview] = useState(null);
  const [videoInfo, setVideoInfo] = useState(null);
  const [templateInfo, setTemplateInfo] = useState(null);
  const [savedFaceLoaded, setSavedFaceLoaded] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedVariant, setSelectedVariant] = useState(0);

  // Video state
  const [generatingVideo, setGeneratingVideo] = useState(false);
  const [videoStatus, setVideoStatus] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoError, setVideoError] = useState(null);
  const [videoPhase, setVideoPhase] = useState("hook"); // "hook" | "extend"
  // Which phase the last error came from, so the retry affordance repeats the
  // action that actually failed rather than always regenerating the hook.
  const [failedPhase, setFailedPhase] = useState(null);
  const [motionStyle, setMotionStyle] = useState("");
  // Backend-reported availability of Aleph's exact-edit path for the attached
  // video. null = not yet known (or no video attached). Previously this was
  // inferred from "is a video attached?", which couldn't see whether the
  // analysis and source clip were actually obtainable server-side — so the
  // badge could promise an exact edit the backend would then downgrade.
  const [exactEditAvailable, setExactEditAvailable] = useState(null);
  // The engine the backend ACTUALLY used, read from the generation response.
  // Availability is only a structural pre-check — auto-analysis can still fail
  // at request time and silently route to the generative engine. Reporting the
  // real value after the fact is the only way the UI can never overclaim.
  const [actualEngine, setActualEngine] = useState(null);
  // Motion styles come from the backend so each card shows the exact prompt
  // text that will be sent. Falls back to labels only (no description) if the
  // fetch fails — showing a hardcoded description here is what allowed the UI
  // and the prompt to drift apart in the first place, so we'd rather show
  // nothing than something we can't guarantee.
  const [motionStyles, setMotionStyles] = useState(null);
  // Hook videos are muted/silent by default. TikTok creators normally attach
  // a trending sound or native text-to-speech in TikTok's own editor after
  // exporting — AI-generated audio can't be posted as a "trending sound" and
  // would just be replaced. Off by default; opt in for platforms without an
  // in-app sound library (e.g. Reels/Shorts).
  const [includeHookAudio, setIncludeHookAudio] = useState(false);
  const [hookCategory, setHookCategory] = useState("");
  const [hookCustomPrompt, setHookCustomPrompt] = useState("");
  const pollingRef = useRef(null);
  const imagePollingRef = useRef(null);
  const imageJobIdRef = useRef(null);
  // Remembers the completed hook clip's URL. Kept in a ref (not state) so the
  // polling callbacks always read the current value, and so a failed extension
  // can put the finished hook back on screen instead of losing it.
  const hookVideoUrlRef = useRef(null);
  // The HOOK's job id specifically — tracked separately from videoJobId because
  // the backend bridges the extension off the hook clip. After an extension runs,
  // videoJobId points at the extension, so re-rolling with it would chain a
  // continuation of the continuation instead of re-rolling the extension.
  const hookJobIdRef = useRef(null);

  // Brand video state
  const [brandUrl, setBrandUrl] = useState("");
  const [brandProfile, setBrandProfile] = useState(null);
  const [brandedDuration, setBrandedDuration] = useState(15);
  const [videoModel, setVideoModel] = useState("minimax-h3"); // generative fallback engine
  // "" = Default (match the original hook's movement). Any explicit value is a
  // customization and routes generation to the generative engine instead of
  // Aleph's exact edit, so the default must be empty — not a real motion.

  // Load the target from query params. This is the ONLY way a target enters
  // the page — there is no target upload. Callers are the analysis screen
  // ("Face Swap This Hook") and the bookmarks screen, which pass an
  // /api/media/frames/... or /api/media/templates/... path respectively. The
  // backend independently allowlists those two subtrees, so a hand-edited
  // query string can't widen this.
  useEffect(() => {
    const frameUrl = searchParams.get("target");
    const videoId = searchParams.get("videoId");
    const frameIndex = searchParams.get("frame");
    const templateId = searchParams.get("templateId");
    const templateName = searchParams.get("templateName");
    if (frameUrl) {
      setTargetPreview(mediaUrl(frameUrl));
      setTargetFrameUrl(frameUrl);
      setTargetFile({ name: "target_frame.jpg", fromVideo: true });
      if (videoId) setVideoInfo({ videoId, frameIndex: frameIndex || "key" });
      if (templateId) setTemplateInfo({ templateId, name: templateName || "" });
    }
  }, [searchParams]);

  // Load brand profile
  useEffect(() => {
    api.getActiveBrand().then(setBrandProfile).catch(() => setBrandProfile(null));
  }, []);

  // Load the canonical motion styles (key, label, and the exact prompt text).
  useEffect(() => {
    api
      .getHookMotionStyles()
      .then((d) => setMotionStyles(Array.isArray(d?.styles) ? d.styles : []))
      .catch(() => setMotionStyles([]));
  }, []);

  // Ask the backend whether the exact-edit path is actually available for this
  // video instead of inferring it. Ignores a stale response if the attached
  // video changes mid-flight. On failure we leave it null rather than assuming
  // true, so the UI degrades to a neutral message instead of over-promising.
  useEffect(() => {
    const vid = videoInfo?.videoId;
    if (!vid) {
      setExactEditAvailable(null);
      return;
    }
    let cancelled = false;
    setExactEditAvailable(null);
    api
      .getHookEngine(vid)
      .then((d) => {
        if (!cancelled) setExactEditAvailable(!!d.exact_edit_available);
      })
      .catch(() => {
        if (!cancelled) setExactEditAvailable(null);
      });
    return () => {
      cancelled = true;
    };
  }, [videoInfo && videoInfo.videoId]);

  // Load saved face from localStorage
  useEffect(() => {
    try {
      if (localStorage.getItem(ACTIVE_FACE_SWAP_JOB_KEY)) return;
      const savedFace = localStorage.getItem("hookforge_saved_face");
      if (savedFace) {
        const { dataUrl, name } = JSON.parse(savedFace);
        if (dataUrl) {
          // Convert data URL back to a File object
          fetch(dataUrl)
            .then((res) => res.blob())
            .then((blob) => {
              const file = new File([blob], name || "saved_face.png", { type: blob.type });
              setSourceFile(file);
              setSourcePreview(dataUrl);
              setSavedFaceLoaded(true);
            })
            .catch(() => {}); // Silently fail if corrupt
        }
      }
    } catch (e) {
      // localStorage might be unavailable or data corrupt — ignore
    }
  }, []);

  // Cleanup polling
  useEffect(() => () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (imagePollingRef.current) clearInterval(imagePollingRef.current);
    imageJobIdRef.current = null;
  }, []);

  const currentStep = !targetFile ? 1 : !sourceFile ? 2 : 3;

  /* --- Handlers --- */
  const handleSourceSelect = (file) => { setSourceFile(file); setSourcePreview(URL.createObjectURL(file)); setSavedFaceLoaded(false); setResult(null); setGenError(null); };
  // Clearing the target drops back to the picker prompt — there is nothing to
  // upload in its place, so the only way forward is Discover or Bookmarks.
  const handleRemoveTarget = () => { setTargetFile(null); setTargetPreview(null); setTargetFrameUrl(null); setVideoInfo(null); setTemplateInfo(null); setResult(null); };
  const handleRemoveSource = () => { setSourceFile(null); setSourcePreview(null); setSavedFaceLoaded(false); setResult(null); };

  const handleSaveFace = () => {
    if (!sourcePreview || !sourceFile) return;
    try {
      // Read the file as data URL and store in localStorage
      const reader = new FileReader();
      reader.onload = () => {
        localStorage.setItem("hookforge_saved_face", JSON.stringify({
          dataUrl: reader.result,
          name: sourceFile.name || "saved_face.png",
          savedAt: new Date().toISOString(),
        }));
        setSavedFaceLoaded(true);
        toast.success("Face saved! It will auto-load next time.");
      };
      reader.readAsDataURL(sourceFile);
    } catch (e) {
      toast.error("Could not save face. Storage may be full.");
    }
  };

  const handleRemoveSavedFace = () => {
    localStorage.removeItem("hookforge_saved_face");
    setSourceFile(null);
    setSourcePreview(null);
    setSavedFaceLoaded(false);
    toast.success("Saved face removed.");
  };

  const startImagePolling = (jobId, appendVariants = false) => {
    if (imagePollingRef.current) clearInterval(imagePollingRef.current);
    imageJobIdRef.current = jobId;

    const poll = async () => {
      if (imageJobIdRef.current !== jobId) return;
      try {
        const status = await api.faceSwapStatus(jobId);
        if (imageJobIdRef.current !== jobId) return;
        if (status.status === "completed") {
          clearInterval(imagePollingRef.current);
          imagePollingRef.current = null;
          imageJobIdRef.current = null;
          if (!appendVariants) localStorage.removeItem(ACTIVE_FACE_SWAP_JOB_KEY);

          if (appendVariants) {
            setResult((previous) => {
              const existing = previous?.variants?.length
                ? previous.variants
                : [{
                    id: previous.id,
                    image_url: previous.generated_image_url,
                    resolution: previous.resolution,
                    variant_index: 0,
                  }];
              const additions = (status.variants || []).map((variant, index) => ({
                ...variant,
                variant_index: existing.length + index,
              }));
              return { ...previous, variants: [...existing, ...additions] };
            });
            setGeneratingMore(false);
            toast.success(`${status.variants?.length || 0} more variant${status.variants?.length === 1 ? "" : "s"} ready!`);
          } else {
            if (status.target_image_url) setTargetPreview(mediaUrl(status.target_image_url));
            if (status.source_face_url) setSourcePreview(mediaUrl(status.source_face_url));
            setResult(status);
            setGenerating(false);
            toast.success("Face swap complete!");
          }
        } else if (status.status === "failed") {
          clearInterval(imagePollingRef.current);
          imagePollingRef.current = null;
          imageJobIdRef.current = null;
          if (!appendVariants) localStorage.removeItem(ACTIVE_FACE_SWAP_JOB_KEY);
          const message = status.error
            ? `AI face swap generation failed. ${status.error}`
            : "AI face swap generation failed. Please try again.";
          if (appendVariants) {
            setGeneratingMore(false);
            toast.error(message);
          } else {
            setGenerating(false);
            setGenError(message);
          }
        }
      } catch (err) {
        if (err?.response?.status === 404 && imageJobIdRef.current === jobId) {
          clearInterval(imagePollingRef.current);
          imagePollingRef.current = null;
          imageJobIdRef.current = null;
          localStorage.removeItem(ACTIVE_FACE_SWAP_JOB_KEY);
          setGenerating(false);
          setGeneratingMore(false);
          setGenError("This face-swap job is no longer available. Please generate it again.");
          return;
        }
        // A transient status request failure should not cancel a provider generation.
        console.warn("Face-swap status poll failed:", err);
      }
    };

    poll();
    imagePollingRef.current = setInterval(poll, 3000);
  };

  // Resume an accepted job after a refresh or navigation back to this page.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(ACTIVE_FACE_SWAP_JOB_KEY) || "null");
      if (!saved?.jobId) return;
      if (saved.targetImageUrl) setTargetPreview(mediaUrl(saved.targetImageUrl));
      if (saved.sourceFaceUrl) setSourcePreview(mediaUrl(saved.sourceFaceUrl));
      setTargetFile({ name: "restored-target", restored: true });
      setSourceFile({ name: "restored-face", restored: true });
      setGenerating(true);
      setGenError(null);
      startImagePolling(saved.jobId);
    } catch (err) {
      localStorage.removeItem(ACTIVE_FACE_SWAP_JOB_KEY);
    }
    // The active job is restored only once when this page mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleGenerate = async () => {
    if (!targetFrameUrl) {
      toast.error("Pick a hook from Discover or your bookmarks first.");
      return;
    }
    if (!sourceFile) { toast.error("Upload a photo of your face first."); return; }
    setGenerating(true); setGenError(null); setResult(null); setSelectedVariant(0); setGeneratingMore(false);
    try {
      const formData = new FormData();
      formData.append("source_face", sourceFile);
      formData.append("target_frame_url", targetFrameUrl);
      if (customPrompt.trim()) formData.append("customization_prompt", customPrompt.trim());
      const submission = await api.faceSwap(formData);
      localStorage.setItem(ACTIVE_FACE_SWAP_JOB_KEY, JSON.stringify({
        jobId: submission.job_id,
        targetImageUrl: submission.target_image_url,
        sourceFaceUrl: submission.source_face_url,
        createdAt: new Date().toISOString(),
      }));
      startImagePolling(submission.job_id);
    } catch (err) {
      setGenError(getErrorMessage(err));
      setGenerating(false);
    }
  };

  const [generatingMore, setGeneratingMore] = useState(false);

  const handleGenerateMoreVariants = async () => {
    if (!targetFrameUrl || !sourceFile) return;
    setGeneratingMore(true);
    try {
      const formData = new FormData();
      formData.append("source_face", sourceFile);
      formData.append("target_frame_url", targetFrameUrl);
      formData.append("variants", String(Math.min(2, 4 - (result.variants?.length || 1))));
      if (customPrompt.trim()) formData.append("customization_prompt", customPrompt.trim());
      const submission = await api.faceSwap(formData);
      startImagePolling(submission.job_id, true);
    } catch (err) {
      toast.error(getErrorMessage(err));
      setGeneratingMore(false);
    }
  };

  // `phase` is passed explicitly rather than read from videoPhase state, because
  // setVideoPhase hasn't committed yet when this is called from a click handler.
  const startPolling = (jobId, phase = "hook") => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    let pollCount = 0;
    const MAX_POLLS = 120; // 10 minutes at 5s intervals

    const stop = () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      pollingRef.current = null;
    };

    // Return the UI to an actionable state on failure. For a failed extension
    // that means restoring the already-finished hook clip, so the user can retry
    // the extension instead of having to regenerate the hook from scratch.
    const fail = (message) => {
      stop();
      setVideoError(message);
      setFailedPhase(phase);
      setGeneratingVideo(false);
      setVideoStatus(null);
      if (phase === "extend" && hookVideoUrlRef.current) {
        setVideoUrl(hookVideoUrlRef.current);
        setVideoPhase("hook");
      }
    };

    pollingRef.current = setInterval(async () => {
      pollCount++;
      try {
        const s = await api.faceSwapVideoStatus(jobId);
        setVideoStatus(s.status);
        if (s.status === "completed") {
          const url = s.video_url || s.video_urls?.[0];
          if (phase === "hook") hookVideoUrlRef.current = url;
          setVideoUrl(url);
          setGeneratingVideo(false);
          stop();
          toast.success("Video ready!");
        } else if (s.status === "failed" || s.status === "cancelled" || s.status === "expired") {
          fail(s.error || "Video generation failed.");
        } else if (pollCount >= MAX_POLLS) {
          fail("Video generation timed out. Please try again.");
        }
      } catch (err) {
        console.warn("Poll error:", err);
        // A few transient status failures are tolerated; give up after that.
        if (pollCount > 5 && err?.response?.status >= 400) {
          fail(`Video status check failed (${err?.response?.status}). The video may still be generating — try refreshing.`);
        }
      }
    }, 5000);
  };

  const activeImageId = () =>
    (result?.variants && result.variants[selectedVariant]?.id) || result?.id;

  // ── Hook engine derivation ────────────────────────────────────────────────
  // Mirrors the backend's routing: exact edit requires the source to be
  // usable (reported by /hook-engine) AND no style input asking to deviate
  // from a literal replication. Kept in one place so the engine badge,
  // progress copy, tradeoff notice, and Default card can't drift apart.
  const styleOverrides = [
    hookCategory && "energy",
    hookCustomPrompt.trim() && "direction",
    motionStyle && "motion",
  ].filter(Boolean);
  const hasStyleOverride = styleOverrides.length > 0;
  const willUseExactEdit = exactEditAvailable === true && !hasStyleOverride;

  const handleGenerateHook = async () => {
    const activeId = activeImageId();
    if (!activeId) return;
    setVideoPhase("hook"); setGeneratingVideo(true); setVideoError(null); setFailedPhase(null);
    setVideoUrl(null); setVideoStatus("pending");
    setActualEngine(null);
    hookVideoUrlRef.current = null;
    try {
      const d = await api.faceSwapGenerateHook(
        activeId, motionStyle, videoModel, videoInfo?.videoId || "", "", includeHookAudio, hookCategory, hookCustomPrompt
      );
      hookJobIdRef.current = d.job_id;
      // Record which engine the backend actually chose, so the finished result
      // reports the truth even if it differs from what we predicted.
      setActualEngine(d.model || null);
      startPolling(d.job_id, "hook");
      if (d.from_template) toast.success(`Reusing "${d.template_name}" — no analysis cost.`);
    } catch (err) {
      setVideoError(getErrorMessage(err)); setFailedPhase("hook");
      setVideoStatus(null); setGeneratingVideo(false);
    }
  };

  const handleExtendVideo = async () => {
    const activeId = activeImageId();
    if (!activeId) return;
    setVideoPhase("extend"); setGeneratingVideo(true); setVideoError(null); setFailedPhase(null);
    setVideoUrl(null); setVideoStatus("pending");
    try {
      // Always bridge off the HOOK clip so re-rolling an extension regenerates
      // it from the hook's ending rather than chaining onto the last extension.
      const d = await api.faceSwapExtendVideo(activeId, hookJobIdRef.current || "", brandUrl.trim(), brandedDuration, videoModel, videoInfo?.videoId || "");
      startPolling(d.job_id, "extend");
    } catch (err) {
      setVideoError(getErrorMessage(err)); setFailedPhase("extend");
      setVideoStatus(null); setGeneratingVideo(false);
      // Put the finished hook back on screen so its Extend controls return.
      if (hookVideoUrlRef.current) { setVideoUrl(hookVideoUrlRef.current); setVideoPhase("hook"); }
    }
  };

  // The retry affordance must repeat whichever step failed — retrying a failed
  // extension by regenerating the hook would silently do the wrong thing.
  const retryVideo = () => {
    if (failedPhase === "extend") handleExtendVideo();
    else handleGenerateHook();
  };

  const handleReset = () => {
    setTargetFile(null); setTargetPreview(null); setTargetFrameUrl(null); setVideoInfo(null);
    setSourceFile(null); setSourcePreview(null); setResult(null); setGenError(null);
    setSelectedVariant(0); setCustomPrompt("");
    setGeneratingVideo(false);
    setVideoStatus(null); setVideoUrl(null); setVideoError(null); setFailedPhase(null);
    setVideoPhase("hook"); setMotionStyle("");
    setHookCategory(""); setHookCustomPrompt("");
    // videoInfo is cleared here too, and the effect keyed on it will null this
    // out — set it explicitly so there's no frame where a stale availability
    // from the previous video is still on screen.
    setExactEditAvailable(null);
    setActualEngine(null);
    // Match the initial state (15s), not an arbitrary different default.
    setBrandUrl(""); setBrandedDuration(15); setGeneratingMore(false);
    setIncludeHookAudio(false);
    hookVideoUrlRef.current = null;
    hookJobIdRef.current = null;
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
    if (imagePollingRef.current) { clearInterval(imagePollingRef.current); imagePollingRef.current = null; }
    imageJobIdRef.current = null;
    localStorage.removeItem(ACTIVE_FACE_SWAP_JOB_KEY);
  };

  /* ===================== RENDER ===================== */
  return (
    <div className="mx-auto max-w-4xl space-y-6">

      {/* ---------- HEADER ---------- */}
      <PageHeader
        icon={Repeat2}
        title="Face Swap"
        align="center"
        // Keyed off targetPreview rather than videoInfo: a target can now come
        // from a saved template too, which sets templateInfo and leaves
        // videoInfo null.
        description={
          targetPreview && savedFaceLoaded
            ? "Your hook frame and saved face are ready. Hit Generate."
            : targetPreview
            ? "Your hook frame is ready. Add your face to swap."
            : savedFaceLoaded
            ? "Your saved face is loaded. Pick a hook from Discover or your bookmarks."
            : "Pick a hook from Discover or your bookmarks, then add your face."
        }
      />

      {/* ---------- STEP INDICATOR ---------- */}
      <StepDots
        total={3}
        current={currentStep}
        complete={!!result}
        testId="face-swap-step-indicator"
      />


      {/* ---------- UPLOAD PHASE ---------- */}
      {!result && (
        <>
          {targetPreview ? (
            /* --- TARGET FRAME ALREADY CHOSEN (discovery or bookmark) --- */
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {/* Chosen frame — always read-only, never an upload zone */}
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StepBadge done>1</StepBadge>
                  <span className="text-sm font-semibold">Hook Frame Selected</span>
                  {videoInfo ? (
                    <Badge variant="indigo" className="text-xs">
                      <Film className="h-3 w-3" /> Frame {videoInfo.frameIndex}
                    </Badge>
                  ) : templateInfo ? (
                    <Badge variant="indigo" className="text-xs">
                      <Bookmark className="h-3 w-3" /> Saved template
                    </Badge>
                  ) : null}
                </div>
                <div className="group relative overflow-hidden rounded-2xl border border-[color:var(--hairline)]">
                  <img src={targetPreview} alt="Selected video frame" className="aspect-[3/4] w-full object-cover" />
                  <button
                    onClick={handleRemoveTarget}
                    className="absolute right-2.5 top-2.5 rounded-full bg-black/60 p-1.5 text-white opacity-0 backdrop-blur-sm transition-opacity hover:bg-black/85 group-hover:opacity-100"
                    aria-label="Change target"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                  <div className="absolute bottom-2.5 left-2.5 inline-flex items-center gap-1 rounded-full bg-[color:var(--brand-indigo)] px-2 py-0.5 text-xs font-bold text-white">
                    <Check className="h-2.5 w-2.5" /> {templateInfo ? "From bookmark" : "From discovery"}
                  </div>
                </div>
              </div>

              {/* Source face (the only thing user needs to upload) */}
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StepBadge done={!!sourceFile} current={!sourceFile}>2</StepBadge>
                  <span className="text-sm font-semibold">Your Face</span>
                  {savedFaceLoaded && (
                    <Badge className="border-emerald-500/25 bg-emerald-500/10 text-xs text-emerald-400">
                      <Save className="h-2.5 w-2.5" /> Saved
                    </Badge>
                  )}
                </div>
                <DropZone onFileSelect={handleSourceSelect} accept="image/jpeg,image/png,image/webp" label="Drop your face photo here" sublabel="Clear, frontal view works best" preview={sourcePreview} onRemove={handleRemoveSource} testId="source" icon={User} />
                {sourceFile && !savedFaceLoaded && (
                  <button onClick={handleSaveFace} className="flex items-center gap-1.5 text-xs font-medium text-[color:var(--brand-indigo)] transition-colors hover:text-[color:var(--brand-indigo-dark)]" data-testid="save-face-button">
                    <Save className="h-3 w-3" /> Save this face for next time
                  </button>
                )}
                {savedFaceLoaded && (
                  <button onClick={handleRemoveSavedFace} className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-[color:var(--brand-coral)]" data-testid="remove-saved-face-button">
                    <Trash2 className="h-3 w-3" /> Remove saved face
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* --- NO TARGET YET ---------------------------------------------
               There is deliberately no target upload. A swap only makes sense
               against a hook that has been analyzed, so the two entry points
               are the discovery feed and saved templates. This screen exists
               to route the user to one of them rather than dead-ending. */
            <div
              className="surface mx-auto max-w-xl space-y-5 rounded-2xl p-6 text-center"
              data-testid="face-swap-no-target"
            >
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                <Film className="h-5 w-5" />
              </span>
              <div className="space-y-1.5">
                <h2 className="font-display text-lg font-semibold">Pick a hook to swap into</h2>
                <p className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground">
                  Face swaps run against a frame from a hook that's already been analyzed. Choose a
                  trending video, or reuse one of your saved templates.
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
                <a href="/discover" className="sm:w-auto">
                  <Button variant="brand" className="w-full gap-1.5" data-testid="go-to-discover-cta">
                    <Compass className="h-4 w-4" /> Browse trending hooks
                  </Button>
                </a>
                <a href="/bookmarks" className="sm:w-auto">
                  <Button variant="outline" className="w-full gap-1.5" data-testid="go-to-bookmarks-cta">
                    <Bookmark className="h-4 w-4" /> Use a saved template
                  </Button>
                </a>
              </div>

              {savedFaceLoaded && (
                <p className="flex items-center justify-center gap-1.5 border-t border-[color:var(--hairline)] pt-4 text-xs text-muted-foreground">
                  <Save className="h-3 w-3 text-emerald-400" />
                  Your saved face is ready — it'll load automatically once you pick a hook.
                </p>
              )}
            </div>
          )}

          {/* Customization prompt (optional) */}
          {targetFile && sourceFile && !generating && (
            <div className="mx-auto max-w-md space-y-2" data-testid="customization-prompt-section">
              <label htmlFor="custom-prompt" className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <Sparkles className="h-3 w-3 text-[color:var(--brand-indigo)]" />
                Customize (optional)
              </label>
              <Input
                id="custom-prompt"
                placeholder="e.g. Change the outfit to a black leather jacket, or Put me in a coffee shop..."
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                className="text-sm"
                data-testid="customization-prompt-input"
              />
              <p className="text-xs leading-snug text-muted-foreground">
                Describe changes to clothing, environment, or style. Leave empty to keep the original scene.
              </p>
            </div>
          )}

          {/* Generate button */}
          {targetFile && sourceFile && (
            <div className="pt-1 text-center">
              {generating ? (
                <div className="surface mx-auto max-w-md rounded-2xl p-5">
                  <GenerationProgress stages={["Analyzing faces", "Matching lighting", "Generating image", "Final blending"]} active={true} />
                </div>
              ) : (
                <Button onClick={handleGenerate} size="lg" variant="brand" className="px-9" data-testid="generate-swap-button">
                  <Sparkles className="h-4 w-4" /> Generate Face Swap
                </Button>
              )}
            </div>
          )}

          {genError && (
            <Alert variant="destructive" className="mx-auto max-w-md" data-testid="face-swap-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription className="flex items-center justify-between gap-2">
                <span className="text-sm">{genError}</span>
                <Button size="sm" variant="ghost" onClick={handleGenerate} className="shrink-0 gap-1"><RotateCcw className="h-3 w-3" /> Retry</Button>
              </AlertDescription>
            </Alert>
          )}
        </>
      )}

      {/* ---------- RESULT PHASE ---------- */}
      {result && (
        <div className="space-y-5">

          {/* Result comparison */}
          <div
            className="overflow-hidden rounded-2xl border border-[color:var(--indigo-35)] shadow-[var(--glow-indigo)]"
            data-testid="face-swap-result"
          >
            {/* On phones the two inputs sit side by side and the result spans
                the full width beneath them, so the payoff image never shrinks
                to a third of a 375px screen. Three-up from md upwards. */}
            <div className="grid grid-cols-2 gap-px bg-border md:grid-cols-3">
              <div className="bg-card p-3 text-center">
                <p className="eyebrow mb-2">Target</p>
                <img src={targetPreview} alt="Target" className="aspect-[3/4] w-full rounded-lg object-cover" />
              </div>
              <div className="bg-card p-3 text-center">
                <p className="eyebrow mb-2">Your Face</p>
                <img src={sourcePreview} alt="Source" className="aspect-[3/4] w-full rounded-lg object-cover" />
              </div>
              <div className="col-span-2 bg-[color:var(--indigo-6)] p-3 text-center md:col-span-1">
                <p className="eyebrow mb-2 flex items-center justify-center gap-1 text-[color:var(--brand-indigo)]">
                  <Sparkles className="h-2.5 w-2.5" /> Result
                </p>
                <img src={mediaUrl((result.variants && result.variants[selectedVariant]?.image_url) || result.generated_image_url)} alt="Result" className="aspect-[3/4] w-full rounded-lg object-cover ring-1 ring-[color:var(--brand-indigo)]" data-testid="face-swap-generated-image" />
              </div>
            </div>
          </div>

          {/* Variant picker — shown when multiple variants are available */}
          {result.variants && result.variants.length > 1 && (
            <div className="surface space-y-3 rounded-2xl p-4" data-testid="variant-picker">
              <div className="flex items-center justify-between gap-3">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <Sparkles className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" />
                  Pick your best variant
                </p>
                <span className="text-xs text-muted-foreground">{selectedVariant + 1} of {result.variants.length} selected</span>
              </div>
              {/* Two-up on phones keeps each variant large enough to actually
                  judge a face swap; four-up on large screens avoids leaving a
                  lone orphan on the second row when all 4 variants exist. */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {result.variants.map((variant, idx) => (
                  <button
                    key={variant.id}
                    onClick={() => setSelectedVariant(idx)}
                    className={`relative overflow-hidden rounded-xl border-2 transition-[transform,border-color,box-shadow] duration-200 ${
                      selectedVariant === idx
                        ? "scale-[1.02] border-[color:var(--brand-indigo)] shadow-[var(--glow-indigo)]"
                        : "border-[color:var(--hairline)] hover:scale-[1.01] hover:border-[color:var(--indigo-45)]"
                    }`}
                    data-testid={`variant-option-${idx}`}
                  >
                    <img
                      src={mediaUrl(variant.image_url)}
                      alt={`Variant ${idx + 1}`}
                      className="aspect-[3/4] w-full object-cover"
                    />
                    {selectedVariant === idx && (
                      <div className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-[color:var(--brand-indigo)] text-white shadow-[var(--shadow-sm)]">
                        <Check className="h-3 w-3" />
                      </div>
                    )}
                    <div className="absolute bottom-1.5 left-1.5">
                      <span className={`rounded-full px-1.5 py-0.5 text-xs font-bold ${
                        selectedVariant === idx ? "bg-[color:var(--brand-indigo)] text-white" : "bg-black/60 text-white"
                      }`}>
                        {idx + 1}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Generate more variants button */}
          {targetFile && sourceFile && !targetFile.restored && !sourceFile.restored && (!result.variants || result.variants.length < 4) && (
            <Button
              onClick={handleGenerateMoreVariants}
              disabled={generatingMore}
              variant="outline"
              className="w-full gap-1.5"
              data-testid="generate-more-variants-button"
            >
              {generatingMore ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              {generatingMore ? "Generating alternatives..." : "Generate Alternatives"}
            </Button>
          )}

          {/* Quick actions */}
          <div className="flex gap-2">
            <a href={mediaUrl((result.variants && result.variants[selectedVariant]?.image_url) || result.generated_image_url)} download target="_blank" rel="noreferrer" className="flex-1">
              <Button variant="outline" className="w-full gap-1.5" data-testid="download-swap-button"><Download className="h-3.5 w-3.5" /> Download</Button>
            </a>
            <Button onClick={handleReset} variant="ghost" className="gap-1.5 text-muted-foreground" data-testid="new-swap-button"><RotateCcw className="h-3.5 w-3.5" /> Reset</Button>
          </div>

          {/* ---------- VIDEO GENERATION (Hook → Extend) ---------- */}
          <div className="surface space-y-5 rounded-2xl p-5" data-testid="phase2-video-section">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--coral-25)] bg-[color:var(--coral-12)] text-[color:var(--brand-coral)]">
                <Clapperboard className="h-[18px] w-[18px]" />
              </span>
              <div>
                <h2 className="font-display text-base font-semibold">Create Video</h2>
                <p className="text-xs text-muted-foreground">Step 1: 3s hook &rarr; Step 2: Extend with brand message</p>
              </div>
            </div>

            {/* Hook video complete — show it + offer extend */}
            {videoUrl && videoPhase === "hook" && (
              <div className="space-y-5" data-testid="hook-video-result">
                <div className="space-y-2.5">
                  <StepLabel step="Step 1" title={`3s Hook Video${!includeHookAudio ? " (muted)" : ""}`} done />
                  <video src={videoUrl} controls autoPlay loop muted={!includeHookAudio} className="w-full rounded-xl border border-[color:var(--hairline)]" data-testid="hook-video-player" />
                  {/* Ground truth: what the backend actually ran. The pre-generation
                      badge is a prediction from a structural check; this is the
                      outcome, so a prediction that didn't hold is visible rather
                      than silently wrong. */}
                  {actualEngine && (
                    <p className="text-xs text-muted-foreground" data-testid="hook-engine-used">
                      {actualEngine === "aleph-2" ? (
                        <>
                          <span className="font-semibold text-[color:var(--brand-indigo)]">Exact edit</span>
                          {" "}— generated by editing the original hook video, so movement, gestures, camera, and clothing match it.
                        </>
                      ) : (
                        <>
                          <span className="font-semibold">Generative engine</span>
                          {" "}— this hook was regenerated rather than edited
                          {willUseExactEdit ? ", because the exact edit couldn't be completed for this video" : ""}.
                        </>
                      )}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <a href={videoUrl} download target="_blank" rel="noreferrer" className="min-w-[160px] flex-1">
                    <Button variant="outline" className="w-full gap-1.5" data-testid="download-hook-button"><Download className="h-3.5 w-3.5" /> Download Hook</Button>
                  </a>
                  <Button
                    onClick={handleGenerateHook}
                    disabled={generatingVideo}
                    variant="outline"
                    className="gap-1.5"
                    data-testid="reroll-hook-button"
                    title="Generate another take with the same prompt — only costs the video generation, no re-analysis"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Re-roll
                  </Button>
                  <Button onClick={handleReset} variant="ghost" className="gap-1.5 text-muted-foreground"><RotateCcw className="h-3.5 w-3.5" /> Reset</Button>
                </div>

                {/* Extend section */}
                <div className="space-y-3.5 border-t border-[color:var(--hairline)] pt-4">
                  <StepLabel step="Step 2" tone="coral" title="Extend with brand message" />
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Now add a longer continuation with your brand message, voiceover, and CTA.
                    {brandProfile && <span className="text-[color:var(--brand-indigo)]"> Brand profile detected.</span>}
                  </p>
                  <div className="flex gap-2">
                    <Input value={brandUrl} onChange={(e) => setBrandUrl(e.target.value)} placeholder="https://yourbrand.com" className="flex-1 text-sm" data-testid="extend-brand-url-input" />
                    <div className="w-20 shrink-0">
                      <Input type="number" min={5} max={15} value={brandedDuration} onChange={(e) => setBrandedDuration(Math.max(5, Math.min(15, Number(e.target.value) || 10)))} className="text-center text-sm" />
                      <p className="mt-1 text-center text-xs text-muted-foreground">{brandedDuration}s</p>
                    </div>
                  </div>
                  {/* Model selector */}
                  <div className="flex gap-1 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 p-1" data-testid="extend-model-selector">
                    {[
                      { key: "minimax-h3", label: "MiniMax H3", sub: "2K · Native audio · V2V (extend)" },
                    ].map((m) => (
                      <button key={m.key} onClick={() => setVideoModel(m.key)}
                        className={`flex-1 rounded-lg px-2 py-1.5 text-center transition-colors duration-200 ${videoModel === m.key ? "bg-[color:var(--indigo-10)]" : "hover:bg-[color:var(--indigo-6)]"}`}>
                        <span className={`block text-xs font-semibold ${videoModel === m.key ? "text-[color:var(--brand-indigo)]" : "text-muted-foreground"}`}>{m.label}</span>
                        <span className="text-xs text-muted-foreground">{m.sub}</span>
                      </button>
                    ))}
                  </div>
                  <Button onClick={handleExtendVideo} disabled={generatingVideo} variant="brand" className="w-full" data-testid="extend-video-button">
                    <Film className="h-4 w-4" /> Extend to {brandedDuration}s Branded Video
                  </Button>
                </div>
              </div>
            )}

            {/* Extended video complete */}
            {videoUrl && videoPhase === "extend" && (
              <div className="space-y-3.5" data-testid="extended-video-result">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-white">Complete</span>
                  <span className="text-xs font-semibold">Extended branded video ready</span>
                </div>
                <video src={videoUrl} controls autoPlay loop className="w-full rounded-xl border border-[color:var(--hairline)]" data-testid="extended-video-player" />
                <div className="flex flex-wrap gap-2">
                  <a href={videoUrl} download target="_blank" rel="noreferrer" className="min-w-[160px] flex-1">
                    <Button variant="accent" className="w-full gap-1.5" data-testid="download-extended-button"><Download className="h-3.5 w-3.5" /> Download Video</Button>
                  </a>
                  <Button
                    onClick={handleExtendVideo}
                    disabled={generatingVideo}
                    variant="outline"
                    className="gap-1.5"
                    data-testid="reroll-extend-button"
                    title="Generate another take with the same prompt"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Re-roll
                  </Button>
                  <Button onClick={handleReset} variant="outline" className="gap-1.5"><RotateCcw className="h-3.5 w-3.5" /> New</Button>
                </div>
              </div>
            )}

            {/* Video in progress */}
            {!videoUrl && (videoStatus === "pending" || videoStatus === "in_progress") && (
              <div className="flex items-center gap-3.5 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 p-4">
                <Loader2 className="h-5 w-5 shrink-0 animate-spin text-[color:var(--brand-indigo)]" />
                <div>
                  <p className="text-sm font-semibold">{videoStatus === "pending" ? "Queued..." : "Generating..."}</p>
                  <p className="text-xs text-muted-foreground">
                    {videoPhase === "hook"
                      ? (willUseExactEdit
                          ? "Editing the original hook video with your face (30s-2min)"
                          : `Creating 3s ${includeHookAudio ? "hook with AI audio" : "silent hook"} (30s-2min)`)
                      : "Extending video with brand message (1-3min)"}
                  </p>
                </div>
              </div>
            )}

            {videoError && (
              <div className="flex items-center gap-2.5 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive" data-testid="video-error">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1">{videoError}</span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={retryVideo}
                  disabled={generatingVideo}
                  className="h-auto shrink-0 gap-1 px-2 py-1 text-destructive"
                  data-testid="retry-video-button"
                  title={failedPhase === "extend" ? "Retry the extension" : "Retry the hook video"}
                >
                  <RotateCcw className="h-3 w-3" />
                  {failedPhase === "extend" ? "Retry extend" : "Retry"}
                </Button>
              </div>
            )}

            {/* Initial state — generate hook button */}
            {!videoUrl && !videoStatus && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <StepLabel step="Step 1" title="Generate 3s Hook" />
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {videoInfo
                      ? "Edits the original hook video directly with your face — body movements, hand gestures, camera, and clothing stay pixel-for-pixel identical."
                      : "Animates your photo into a hook using your face."}
                    {" "}Muted by default — add a trending sound or text-to-speech in TikTok's editor after exporting.
                  </p>
                </div>

                {/* Audio toggle — off by default (see rationale above) */}
                <button
                  type="button"
                  onClick={() => setIncludeHookAudio((v) => !v)}
                  className="flex w-full items-center justify-between gap-2 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 px-3.5 py-2.5 transition-colors hover:border-[color:var(--indigo-35)]"
                  data-testid="hook-audio-toggle"
                  aria-pressed={includeHookAudio}
                >
                  <span className="flex items-center gap-2.5 text-left">
                    {includeHookAudio ? (
                      <Volume2 className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                    ) : (
                      <VolumeX className="h-4 w-4 text-muted-foreground" />
                    )}
                    <span className="text-xs font-semibold">
                      {includeHookAudio ? "AI audio on" : "Muted (recommended for TikTok)"}
                    </span>
                  </span>
                  <span
                    className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${
                      includeHookAudio ? "bg-[color:var(--brand-indigo)]" : "bg-border"
                    }`}
                  >
                    <span
                      className={`inline-block h-3 w-3 rounded-full bg-white transition-transform ${
                        includeHookAudio ? "translate-x-3.5" : "translate-x-0.5"
                      }`}
                    />
                  </span>
                </button>


                {/* Hook style selector — optional category + custom prompt */}
                <HookStyleSelector
                  hookCategory={hookCategory}
                  onCategoryChange={setHookCategory}
                  hookCustomPrompt={hookCustomPrompt}
                  onCustomPromptChange={setHookCustomPrompt}
                  disabled={generatingVideo}
                />

                {/* Motion style selector. Always shown so "Default" is an explicit,
                    visible choice rather than an invisible one — previously this was
                    hidden whenever a source video existed while still shipping
                    "lean-in" to the backend, so users had no way to see or control it.
                    Default ("") means "don't dictate the movement", which is what keeps
                    a video-backed hook eligible for Aleph's exact edit. */}
                <div className="space-y-2">
                  <p className="eyebrow">Motion style</p>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {/* Default / no override */}
                    <button
                      onClick={() => setMotionStyle("")}
                      className={`rounded-xl border p-2.5 text-left transition-colors duration-200 ${!motionStyle ? "border-[color:var(--brand-indigo)] bg-[color:var(--indigo-8)]" : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"}`}
                      data-testid="motion-default"
                    >
                      <span className={`block text-xs font-semibold ${!motionStyle ? "text-[color:var(--brand-indigo)]" : "text-foreground"}`}>
                        Default {exactEditAvailable === true ? "— Match original" : "— Auto"}
                      </span>
                      <span className="text-xs leading-snug text-muted-foreground">
                        {exactEditAvailable === true
                          ? "Replicate the original hook's real movement exactly. Recommended — this is the only option that uses the exact-edit engine."
                          : "Let AI pick the movement that best fits your photo."}
                      </span>
                    </button>

                    {(motionStyles || []).map((m) => (
                      <button
                        key={m.key}
                        /* Toggle: clicking the active card returns to Default, so a
                           selection is never a one-way door. */
                        onClick={() => setMotionStyle(motionStyle === m.key ? "" : m.key)}
                        className={`rounded-xl border p-2.5 text-left transition-colors duration-200 ${motionStyle === m.key ? "border-[color:var(--brand-indigo)] bg-[color:var(--indigo-8)]" : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"}`}
                        data-testid={`motion-${m.key}`}
                      >
                        <span className={`block text-xs font-semibold ${motionStyle === m.key ? "text-[color:var(--brand-indigo)]" : "text-foreground"}`}>{m.label}</span>
                        {/* Rendered verbatim from the backend — this is the actual
                            instruction the video model receives, capitalized for
                            readability only. */}
                        {m.motion && (
                          <span className="text-xs leading-snug text-muted-foreground">
                            {m.motion.charAt(0).toUpperCase() + m.motion.slice(1)}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Explicit tradeoff notice — only meaningful when a source video
                    exists, since that's the only case where an exact edit was
                    actually available to give up. */}
                {exactEditAvailable === true && hasStyleOverride && (
                  <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-2.5" data-testid="aleph-tradeoff-notice">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                    <p className="text-xs leading-snug text-muted-foreground">
                      <span className="font-semibold text-amber-500">Exact edit turned off.</span>{" "}
                      Custom {styleOverrides.join(", ")}{" "}
                      means the hook is regenerated instead of edited, so body movement,
                      gestures, camera, and clothing won't match the original pixel-for-pixel.
                      Clear your selections to restore the exact edit.
                    </p>
                  </div>
                )}

                {/* Engine indicator — the engine is chosen automatically based on
                    whether an exact source video exists to edit and whether the
                    user customized the hook away from a literal replication.
                    Aleph 2.0 edits the real hook video directly (exact replication);
                    the generative fallback synthesizes a new scene when there's no
                    source video to edit or the hook was customized. */}
                <div className="rounded-xl border border-[color:var(--hairline)] bg-secondary/30 p-2.5" data-testid="hook-model-indicator">
                  {willUseExactEdit ? (
                    <>
                      <span className="block text-xs font-semibold text-[color:var(--brand-indigo)]">Runway Aleph 2.0 &middot; Exact edit</span>
                      <span className="text-xs text-muted-foreground">Edits the original hook video directly — body movement, gestures, camera, and clothing stay pixel-for-pixel identical. Only the face changes.</span>
                    </>
                  ) : videoInfo && exactEditAvailable === null ? (
                    /* Availability not yet known (request in flight, or it failed).
                       Stay neutral rather than claiming either engine. */
                    <>
                      <span className="block text-xs font-semibold text-muted-foreground">Checking engine…</span>
                      <span className="text-xs text-muted-foreground">Determining whether this hook can be edited exactly.</span>
                    </>
                  ) : (
                    <>
                      <span className="block text-xs font-semibold text-muted-foreground">Generative engine</span>
                      <span className="text-xs text-muted-foreground">
                        {exactEditAvailable === true && hasStyleOverride
                          ? `Custom ${styleOverrides.join(", ")} was set, so a new scene is generated instead of editing the original video.`
                          : videoInfo
                            ? "The original clip for this video isn't available to edit, so a new scene is generated instead."
                            : "No source video to edit — a new scene is generated from your photo."}
                      </span>
                    </>
                  )}
                </div>

                <Button onClick={handleGenerateHook} disabled={generatingVideo} variant="brand" size="lg" className="w-full" data-testid="generate-hook-button">
                  <Clapperboard className="h-4 w-4" />
                  Generate 3s Hook Video
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
