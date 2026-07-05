import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Skeleton } from "../components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import GenerationProgress from "../components/GenerationProgress";
import Stepper from "../components/Stepper";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { ArrowLeft, Wand2, Clapperboard, AlertTriangle, RotateCcw, Clock, Film, Camera, Eye, Users, MapPinned, Megaphone, CheckCircle2, Globe, Sparkles, ListChecks } from "lucide-react";
import { toast } from "sonner";

const PROMPT_STAGES = ["Reading the hook analysis", "Weaving in your brand context", "Writing the video prompt"];

const BREAKDOWN_SECTIONS = [
  { key: "content", label: "Content", icon: Film },
  { key: "camera_angle", label: "Camera Angle", icon: Camera },
  { key: "view_position", label: "View Position", icon: Eye },
  { key: "character_behavior", label: "Character Behavior", icon: Users },
  { key: "scene_details", label: "Scene Details", icon: MapPinned },
  { key: "brand_narrative", label: "Brand Narrative", icon: Megaphone },
];

export default function GenerateVideo() {
  const { customizationId } = useParams();
  const navigate = useNavigate();

  const [customization, setCustomization] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const [brandName, setBrandName] = useState("");
  const [brandGoal, setBrandGoal] = useState("");
  const [brandDetails, setBrandDetails] = useState("");
  const [duration, setDuration] = useState(30);

  // Brand website analysis: fetches the brand's site and derives structured
  // context (overview, USPs, voice/tone, target audience). These fields
  // remain manually editable regardless of whether analysis was run.
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [analyzingWebsite, setAnalyzingWebsite] = useState(false);
  const [websiteError, setWebsiteError] = useState(null);
  const [websiteAnalyzed, setWebsiteAnalyzed] = useState(false);
  const [brandOverview, setBrandOverview] = useState("");
  const [usps, setUsps] = useState("");
  const [brandVoiceTone, setBrandVoiceTone] = useState("");
  const [targetAudience, setTargetAudience] = useState("");

  const [generatingPrompt, setGeneratingPrompt] = useState(false);
  const [promptError, setPromptError] = useState(null);
  const [job, setJob] = useState(null);
  const [editedPrompt, setEditedPrompt] = useState("");

  const [submittingVideo, setSubmittingVideo] = useState(false);
  const [videoJob, setVideoJob] = useState(null);

  useEffect(() => {
    api
      .getCustomization(customizationId)
      .then(setCustomization)
      .catch((err) => setLoadError(getErrorMessage(err)));
  }, [customizationId]);

  const handleAnalyzeWebsite = async () => {
    if (!websiteUrl.trim()) return;
    setAnalyzingWebsite(true);
    setWebsiteError(null);
    try {
      const data = await api.analyzeBrandWebsite(websiteUrl.trim());
      if (data.brand_name && !brandName.trim()) setBrandName(data.brand_name);
      setBrandOverview(data.brand_overview || "");
      setUsps((data.unique_selling_propositions || []).join("\n"));
      setBrandVoiceTone(data.brand_voice_tone || "");
      setTargetAudience(data.target_audience || "");
      setWebsiteAnalyzed(true);
      toast.success("Website analyzed — review the fields below before generating your prompt.");
    } catch (err) {
      setWebsiteError(getErrorMessage(err));
    } finally {
      setAnalyzingWebsite(false);
    }
  };

  const handleGeneratePrompt = async () => {
    setGeneratingPrompt(true);
    setPromptError(null);
    setJob(null);
    setVideoJob(null);
    try {
      const data = await api.generateVideoPrompt(customizationId, {
        brand_name: brandName,
        brand_goal: brandGoal,
        brand_details: brandDetails,
        duration_seconds: Number(duration) || 30,
        website_url: websiteUrl,
        brand_overview: brandOverview,
        unique_selling_propositions: usps
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        brand_voice_tone: brandVoiceTone,
        target_audience: targetAudience,
      });
      setJob(data);
      setEditedPrompt(data.full_prompt_text || "");
    } catch (err) {
      setPromptError(getErrorMessage(err));
    } finally {
      setGeneratingPrompt(false);
    }
  };

  const handleGenerateVideo = async () => {
    if (!job) return;
    setSubmittingVideo(true);
    try {
      const imageIds = (customization?.generated_images || []).map((i) => i.id);
      const data = await api.generateVideo(job.id, {
        image_ids: imageIds,
        edited_prompt: editedPrompt,
        duration_seconds: Number(duration) || 30,
      });
      setVideoJob(data);
      toast.success("Video brief saved! Ready for video generation once a provider is connected.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSubmittingVideo(false);
    }
  };

  if (loadError) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Alert variant="destructive" className="rounded-2xl">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load this customization</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
        <Button onClick={() => navigate("/")} className="gap-1.5">
          <ArrowLeft className="h-4 w-4" /> Back to feed
        </Button>
      </div>
    );
  }

  if (!customization) {
    return (
      <div className="space-y-6" data-testid="generate-video-loading">
        <Stepper current="video" />
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-full max-w-2xl" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
          <Card className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-4 h-fit">
            <div className="flex gap-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="w-16 h-20 rounded-lg shrink-0" />
              ))}
            </div>
            <Skeleton className="h-9 w-full rounded-md" />
            <Skeleton className="h-9 w-full rounded-md" />
            <Skeleton className="h-24 w-full rounded-md" />
            <Skeleton className="h-10 w-full rounded-xl" />
          </Card>
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Stepper current="video" />
      <Button
        variant="ghost"
        onClick={() => navigate(`/customize/${customization.video_id}`)}
        className="gap-1.5 -ml-2"
        data-testid="back-to-customize-button"
      >
        <ArrowLeft className="h-4 w-4" /> Back to face swap
      </Button>

      <div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight">Generate your video</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl">
          We'll auto-write a video prompt from the original hook's content, camera angle, view position, character
          behavior, and scene details — then tailor the rest of the video to your brand.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
        <Card className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-4 h-fit">
          <div className="flex gap-2 overflow-x-auto pb-1" data-testid="reference-images-row">
            {(customization.generated_images || []).map((img) => (
              <img
                key={img.id}
                src={mediaUrl(img.image_url)}
                alt="Face-swapped reference"
                className="w-16 h-20 object-cover rounded-lg border border-border shrink-0"
              />
            ))}
          </div>

          <div className="space-y-2 rounded-xl border border-dashed border-border p-3 bg-[color:rgba(13,148,136,0.04)]">
            <label className="text-sm font-medium flex items-center gap-1.5">
              <Globe className="h-3.5 w-3.5" /> Brand website (optional)
            </label>
            <p className="text-xs text-muted-foreground">
              Paste your brand's website and we'll auto-fill the overview, USPs, voice/tone, and
              audience below — you can edit anything before generating the prompt.
            </p>
            <div className="flex items-center gap-2">
              <Input
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                placeholder="https://yourbrand.com"
                data-testid="brand-website-input"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAnalyzeWebsite();
                  }
                }}
              />
              <Button
                type="button"
                onClick={handleAnalyzeWebsite}
                disabled={analyzingWebsite || !websiteUrl.trim()}
                size="sm"
                className="shrink-0 gap-1.5 bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
                data-testid="analyze-website-button"
              >
                <Sparkles className={`h-3.5 w-3.5 ${analyzingWebsite ? "animate-pulse" : ""}`} />
                {analyzingWebsite ? "Analyzing..." : "Analyze"}
              </Button>
            </div>
            {websiteError && (
              <p className="text-xs text-destructive" data-testid="website-error-text">
                {websiteError}
              </p>
            )}
            {websiteAnalyzed && !websiteError && (
              <p className="text-xs text-[color:var(--brand-teal-dark)] flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Fields below were pre-filled from your website. Review and edit as needed.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Brand name</label>
            <Input
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="e.g. Voxel — Voice Journaling App"
              data-testid="brand-name-input"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Brand goal</label>
            <Input
              value={brandGoal}
              onChange={(e) => setBrandGoal(e.target.value)}
              placeholder="e.g. Drive app installs"
              data-testid="brand-goal-input"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Brand details</label>
            <Textarea
              value={brandDetails}
              onChange={(e) => setBrandDetails(e.target.value)}
              placeholder="What does the brand offer? What should the video communicate?"
              className="min-h-[90px]"
              data-testid="brand-details-textarea"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Brand overview</label>
            <Textarea
              value={brandOverview}
              onChange={(e) => setBrandOverview(e.target.value)}
              placeholder="What does the brand do, who does it serve, and what does it sell? (auto-filled by website analysis)"
              className="min-h-[70px]"
              data-testid="brand-overview-textarea"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-1.5">
              <ListChecks className="h-3.5 w-3.5" /> Unique selling propositions (one per line)
            </label>
            <Textarea
              value={usps}
              onChange={(e) => setUsps(e.target.value)}
              placeholder={"e.g.\nOnly app with offline voice transcription\n7-day free trial, no card required"}
              className="min-h-[70px]"
              data-testid="brand-usps-textarea"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Brand voice &amp; tone</label>
            <Input
              value={brandVoiceTone}
              onChange={(e) => setBrandVoiceTone(e.target.value)}
              placeholder="e.g. playful and irreverent, premium and minimal"
              data-testid="brand-voice-tone-input"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Target audience</label>
            <Input
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="e.g. busy working parents in their 30s-40s"
              data-testid="target-audience-input"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" /> Target duration (seconds, max 30)
            </label>
            <Input
              type="number"
              min={5}
              max={30}
              value={duration}
              onChange={(e) => setDuration(Math.max(5, Math.min(30, Number(e.target.value) || 30)))}
              data-testid="duration-input"
            />
          </div>

          <Button
            onClick={handleGeneratePrompt}
            disabled={generatingPrompt}
            className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#EA580C] text-white"
            data-testid="generate-prompt-button"
          >
            <Wand2 className="h-4 w-4" /> {generatingPrompt ? "Writing prompt..." : "Generate Video Prompt"}
          </Button>
        </Card>

        <div className="space-y-6">
          {generatingPrompt && (
            <Card className="p-6 rounded-2xl border-border shadow-[var(--shadow-soft)]">
              <h3 className="font-display font-semibold mb-3 flex items-center gap-2">
                <Clapperboard className="h-4 w-4" /> Writing your video prompt...
              </h3>
              <GenerationProgress stages={PROMPT_STAGES} active={true} />
            </Card>
          )}

          {promptError && (
            <Alert variant="destructive" className="rounded-2xl" data-testid="prompt-error-alert">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Prompt generation failed</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{promptError}</p>
                <Button size="sm" onClick={handleGeneratePrompt} className="gap-1.5" data-testid="retry-prompt-button">
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {job && !generatingPrompt && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="prompt-breakdown">
                {BREAKDOWN_SECTIONS.map(({ key, label, icon: Icon }) => (
                  <Card key={key} className="p-4 rounded-2xl border-border shadow-[var(--shadow-soft)]">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Icon className="h-4 w-4 text-[color:var(--brand-teal)]" />
                      <h4 className="text-sm font-semibold">{label}</h4>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed line-clamp-4">
                      {job.prompt_breakdown?.[key]}
                    </p>
                  </Card>
                ))}
              </div>

              <Card className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold">Full video prompt (editable)</h4>
                  <Badge variant="secondary" className="rounded-full text-[10px]">
                    ~{job.target_duration_seconds}s
                  </Badge>
                </div>
                <Textarea
                  value={editedPrompt}
                  onChange={(e) => setEditedPrompt(e.target.value)}
                  className="min-h-[180px] font-mono text-xs"
                  data-testid="full-prompt-textarea"
                />
              </Card>

              {!videoJob ? (
                <Button
                  onClick={handleGenerateVideo}
                  disabled={submittingVideo}
                  className="w-full gap-2 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
                  data-testid="generate-video-button"
                >
                  <Clapperboard className="h-4 w-4" /> {submittingVideo ? "Saving brief..." : "Generate Video"}
                </Button>
              ) : (
                <Alert className="rounded-2xl border-[color:var(--brand-teal)] bg-[color:rgba(13,148,136,0.06)]" data-testid="video-brief-ready-alert">
                  <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-teal)]" />
                  <AlertTitle>Video brief ready</AlertTitle>
                  <AlertDescription>
                    Your face-swapped reference image(s), prompt, and target duration ({videoJob.target_duration_seconds}s)
                    are saved and ready to send to a video-generation provider. Actual video rendering will go live once
                    a provider (e.g. Runway, Kling, Luma) is connected — this brief is saved to your History in the
                    meantime.
                  </AlertDescription>
                </Alert>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
