import { useState, useRef, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Alert, AlertDescription } from "../components/ui/alert";
import GenerationProgress from "../components/GenerationProgress";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import {
  Upload,
  Sparkles,
  AlertTriangle,
  RotateCcw,
  X,
  Download,
  ImageIcon,
  User,
  Wand2,
  Check,
  Film,
  Clapperboard,
  Play,
  Clock,
  Loader2,
  Globe,
  ArrowRight,
  Save,
  Trash2,
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
      <div className="relative group" data-testid={`${testId}-preview`}>
        <img src={preview} alt="Preview" className="w-full rounded-xl object-cover aspect-[3/4]" />
        <button
          onClick={onRemove}
          className="absolute top-2 right-2 rounded-full bg-black/60 text-white p-1.5 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/80"
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
        className={`w-full flex flex-col items-center justify-center gap-2.5 rounded-xl border-2 border-dashed py-12 cursor-pointer transition-all ${
          isDragging ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.04)] scale-[1.01]" : "border-border hover:border-[color:rgba(99,102,241,0.4)] bg-card/50 hover:bg-card/80"
        }`}
        data-testid={`${testId}-dropzone`}
      >
        <div className={`h-11 w-11 rounded-full flex items-center justify-center ${isDragging ? "bg-[color:rgba(99,102,241,0.1)]" : "bg-muted"}`}>
          <Icon className={`h-5 w-5 ${isDragging ? "text-[color:var(--brand-teal)]" : "text-muted-foreground"}`} />
        </div>
        <span className="text-sm font-medium">{label}</span>
        <span className="text-[11px] text-muted-foreground">{sublabel}</span>
      </button>
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
  const [savedFaceLoaded, setSavedFaceLoaded] = useState(false);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedVariant, setSelectedVariant] = useState(0);

  // Video state
  const [videoDuration, setVideoDuration] = useState(10);
  const [videoPrompt, setVideoPrompt] = useState("");
  const [generatingVideo, setGeneratingVideo] = useState(false);
  const [videoJobId, setVideoJobId] = useState(null);
  const [videoStatus, setVideoStatus] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoError, setVideoError] = useState(null);
  const [videoPhase, setVideoPhase] = useState("hook"); // "hook" | "extend"
  const [motionStyle, setMotionStyle] = useState("lean-in");
  const pollingRef = useRef(null);
  const imagePollingRef = useRef(null);
  const imageJobIdRef = useRef(null);

  // Brand video state
  const [brandUrl, setBrandUrl] = useState("");
  const [brandProfile, setBrandProfile] = useState(null);
  const [brandedDuration, setBrandedDuration] = useState(15);
  const [brandedPrompt, setBrandedPrompt] = useState("");
  const [brandedPromptBrand, setBrandedPromptBrand] = useState("");
  const [generatingBrandedPrompt, setGeneratingBrandedPrompt] = useState(false);
  const [brandedPromptError, setBrandedPromptError] = useState(null);

  // Video mode tab
  const [videoMode, setVideoMode] = useState("branded"); // "preview" | "branded"
  const [videoModel, setVideoModel] = useState("seedance-2.0"); // default to best quality

  // Load target from query params
  useEffect(() => {
    const frameUrl = searchParams.get("target");
    const videoId = searchParams.get("videoId");
    const frameIndex = searchParams.get("frame");
    if (frameUrl) {
      setTargetPreview(mediaUrl(frameUrl));
      setTargetFrameUrl(frameUrl);
      setTargetFile({ name: "video_frame.jpg", fromVideo: true });
      if (videoId) setVideoInfo({ videoId, frameIndex: frameIndex || "key" });
    }
  }, [searchParams]);

  // Load brand profile
  useEffect(() => {
    api.getActiveBrand().then(setBrandProfile).catch(() => setBrandProfile(null));
  }, []);

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
  const handleTargetSelect = (file) => { setTargetFile(file); setTargetPreview(URL.createObjectURL(file)); setTargetFrameUrl(null); setVideoInfo(null); setResult(null); setGenError(null); };
  const handleSourceSelect = (file) => { setSourceFile(file); setSourcePreview(URL.createObjectURL(file)); setSavedFaceLoaded(false); setResult(null); setGenError(null); };
  const handleRemoveTarget = () => { setTargetFile(null); setTargetPreview(null); setTargetFrameUrl(null); setVideoInfo(null); setResult(null); };
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
    if (!targetFile || !sourceFile) { toast.error("Upload both images first."); return; }
    setGenerating(true); setGenError(null); setResult(null); setSelectedVariant(0); setGeneratingMore(false);
    try {
      const formData = new FormData();
      formData.append("source_face", sourceFile);
      if (targetFrameUrl) formData.append("target_frame_url", targetFrameUrl);
      else formData.append("target_image", targetFile);
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
    if (!targetFile || !sourceFile) return;
    setGeneratingMore(true);
    try {
      const formData = new FormData();
      formData.append("source_face", sourceFile);
      if (targetFrameUrl) formData.append("target_frame_url", targetFrameUrl);
      else formData.append("target_image", targetFile);
      formData.append("variants", String(Math.min(2, 4 - (result.variants?.length || 1))));
      const submission = await api.faceSwap(formData);
      startImagePolling(submission.job_id, true);
    } catch (err) {
      toast.error(getErrorMessage(err));
      setGeneratingMore(false);
    }
  };

  const startPolling = (jobId) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const s = await api.faceSwapVideoStatus(jobId);
        setVideoStatus(s.status);
        if (s.status === "completed") { setVideoUrl(s.video_url || s.video_urls?.[0]); setGeneratingVideo(false); clearInterval(pollingRef.current); pollingRef.current = null; toast.success("Video ready!"); }
        else if (s.status === "failed") { setVideoError(s.error || "Generation failed."); setGeneratingVideo(false); clearInterval(pollingRef.current); pollingRef.current = null; }
      } catch (err) { console.warn("Poll error:", err); }
    }, 5000);
  };

  const handleGenerateHook = async () => {
    const activeId = (result?.variants && result.variants[selectedVariant]?.id) || result?.id;
    if (!activeId) return;
    setVideoPhase("hook"); setGeneratingVideo(true); setVideoError(null); setVideoUrl(null); setVideoStatus("pending");
    try {
      const d = await api.faceSwapGenerateHook(activeId, motionStyle, videoModel, videoInfo?.videoId || "");
      setVideoJobId(d.job_id); startPolling(d.job_id);
    } catch (err) { setVideoError(getErrorMessage(err)); setVideoStatus(null); setGeneratingVideo(false); }
  };

  const handleExtendVideo = async () => {
    const activeId = (result?.variants && result.variants[selectedVariant]?.id) || result?.id;
    if (!activeId) return;
    setVideoPhase("extend"); setGeneratingVideo(true); setVideoError(null); setVideoUrl(null); setVideoStatus("pending");
    try {
      const d = await api.faceSwapExtendVideo(activeId, videoJobId, brandUrl.trim(), brandedDuration, videoModel);
      setVideoJobId(d.job_id); startPolling(d.job_id);
    } catch (err) { setVideoError(getErrorMessage(err)); setVideoStatus(null); setGeneratingVideo(false); }
  };

  const handleQuickPreview = async () => {
    const activeId = (result?.variants && result.variants[selectedVariant]?.id) || result?.id;
    if (!activeId) return;
    setVideoPhase("hook"); setVideoDuration(5); setVideoPrompt(""); setGeneratingVideo(true); setVideoError(null); setVideoUrl(null); setVideoStatus("pending");
    try { const d = await api.faceSwapGenerateHook(activeId, motionStyle, "seedance-2.0-fast", videoInfo?.videoId || ""); setVideoJobId(d.job_id); startPolling(d.job_id); }
    catch (err) { setVideoError(getErrorMessage(err)); setVideoStatus(null); setGeneratingVideo(false); }
  };

  const handleGenerateBrandedPrompt = async () => {
    const activeId = (result?.variants && result.variants[selectedVariant]?.id) || result?.id;
    if (!activeId) return;
    if (!brandUrl.trim() && !brandProfile) { toast.error("Enter your brand URL."); return; }
    setGeneratingBrandedPrompt(true); setBrandedPromptError(null); setBrandedPrompt("");
    try {
      const d = await api.faceSwapBrandedPrompt(activeId, brandUrl.trim(), videoInfo?.videoId || "", brandedDuration);
      setBrandedPrompt(d.video_prompt || ""); setBrandedPromptBrand(d.brand_name || "");
      toast.success("Prompt generated!");
    } catch (err) { setBrandedPromptError(getErrorMessage(err)); }
    finally { setGeneratingBrandedPrompt(false); }
  };

  const handleGenerateBrandedVideo = async () => {
    const activeId = (result?.variants && result.variants[selectedVariant]?.id) || result?.id;
    if (!activeId || !brandedPrompt) return;
    setVideoDuration(brandedDuration); setGeneratingVideo(true); setVideoError(null); setVideoUrl(null); setVideoStatus("pending");
    try { const d = await api.faceSwapGenerateVideo(activeId, brandedPrompt, brandedDuration, videoModel); setVideoJobId(d.job_id); startPolling(d.job_id); }
    catch (err) { setVideoError(getErrorMessage(err)); setVideoStatus(null); setGeneratingVideo(false); }
  };

  const handleReset = () => {
    setTargetFile(null); setTargetPreview(null); setTargetFrameUrl(null); setVideoInfo(null);
    setSourceFile(null); setSourcePreview(null); setResult(null); setGenError(null);
    setSelectedVariant(0);
    setVideoDuration(10); setVideoPrompt(""); setGeneratingVideo(false); setVideoJobId(null);
    setVideoStatus(null); setVideoUrl(null); setVideoError(null); setVideoPhase("hook"); setMotionStyle("lean-in");
    setBrandUrl(""); setBrandedDuration(10); setBrandedPrompt(""); setBrandedPromptBrand("");
    setGeneratingBrandedPrompt(false); setBrandedPromptError(null); setGeneratingMore(false);
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
    if (imagePollingRef.current) { clearInterval(imagePollingRef.current); imagePollingRef.current = null; }
    imageJobIdRef.current = null;
    localStorage.removeItem(ACTIVE_FACE_SWAP_JOB_KEY);
  };

  /* ===================== RENDER ===================== */
  return (
    <div className="space-y-6 max-w-4xl mx-auto">

      {/* ---------- HEADER ---------- */}
      <div className="text-center space-y-1.5 pt-2">
        <h1 className="font-display text-2xl md:text-3xl font-bold tracking-tight">Face Swap</h1>
        <p className="text-sm text-muted-foreground">
          {videoInfo && savedFaceLoaded
            ? "Your video frame and saved face are ready. Hit Generate."
            : videoInfo
            ? "Your video frame is ready. Upload your face to swap."
            : savedFaceLoaded
            ? "Your saved face is loaded. Select a viral video or upload a target."
            : "Select a viral video frame or upload a target, then add your face."}
        </p>
      </div>

      {/* ---------- STEP INDICATOR (minimal) ---------- */}
      <div className="flex items-center justify-center gap-2 py-2" data-testid="face-swap-step-indicator">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full transition-all ${
              result ? "bg-[color:var(--brand-teal)]" : s < currentStep ? "bg-[color:var(--brand-teal)]" : s === currentStep ? "bg-[color:var(--brand-teal)] scale-125" : "bg-border"
            }`} />
            {s < 3 && <div className={`w-8 h-px ${s < currentStep || result ? "bg-[color:var(--brand-teal)]" : "bg-border"}`} />}
          </div>
        ))}
      </div>

      {/* ---------- UPLOAD PHASE ---------- */}
      {!result && (
        <>
          {videoInfo && targetPreview ? (
            /* --- VIDEO FRAME ALREADY SELECTED (from discovery) --- */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Selected frame (locked in, not an upload zone) */}
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <span className="h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold bg-[color:var(--brand-teal)] text-white"><Check className="h-3 w-3" /></span>
                  <span className="text-sm font-semibold">Video Frame Selected</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[color:rgba(99,102,241,0.08)] text-[color:var(--brand-teal-dark)] font-medium flex items-center gap-1"><Film className="h-3 w-3" /> Frame {videoInfo.frameIndex}</span>
                </div>
                <div className="relative">
                  <img src={targetPreview} alt="Selected video frame" className="w-full rounded-xl object-cover aspect-[3/4]" />
                  <button
                    onClick={handleRemoveTarget}
                    className="absolute top-2 right-2 rounded-full bg-black/60 text-white p-1.5 opacity-0 hover:opacity-100 transition-opacity hover:bg-black/80"
                    aria-label="Change target"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                  <div className="absolute bottom-2 left-2 rounded-full bg-[color:var(--brand-teal)] text-white px-2 py-0.5 text-[10px] font-semibold flex items-center gap-1">
                    <Check className="h-2.5 w-2.5" /> From discovery
                  </div>
                </div>
              </div>

              {/* Source face (the only thing user needs to upload) */}
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <span className={`h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold ${sourceFile ? "bg-[color:var(--brand-teal)] text-white" : "bg-[color:var(--brand-coral)] text-white"}`}>{sourceFile ? <Check className="h-3 w-3" /> : "2"}</span>
                  <span className="text-sm font-semibold">Your Face</span>
                  {savedFaceLoaded && <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium flex items-center gap-1"><Save className="h-2.5 w-2.5" /> Saved</span>}
                </div>
                <DropZone onFileSelect={handleSourceSelect} accept="image/jpeg,image/png,image/webp" label="Drop your face photo here" sublabel="Clear, frontal view works best" preview={sourcePreview} onRemove={handleRemoveSource} testId="source" icon={User} />
                {sourceFile && !savedFaceLoaded && (
                  <button onClick={handleSaveFace} className="flex items-center gap-1.5 text-xs text-[color:var(--brand-teal-dark)] hover:underline font-medium" data-testid="save-face-button">
                    <Save className="h-3 w-3" /> Save this face for next time
                  </button>
                )}
                {savedFaceLoaded && (
                  <button onClick={handleRemoveSavedFace} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-red-600 font-medium" data-testid="remove-saved-face-button">
                    <Trash2 className="h-3 w-3" /> Remove saved face
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* --- MANUAL MODE (no video selected, user uploads both) --- */
            <div className="space-y-4">
              {/* Prominent CTA to go to discovery */}
              {!targetFile && (
                <div className="flex items-center gap-3 p-4 rounded-xl border border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.04)]">
                  <Film className="h-5 w-5 text-[color:var(--brand-teal)] shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-medium">No video selected</p>
                    <p className="text-xs text-muted-foreground">Pick a viral video from your niche — that frame becomes your target automatically.</p>
                  </div>
                  <a href="/discover" className="shrink-0">
                    <Button size="sm" className="gap-1.5 rounded-lg bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white" data-testid="go-to-discover-cta">
                      <ArrowRight className="h-3.5 w-3.5" /> Discover Hooks
                    </Button>
                  </a>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Target */}
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <span className={`h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold ${targetFile ? "bg-[color:var(--brand-teal)] text-white" : "bg-muted text-muted-foreground"}`}>1</span>
                  <span className="text-sm font-semibold">Target Image</span>
                </div>
                <DropZone onFileSelect={handleTargetSelect} accept="image/jpeg,image/png,image/webp" label="Drop target image here" sublabel="Or select a video from Discover Hooks" preview={targetPreview} onRemove={handleRemoveTarget} testId="target" icon={ImageIcon} />
              </div>

              {/* Source */}
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <span className={`h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold ${sourceFile ? "bg-[color:var(--brand-teal)] text-white" : targetFile ? "bg-[color:var(--brand-teal)] text-white" : "bg-muted text-muted-foreground"}`}>2</span>
                  <span className={`text-sm font-semibold ${!targetFile ? "text-muted-foreground" : ""}`}>Your Face</span>
                  {savedFaceLoaded && <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium flex items-center gap-1"><Save className="h-2.5 w-2.5" /> Saved</span>}
                </div>
                <DropZone onFileSelect={handleSourceSelect} accept="image/jpeg,image/png,image/webp" label="Drop your face photo here" sublabel="Clear, frontal view works best" preview={sourcePreview} onRemove={handleRemoveSource} testId="source" icon={User} />
                {sourceFile && !savedFaceLoaded && (
                  <button onClick={handleSaveFace} className="flex items-center gap-1.5 text-xs text-[color:var(--brand-teal-dark)] hover:underline font-medium" data-testid="save-face-button">
                    <Save className="h-3 w-3" /> Save this face for next time
                  </button>
                )}
                {savedFaceLoaded && (
                  <button onClick={handleRemoveSavedFace} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-red-600 font-medium" data-testid="remove-saved-face-button">
                    <Trash2 className="h-3 w-3" /> Remove saved face
                  </button>
                )}
              </div>
              </div>
            </div>
          )}

          {/* Generate button */}
          {targetFile && sourceFile && (
            <div className="text-center pt-2">
              {generating ? (
                <Card className="p-5 rounded-2xl max-w-md mx-auto">
                  <GenerationProgress stages={["Analyzing faces", "Matching lighting", "Generating image", "Final blending"]} active={true} />
                </Card>
              ) : (
                <Button onClick={handleGenerate} size="lg" className="gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white px-8 py-5 text-sm font-semibold shadow-md" data-testid="generate-swap-button">
                  <Sparkles className="h-4 w-4" /> Generate Face Swap
                </Button>
              )}
            </div>
          )}

          {genError && (
            <Alert variant="destructive" className="rounded-xl max-w-md mx-auto" data-testid="face-swap-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription className="flex items-center justify-between">
                <span className="text-sm">{genError}</span>
                <Button size="sm" variant="ghost" onClick={handleGenerate} className="gap-1 shrink-0"><RotateCcw className="h-3 w-3" /> Retry</Button>
              </AlertDescription>
            </Alert>
          )}
        </>
      )}

      {/* ---------- RESULT PHASE ---------- */}
      {result && (
        <div className="space-y-5">

          {/* Result comparison */}
          <Card className="rounded-2xl overflow-hidden border-[color:var(--brand-teal)]" data-testid="face-swap-result">
            <div className="grid grid-cols-3 gap-px bg-border">
              <div className="bg-card p-3 text-center">
                <p className="text-[10px] font-medium text-muted-foreground mb-1.5">Target</p>
                <img src={targetPreview} alt="Target" className="w-full rounded-lg object-cover aspect-[3/4]" />
              </div>
              <div className="bg-card p-3 text-center">
                <p className="text-[10px] font-medium text-muted-foreground mb-1.5">Your Face</p>
                <img src={sourcePreview} alt="Source" className="w-full rounded-lg object-cover aspect-[3/4]" />
              </div>
              <div className="bg-[color:rgba(99,102,241,0.02)] p-3 text-center">
                <p className="text-[10px] font-medium text-[color:var(--brand-teal-dark)] mb-1.5 flex items-center justify-center gap-1"><Sparkles className="h-2.5 w-2.5" /> Result</p>
                <img src={mediaUrl((result.variants && result.variants[selectedVariant]?.image_url) || result.generated_image_url)} alt="Result" className="w-full rounded-lg object-cover aspect-[3/4] ring-1 ring-[color:var(--brand-teal)]" data-testid="face-swap-generated-image" />
              </div>
            </div>
          </Card>

          {/* Variant picker — shown when multiple variants are available */}
          {result.variants && result.variants.length > 1 && (
            <Card className="rounded-2xl p-4 space-y-3" data-testid="variant-picker">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-[color:var(--brand-teal)]" />
                  Pick your best variant
                </p>
                <span className="text-[10px] text-muted-foreground">{selectedVariant + 1} of {result.variants.length} selected</span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {result.variants.map((variant, idx) => (
                  <button
                    key={variant.id}
                    onClick={() => setSelectedVariant(idx)}
                    className={`relative rounded-xl overflow-hidden border-2 transition-all ${
                      selectedVariant === idx
                        ? "border-[color:var(--brand-teal)] ring-2 ring-[color:rgba(99,102,241,0.2)] scale-[1.02]"
                        : "border-border hover:border-[color:rgba(99,102,241,0.4)] hover:scale-[1.01]"
                    }`}
                    data-testid={`variant-option-${idx}`}
                  >
                    <img
                      src={mediaUrl(variant.image_url)}
                      alt={`Variant ${idx + 1}`}
                      className="w-full object-cover aspect-[3/4]"
                    />
                    {selectedVariant === idx && (
                      <div className="absolute top-1.5 right-1.5 h-5 w-5 rounded-full bg-[color:var(--brand-teal)] text-white flex items-center justify-center shadow-md">
                        <Check className="h-3 w-3" />
                      </div>
                    )}
                    <div className="absolute bottom-1.5 left-1.5">
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                        selectedVariant === idx ? "bg-[color:var(--brand-teal)] text-white" : "bg-black/60 text-white"
                      }`}>
                        {idx + 1}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </Card>
          )}

          {/* Generate more variants button */}
          {targetFile && sourceFile && !targetFile.restored && !sourceFile.restored && (!result.variants || result.variants.length < 4) && (
            <Button
              onClick={handleGenerateMoreVariants}
              disabled={generatingMore}
              variant="outline"
              className="w-full gap-1.5 rounded-xl text-sm"
              data-testid="generate-more-variants-button"
            >
              {generatingMore ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              {generatingMore ? "Generating alternatives..." : "Generate Alternatives"}
            </Button>
          )}

          {/* Quick actions */}
          <div className="flex gap-2">
            <a href={mediaUrl((result.variants && result.variants[selectedVariant]?.image_url) || result.generated_image_url)} download target="_blank" rel="noreferrer" className="flex-1">
              <Button variant="outline" className="w-full gap-1.5 rounded-xl text-sm" data-testid="download-swap-button"><Download className="h-3.5 w-3.5" /> Download</Button>
            </a>
            <Button onClick={handleReset} variant="ghost" className="gap-1.5 rounded-xl text-sm text-muted-foreground" data-testid="new-swap-button"><RotateCcw className="h-3.5 w-3.5" /> Reset</Button>
          </div>

          {/* ---------- VIDEO GENERATION (Hook → Extend) ---------- */}
          <Card className="rounded-2xl p-5 space-y-4" data-testid="phase2-video-section">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-full bg-[color:var(--brand-coral)] text-white flex items-center justify-center">
                <Clapperboard className="h-4 w-4" />
              </div>
              <div>
                <h2 className="font-display font-semibold text-base">Create Video</h2>
                <p className="text-xs text-muted-foreground">Step 1: Silent 5s hook → Step 2: Extend with brand message</p>
              </div>
            </div>

            {/* Hook video complete — show it + offer extend */}
            {videoUrl && videoPhase === "hook" && (
              <div className="space-y-4" data-testid="hook-video-result">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[color:var(--brand-teal)] text-white">Step 1</span>
                    <span className="text-xs font-medium">5s Hook Video (silent)</span>
                    <Check className="h-3.5 w-3.5 text-green-500" />
                  </div>
                  <video src={videoUrl} controls autoPlay loop muted className="w-full rounded-xl" data-testid="hook-video-player" />
                </div>
                <div className="flex gap-2">
                  <a href={videoUrl} download target="_blank" rel="noreferrer" className="flex-1">
                    <Button variant="outline" className="w-full gap-1.5 rounded-xl text-sm" data-testid="download-hook-button"><Download className="h-3.5 w-3.5" /> Download Hook</Button>
                  </a>
                  <Button onClick={handleReset} variant="ghost" className="gap-1.5 rounded-xl text-sm text-muted-foreground"><RotateCcw className="h-3.5 w-3.5" /> Reset</Button>
                </div>

                {/* Extend section */}
                <div className="pt-3 border-t border-border space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[color:var(--brand-coral)] text-white">Step 2</span>
                    <span className="text-xs font-medium">Extend with brand message</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Now add a longer continuation with your brand message, voiceover, and CTA.
                    {brandProfile && <span className="text-[color:var(--brand-teal)]"> Brand profile detected.</span>}
                  </p>
                  <div className="flex gap-2">
                    <Input value={brandUrl} onChange={(e) => setBrandUrl(e.target.value)} placeholder="https://yourbrand.com" className="flex-1 text-sm" data-testid="extend-brand-url-input" />
                    <div className="w-20">
                      <Input type="number" min={5} max={15} value={brandedDuration} onChange={(e) => setBrandedDuration(Math.max(5, Math.min(15, Number(e.target.value) || 10)))} className="text-sm text-center" />
                      <p className="text-[9px] text-muted-foreground text-center mt-0.5">{brandedDuration}s</p>
                    </div>
                  </div>
                  {/* Model selector */}
                  <div className="flex gap-1 rounded-lg bg-muted/50 p-0.5" data-testid="extend-model-selector">
                    {[
                      { key: "seedance-2.0", label: "Seedance 2.0", sub: "Best quality" },
                      { key: "wan-2.7", label: "Wan 2.7", sub: "Style preservation" },
                      { key: "seedance-2.0-fast", label: "Fast", sub: "Quick & cheap" },
                    ].map((m) => (
                      <button key={m.key} onClick={() => setVideoModel(m.key)}
                        className={`flex-1 text-center py-1.5 px-2 rounded-md transition-all ${videoModel === m.key ? "bg-secondary shadow-sm" : "hover:bg-card/50"}`}>
                        <span className={`text-[11px] font-semibold block ${videoModel === m.key ? "text-foreground" : "text-muted-foreground"}`}>{m.label}</span>
                        <span className="text-[9px] text-muted-foreground">{m.sub}</span>
                      </button>
                    ))}
                  </div>
                  <Button onClick={handleExtendVideo} disabled={generatingVideo} className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white" data-testid="extend-video-button">
                    <Film className="h-4 w-4" /> Extend to {brandedDuration}s Branded Video
                  </Button>
                </div>
              </div>
            )}

            {/* Extended video complete */}
            {videoUrl && videoPhase === "extend" && (
              <div className="space-y-3" data-testid="extended-video-result">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-green-600 text-white">Complete</span>
                  <span className="text-xs font-medium">Extended branded video ready</span>
                </div>
                <video src={videoUrl} controls autoPlay loop className="w-full rounded-xl" data-testid="extended-video-player" />
                <div className="flex gap-2">
                  <a href={videoUrl} download target="_blank" rel="noreferrer" className="flex-1">
                    <Button className="w-full gap-1.5 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white text-sm" data-testid="download-extended-button"><Download className="h-3.5 w-3.5" /> Download Video</Button>
                  </a>
                  <Button onClick={handleReset} variant="outline" className="gap-1.5 rounded-xl text-sm"><RotateCcw className="h-3.5 w-3.5" /> New</Button>
                </div>
              </div>
            )}

            {/* Video in progress */}
            {!videoUrl && (videoStatus === "pending" || videoStatus === "in_progress") && (
              <div className="flex items-center gap-3 p-4 rounded-xl bg-muted/40">
                <Loader2 className="h-5 w-5 animate-spin text-[color:var(--brand-teal)] shrink-0" />
                <div>
                  <p className="text-sm font-medium">{videoStatus === "pending" ? "Queued..." : "Generating..."}</p>
                  <p className="text-xs text-muted-foreground">
                    {videoPhase === "hook" ? "Creating 5s silent hook (30s-2min)" : "Extending video with brand message (1-3min)"}
                  </p>
                </div>
              </div>
            )}

            {videoError && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 text-red-400 text-xs">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1">{videoError}</span>
                <Button size="sm" variant="ghost" onClick={handleGenerateHook} className="text-red-400 h-auto py-1 px-2"><RotateCcw className="h-3 w-3" /></Button>
              </div>
            )}

            {/* Initial state — generate hook button */}
            {!videoUrl && !videoStatus && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[color:var(--brand-teal)] text-white">Step 1</span>
                    <span className="text-xs font-medium">Generate 5s Hook (silent, movement only)</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    A short, silent video with attention-grabbing movement — no voice, no text. Designed to stop the scroll in the first 2-3 seconds.
                  </p>
                </div>

                {/* Motion style selector */}
                <div className="space-y-1.5">
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Motion style</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                    {[
                      { key: "lean-in", label: "Lean In", desc: "Confident approach" },
                      { key: "turn", label: "Dramatic Turn", desc: "Profile to camera" },
                      { key: "gesture", label: "Gesture", desc: "Hand signal / reveal" },
                      { key: "intrigue", label: "Intrigue", desc: "Raised brow, half-smile" },
                      { key: "stop-motion", label: "Stop Motion", desc: "Sudden pose change" },
                    ].map((m) => (
                      <button key={m.key} onClick={() => setMotionStyle(m.key)}
                        className={`text-left p-2 rounded-lg border transition-all ${motionStyle === m.key ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.05)]" : "border-border hover:border-[color:rgba(99,102,241,0.3)]"}`}
                        data-testid={`motion-${m.key}`}>
                        <span className={`text-[11px] font-semibold block ${motionStyle === m.key ? "text-[color:var(--brand-teal)]" : "text-foreground"}`}>{m.label}</span>
                        <span className="text-[9px] text-muted-foreground">{m.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Model selector */}
                <div className="flex gap-1 rounded-lg bg-muted/50 p-0.5" data-testid="hook-model-selector">
                  {[
                    { key: "seedance-2.0", label: "Seedance 2.0", sub: "Best quality" },
                    { key: "wan-2.7", label: "Wan 2.7", sub: "Style preservation" },
                    { key: "seedance-2.0-fast", label: "Fast", sub: "Quick & cheap" },
                  ].map((m) => (
                    <button key={m.key} onClick={() => setVideoModel(m.key)}
                      className={`flex-1 text-center py-1.5 px-2 rounded-md transition-all ${videoModel === m.key ? "bg-secondary shadow-sm" : "hover:bg-card/50"}`}
                      data-testid={`model-${m.key}`}>
                      <span className={`text-[11px] font-semibold block ${videoModel === m.key ? "text-foreground" : "text-muted-foreground"}`}>{m.label}</span>
                      <span className="text-[9px] text-muted-foreground">{m.sub}</span>
                    </button>
                  ))}
                </div>

                <Button onClick={handleGenerateHook} disabled={generatingVideo} className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white" data-testid="generate-hook-button">
                  <Clapperboard className="h-4 w-4" /> Generate 5s Hook Video
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
