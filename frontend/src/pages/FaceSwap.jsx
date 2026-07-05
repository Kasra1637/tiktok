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
} from "lucide-react";
import { toast } from "sonner";

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
          isDragging ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.04)] scale-[1.01]" : "border-border hover:border-[color:rgba(99,102,241,0.4)] bg-white/50 hover:bg-white/80"
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

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);
  const [result, setResult] = useState(null);

  // Video state
  const [videoDuration, setVideoDuration] = useState(10);
  const [videoPrompt, setVideoPrompt] = useState("");
  const [generatingVideo, setGeneratingVideo] = useState(false);
  const [videoJobId, setVideoJobId] = useState(null);
  const [videoStatus, setVideoStatus] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoError, setVideoError] = useState(null);
  const pollingRef = useRef(null);

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

  // Cleanup polling
  useEffect(() => () => { if (pollingRef.current) clearInterval(pollingRef.current); }, []);

  const currentStep = !targetFile ? 1 : !sourceFile ? 2 : 3;

  /* --- Handlers --- */
  const handleTargetSelect = (file) => { setTargetFile(file); setTargetPreview(URL.createObjectURL(file)); setTargetFrameUrl(null); setVideoInfo(null); setResult(null); setGenError(null); };
  const handleSourceSelect = (file) => { setSourceFile(file); setSourcePreview(URL.createObjectURL(file)); setResult(null); setGenError(null); };
  const handleRemoveTarget = () => { setTargetFile(null); setTargetPreview(null); setTargetFrameUrl(null); setVideoInfo(null); setResult(null); };
  const handleRemoveSource = () => { setSourceFile(null); setSourcePreview(null); setResult(null); };

  const handleGenerate = async () => {
    if (!targetFile || !sourceFile) { toast.error("Upload both images first."); return; }
    setGenerating(true); setGenError(null); setResult(null);
    try {
      const formData = new FormData();
      formData.append("source_face", sourceFile);
      if (targetFrameUrl) formData.append("target_frame_url", targetFrameUrl);
      else formData.append("target_image", targetFile);
      const data = await api.faceSwap(formData);
      setResult(data);
      toast.success("Face swap complete!");
    } catch (err) { setGenError(getErrorMessage(err)); }
    finally { setGenerating(false); }
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

  const handleQuickPreview = async () => {
    if (!result?.id) return;
    setVideoDuration(5); setVideoPrompt(""); setGeneratingVideo(true); setVideoError(null); setVideoUrl(null); setVideoStatus("pending");
    try { const d = await api.faceSwapGenerateVideo(result.id, "", 5); setVideoJobId(d.job_id); startPolling(d.job_id); }
    catch (err) { setVideoError(getErrorMessage(err)); setVideoStatus(null); setGeneratingVideo(false); }
  };

  const handleGenerateBrandedPrompt = async () => {
    if (!result?.id) return;
    if (!brandUrl.trim() && !brandProfile) { toast.error("Enter your brand URL."); return; }
    setGeneratingBrandedPrompt(true); setBrandedPromptError(null); setBrandedPrompt("");
    try {
      const d = await api.faceSwapBrandedPrompt(result.id, brandUrl.trim(), videoInfo?.videoId || "", brandedDuration);
      setBrandedPrompt(d.video_prompt || ""); setBrandedPromptBrand(d.brand_name || "");
      toast.success("Prompt generated!");
    } catch (err) { setBrandedPromptError(getErrorMessage(err)); }
    finally { setGeneratingBrandedPrompt(false); }
  };

  const handleGenerateBrandedVideo = async () => {
    if (!result?.id || !brandedPrompt) return;
    setVideoDuration(brandedDuration); setGeneratingVideo(true); setVideoError(null); setVideoUrl(null); setVideoStatus("pending");
    try { const d = await api.faceSwapGenerateVideo(result.id, brandedPrompt, brandedDuration); setVideoJobId(d.job_id); startPolling(d.job_id); }
    catch (err) { setVideoError(getErrorMessage(err)); setVideoStatus(null); setGeneratingVideo(false); }
  };

  const handleReset = () => {
    setTargetFile(null); setTargetPreview(null); setTargetFrameUrl(null); setVideoInfo(null);
    setSourceFile(null); setSourcePreview(null); setResult(null); setGenError(null);
    setVideoDuration(10); setVideoPrompt(""); setGeneratingVideo(false); setVideoJobId(null);
    setVideoStatus(null); setVideoUrl(null); setVideoError(null);
    setBrandUrl(""); setBrandedDuration(15); setBrandedPrompt(""); setBrandedPromptBrand("");
    setGeneratingBrandedPrompt(false); setBrandedPromptError(null);
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
  };

  /* ===================== RENDER ===================== */
  return (
    <div className="space-y-6 max-w-4xl mx-auto">

      {/* ---------- HEADER ---------- */}
      <div className="text-center space-y-1.5 pt-2">
        <h1 className="font-display text-2xl md:text-3xl font-bold tracking-tight">Face Swap</h1>
        <p className="text-sm text-muted-foreground">
          {videoInfo ? "Your video frame is ready. Upload your face to swap." : "Select a viral video frame or upload a target, then add your face."}
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
                  <span className="text-sm font-semibold">Upload Your Face</span>
                </div>
                <DropZone onFileSelect={handleSourceSelect} accept="image/jpeg,image/png,image/webp" label="Drop your face photo here" sublabel="Clear, frontal view works best" preview={sourcePreview} onRemove={handleRemoveSource} testId="source" icon={User} />
              </div>
            </div>
          ) : (
            /* --- MANUAL MODE (no video selected, user uploads both) --- */
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
                </div>
                <DropZone onFileSelect={handleSourceSelect} accept="image/jpeg,image/png,image/webp" label="Drop your face photo here" sublabel="Clear, frontal view works best" preview={sourcePreview} onRemove={handleRemoveSource} testId="source" icon={User} />
              </div>
            </div>
          )}

          {/* Generate button */}
          {targetFile && sourceFile && (
            <div className="text-center pt-2">
              {generating ? (
                <Card className="p-5 rounded-2xl max-w-md mx-auto">
                  <GenerationProgress stages={["Analyzing faces", "Matching lighting", "Generating swap", "Final blending"]} active={true} />
                </Card>
              ) : (
                <Button onClick={handleGenerate} size="lg" className="gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white px-8 py-5 text-sm font-semibold shadow-md" data-testid="generate-swap-button">
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
              <div className="bg-white p-3 text-center">
                <p className="text-[10px] font-medium text-muted-foreground mb-1.5">Target</p>
                <img src={targetPreview} alt="Target" className="w-full rounded-lg object-cover aspect-[3/4]" />
              </div>
              <div className="bg-white p-3 text-center">
                <p className="text-[10px] font-medium text-muted-foreground mb-1.5">Your Face</p>
                <img src={sourcePreview} alt="Source" className="w-full rounded-lg object-cover aspect-[3/4]" />
              </div>
              <div className="bg-[color:rgba(99,102,241,0.02)] p-3 text-center">
                <p className="text-[10px] font-medium text-[color:var(--brand-teal-dark)] mb-1.5 flex items-center justify-center gap-1"><Sparkles className="h-2.5 w-2.5" /> Result</p>
                <img src={mediaUrl(result.generated_image_url)} alt="Result" className="w-full rounded-lg object-cover aspect-[3/4] ring-1 ring-[color:var(--brand-teal)]" data-testid="face-swap-generated-image" />
              </div>
            </div>
          </Card>

          {/* Quick actions */}
          <div className="flex gap-2">
            <a href={mediaUrl(result.generated_image_url)} download target="_blank" rel="noreferrer" className="flex-1">
              <Button variant="outline" className="w-full gap-1.5 rounded-xl text-sm" data-testid="download-swap-button"><Download className="h-3.5 w-3.5" /> Download</Button>
            </a>
            <Button onClick={handleReset} variant="ghost" className="gap-1.5 rounded-xl text-sm text-muted-foreground" data-testid="new-swap-button"><RotateCcw className="h-3.5 w-3.5" /> Reset</Button>
          </div>

          {/* ---------- VIDEO GENERATION ---------- */}
          <Card className="rounded-2xl p-5 space-y-4" data-testid="phase2-video-section">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-full bg-[color:var(--brand-coral)] text-white flex items-center justify-center">
                <Clapperboard className="h-4 w-4" />
              </div>
              <div>
                <h2 className="font-display font-semibold text-base">Create Video</h2>
                <p className="text-xs text-muted-foreground">Turn your swapped image into an animated video</p>
              </div>
            </div>

            {/* Video complete */}
            {videoUrl && (
              <div className="space-y-3" data-testid="video-result">
                <video src={videoUrl} controls autoPlay loop className="w-full rounded-xl" data-testid="generated-video-player" />
                <div className="flex gap-2">
                  <a href={videoUrl} download target="_blank" rel="noreferrer" className="flex-1">
                    <Button className="w-full gap-1.5 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white text-sm" data-testid="download-video-button"><Download className="h-3.5 w-3.5" /> Download Video</Button>
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
                  <p className="text-xs text-muted-foreground">Usually takes 30s to 2 min</p>
                </div>
              </div>
            )}

            {videoError && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 text-red-700 text-xs">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1">{videoError}</span>
                <Button size="sm" variant="ghost" onClick={handleQuickPreview} className="text-red-700 h-auto py-1 px-2"><RotateCcw className="h-3 w-3" /></Button>
              </div>
            )}

            {/* Mode selector — only when no video in progress */}
            {!videoUrl && !videoStatus && (
              <div className="space-y-4">
                {/* Tab buttons */}
                <div className="flex rounded-lg bg-muted p-0.5">
                  <button onClick={() => setVideoMode("branded")} className={`flex-1 text-xs font-semibold py-2 px-3 rounded-md transition-all ${videoMode === "branded" ? "bg-white shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                    Branded Video
                  </button>
                  <button onClick={() => setVideoMode("preview")} className={`flex-1 text-xs font-semibold py-2 px-3 rounded-md transition-all ${videoMode === "preview" ? "bg-white shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
                    Quick Preview
                  </button>
                </div>

                {/* Quick Preview tab */}
                {videoMode === "preview" && (
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground">Generate a 5-second video with natural motion to see how your face looks animated.</p>
                    <Button onClick={handleQuickPreview} disabled={generatingVideo} variant="secondary" className="w-full gap-2 rounded-xl" data-testid="quick-preview-button">
                      <Play className="h-4 w-4" /> Generate 5s Preview
                    </Button>
                  </div>
                )}

                {/* Branded Video tab */}
                {videoMode === "branded" && (
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground">
                      Enter your website — we'll generate a custom video prompt for your brand, then animate it.
                      {brandProfile && <span className="text-[color:var(--brand-teal)]"> Saved brand profile detected.</span>}
                    </p>

                    <div className="flex gap-2">
                      <Input value={brandUrl} onChange={(e) => setBrandUrl(e.target.value)} placeholder="https://yourbrand.com" className="flex-1 text-sm" data-testid="brand-url-input" />
                      <div className="w-20">
                        <Input type="number" min={5} max={30} value={brandedDuration} onChange={(e) => setBrandedDuration(Math.max(5, Math.min(30, Number(e.target.value) || 15)))} className="text-sm text-center" data-testid="branded-duration-input" />
                        <p className="text-[9px] text-muted-foreground text-center mt-0.5">{brandedDuration}s</p>
                      </div>
                    </div>

                    {brandedPrompt && (
                      <Textarea value={brandedPrompt} onChange={(e) => setBrandedPrompt(e.target.value)} className="min-h-[80px] text-xs" data-testid="branded-prompt-textarea" placeholder="Your AI-generated video prompt..." />
                    )}

                    {brandedPromptError && <p className="text-xs text-red-600">{brandedPromptError}</p>}

                    {generatingBrandedPrompt ? (
                      <div className="flex items-center gap-2 py-2">
                        <Loader2 className="h-4 w-4 animate-spin text-[color:var(--brand-coral)]" />
                        <span className="text-xs">Writing your branded prompt...</span>
                      </div>
                    ) : !brandedPrompt ? (
                      <Button onClick={handleGenerateBrandedPrompt} disabled={generatingBrandedPrompt} className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white" data-testid="generate-branded-prompt-button">
                        <Wand2 className="h-4 w-4" /> Write Video Prompt
                      </Button>
                    ) : (
                      <Button onClick={handleGenerateBrandedVideo} disabled={generatingVideo} className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white" data-testid="generate-branded-video-button">
                        <Clapperboard className="h-4 w-4" /> Generate {brandedDuration}s Video
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
