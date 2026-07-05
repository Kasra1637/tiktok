import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Skeleton } from "../components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import GenerationProgress from "../components/GenerationProgress";
import RemixChat from "../components/RemixChat";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { ArrowLeft, Wand2, Clapperboard, AlertTriangle, RotateCcw, Clock, Film, Camera, Eye, Users, MapPinned, Megaphone, CheckCircle2, Sparkles, Briefcase, MessageSquareText } from "lucide-react";
import { toast } from "sonner";

function RemixChatEmptyState() {
  return (
    <div className="text-center px-6 max-w-sm mx-auto" data-testid="remix-chat-empty-state">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[color:rgba(99,102,241,0.10)] text-[color:var(--brand-teal)] mx-auto mb-3">
        <Sparkles className="h-5 w-5" />
      </span>
      <p className="text-sm font-medium">Tell us how you want to remix this hook</p>
      <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
        e.g. "Remix this for my dating app that gives feedback on profile screenshots" — we'll check the
        audience fit against the original video and ask a couple of quick questions before writing your video
        prompt.
      </p>
    </div>
  );
}

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

  const [brandProfile, setBrandProfile] = useState(null);
  const [brandLoading, setBrandLoading] = useState(true);

  const [brandName, setBrandName] = useState("");
  const [brandGoal, setBrandGoal] = useState("");
  const [brandDetails, setBrandDetails] = useState("");
  const [duration, setDuration] = useState(30);

  const [generatingPrompt, setGeneratingPrompt] = useState(false);
  const [promptError, setPromptError] = useState(null);
  const [job, setJob] = useState(null);
  const [editedPrompt, setEditedPrompt] = useState("");
  const [usingRemix, setUsingRemix] = useState(false);

  const [submittingVideo, setSubmittingVideo] = useState(false);
  const [videoJob, setVideoJob] = useState(null);

  // Conversational remix chat: an alternative to the saved brand-profile
  // "Content Remixer" button above, for describing your goal in your own
  // words and getting clarifying questions back. Replies incrementally
  // fill in the manual brand fields below, which stay fully editable.
  const [remixMessages, setRemixMessages] = useState([]);
  const [remixSending, setRemixSending] = useState(false);
  const [remixReady, setRemixReady] = useState(false);

  const applyChatBriefToFields = (brief) => {
    if (!brief) return;
    if (brief.brand_name) setBrandName(brief.brand_name);
    if (brief.brand_goal) setBrandGoal(brief.brand_goal);
    const detailParts = [
      brief.brand_details,
      brief.brand_overview,
      (brief.unique_selling_propositions || []).length
        ? `USPs: ${(brief.unique_selling_propositions || []).join("; ")}`
        : "",
      brief.brand_voice_tone ? `Tone: ${brief.brand_voice_tone}` : "",
      brief.target_audience ? `Target audience: ${brief.target_audience}` : "",
    ].filter(Boolean);
    if (detailParts.length) setBrandDetails(detailParts.join(" "));
  };

  useEffect(() => {
    api
      .getCustomization(customizationId)
      .then(setCustomization)
      .catch((err) => setLoadError(getErrorMessage(err)));

    api
      .getRemixChat(customizationId)
      .then((chat) => {
        setRemixMessages(chat.messages || []);
        setRemixReady(!!chat.ready_to_generate);
        applyChatBriefToFields(chat.brief);
      })
      .catch(() => {
        // Non-fatal: the chat just starts empty if it can't be loaded yet.
      });
  }, [customizationId]);

  const handleSendRemixMessage = async (text) => {
    const optimisticUser = { role: "user", content: text };
    setRemixMessages((prev) => [...prev, optimisticUser]);
    setRemixSending(true);
    try {
      const chat = await api.sendRemixChatMessage(customizationId, text);
      setRemixMessages(chat.messages || []);
      setRemixReady(!!chat.ready_to_generate);
      applyChatBriefToFields(chat.brief);
    } catch (err) {
      toast.error(getErrorMessage(err));
      setRemixMessages((prev) => prev.filter((m) => m !== optimisticUser));
    } finally {
      setRemixSending(false);
    }
  };

  useEffect(() => {
    api
      .getActiveBrand()
      .then((brand) => {
        setBrandProfile(brand);
        // Pre-fill manual fields from the saved brand profile so they stay editable.
        setBrandName(brand.brand_name || "");
        setBrandGoal(brand.target_audience ? `Reach: ${brand.target_audience}` : "");
        const products = Array.isArray(brand.products_services)
          ? brand.products_services.join(", ")
          : brand.products_services || "";
        const detailParts = [brand.brand_description, products ? `Products/services: ${products}` : "", brand.tone_voice ? `Tone: ${brand.tone_voice}` : ""].filter(Boolean);
        setBrandDetails(detailParts.join(" "));
      })
      .catch(() => setBrandProfile(null))
      .finally(() => setBrandLoading(false));
  }, []);

  const handleGeneratePrompt = async () => {
    setGeneratingPrompt(true);
    setPromptError(null);
    setJob(null);
    setVideoJob(null);
    setUsingRemix(false);
    try {
      const data = await api.generateVideoPrompt(customizationId, {
        brand_name: brandName,
        brand_goal: brandGoal,
        brand_details: brandDetails,
        duration_seconds: Number(duration) || 30,
      });
      setJob(data);
      setEditedPrompt(data.full_prompt_text || "");
    } catch (err) {
      setPromptError(getErrorMessage(err));
    } finally {
      setGeneratingPrompt(false);
    }
  };

  const handleRemixForBrand = async () => {
    setGeneratingPrompt(true);
    setPromptError(null);
    setJob(null);
    setVideoJob(null);
    setUsingRemix(true);
    try {
      const data = await api.generateRemixScript(customizationId, {
        duration_seconds: Number(duration) || 30,
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
        <Button onClick={() => navigate("/discover")} className="gap-1.5">
          <ArrowLeft className="h-4 w-4" /> Back to feed
        </Button>
      </div>
    );
  }

  if (!customization) {
    return (
      <div className="space-y-4" data-testid="generate-video-loading">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-full max-w-2xl" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
          <Card className="p-4 md:p-5 rounded-2xl border-border space-y-3 h-fit">
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
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate(`/customize/${customization.video_id}`)}
        className="gap-1 -ml-2"
        data-testid="back-to-customize-button"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back
      </Button>

      <div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-[color:var(--brand-coral)]" /> Content Remixer
        </h1>
        <p className="text-muted-foreground mt-1 max-w-2xl">
          Remix this viral hook for your brand with AI-powered scriptwriting.
        </p>
      </div>

      <div className="space-y-1.5">
        <span className="text-xs font-medium flex items-center gap-1.5 text-muted-foreground">
          <MessageSquareText className="h-3.5 w-3.5 text-[color:var(--brand-teal)]" /> Chat with AI
        </span>
        <div className="h-[420px] md:h-[480px]">
          <RemixChat
            messages={remixMessages}
            onSend={handleSendRemixMessage}
            sending={remixSending}
            readyToGenerate={remixReady}
            emptyState={<RemixChatEmptyState />}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-4">
        <Card className="p-4 md:p-5 rounded-2xl border-border space-y-3 h-fit">
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

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Brand name</label>
            <Input
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="e.g. Voxel — Voice Journaling App"
              data-testid="brand-name-input"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Brand goal</label>
            <Input
              value={brandGoal}
              onChange={(e) => setBrandGoal(e.target.value)}
              placeholder="e.g. Drive app installs"
              data-testid="brand-goal-input"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Brand details</label>
            <Textarea
              value={brandDetails}
              onChange={(e) => setBrandDetails(e.target.value)}
              placeholder="What does the brand offer? What should the video communicate?"
              className="min-h-[90px]"
              data-testid="brand-details-textarea"
            />
          </div>
          <div className="space-y-1.5">
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

          {brandProfile ? (
            <Button
              onClick={handleRemixForBrand}
              disabled={generatingPrompt}
              className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white"
              data-testid="remix-for-brand-button"
            >
              <Sparkles className="h-4 w-4" />
              {generatingPrompt ? "Remixing..." : `Remix this hook for ${brandProfile.brand_name || "your brand"}`}
            </Button>
          ) : (
            <Button
              onClick={handleGeneratePrompt}
              disabled={generatingPrompt}
              className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white"
              data-testid="generate-prompt-button"
            >
              <Wand2 className="h-4 w-4" /> {generatingPrompt ? "Writing prompt..." : "Generate Video Prompt"}
            </Button>
          )}
          {brandProfile && (
            <Button
              onClick={handleGeneratePrompt}
              disabled={generatingPrompt}
              variant="secondary"
              className="w-full gap-2 rounded-xl"
              data-testid="generate-prompt-manual-button"
            >
              <Wand2 className="h-4 w-4" /> {generatingPrompt ? "Writing prompt..." : "Generate with manual fields instead"}
            </Button>
          )}
        </Card>

        <div className="space-y-4">
          {generatingPrompt && (
            <Card className="p-6 rounded-2xl border-border">
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
                <Button
                  size="sm"
                  onClick={usingRemix ? handleRemixForBrand : handleGeneratePrompt}
                  className="gap-1.5"
                  data-testid="retry-prompt-button"
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {job && !generatingPrompt && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="prompt-breakdown">
                {BREAKDOWN_SECTIONS.map(({ key, label, icon: Icon }) => (
                  <Card key={key} className="p-4 rounded-2xl border-border">
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

              <Card className="p-4 md:p-5 rounded-2xl border-border space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold">Full video prompt (editable)</h4>
                  <div className="flex items-center gap-1.5">
                    {usingRemix && (
                      <Badge className="rounded-full text-[10px] bg-[color:var(--brand-coral)] text-white border-transparent">
                        Content Remix
                      </Badge>
                    )}
                    <Badge variant="secondary" className="rounded-full text-[10px]">
                      ~{job.target_duration_seconds}s
                    </Badge>
                  </div>
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
