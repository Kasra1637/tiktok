import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Skeleton } from "../components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import GenerationProgress from "../components/GenerationProgress";
import RemixChat from "../components/RemixChat";
import PageHeader from "../components/PageHeader";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { ArrowLeft, Wand2, Clapperboard, AlertTriangle, RotateCcw, Clock, Film, Camera, Eye, Users, MapPinned, Megaphone, CheckCircle2, Sparkles, Music2, ImageOff } from "lucide-react";
import { toast } from "sonner";

function RemixChatEmptyState() {
  return (
    <div className="mx-auto max-w-sm px-6 text-center" data-testid="remix-chat-empty-state">
      <span className="mx-auto mb-3.5 flex h-12 w-12 items-center justify-center rounded-2xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
        <Sparkles className="h-5 w-5" />
      </span>
      <p className="font-display text-sm font-semibold">Tell us how you want to remix this hook</p>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
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
  { key: "audio_recommendation", label: "Audio", icon: Music2 },
];

/** Labelled form field wrapper, matching BrandSetup's field rhythm. */
function Field({ label, icon: Icon, children }) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1.5 text-sm font-medium">
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
        {label}
      </label>
      {children}
    </div>
  );
}

export default function GenerateVideo() {
  const { customizationId } = useParams();
  const navigate = useNavigate();

  const [customization, setCustomization] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const [sourceVideo, setSourceVideo] = useState(null);
  const [useOriginalSound, setUseOriginalSound] = useState(false);

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
      .then((c) => {
        setCustomization(c);
        if (c?.video_id) {
          api
            .getVideoInfo(c.video_id)
            .then(setSourceVideo)
            .catch(() => {
              // Non-fatal: sound info just won't be shown if this fails.
            });
        }
      })
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
        use_original_sound: useOriginalSound,
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
        use_original_sound: useOriginalSound,
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
      <div className="mx-auto max-w-2xl space-y-4">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load this customization</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
        <Button onClick={() => navigate("/discover")} variant="accent" className="gap-1.5">
          <ArrowLeft className="h-4 w-4" /> Back to feed
        </Button>
      </div>
    );
  }

  if (!customization) {
    return (
      <div className="space-y-5" data-testid="generate-video-loading">
        <div className="space-y-2.5">
          <Skeleton className="h-9 w-72 rounded-xl" />
          <Skeleton className="h-4 w-full max-w-2xl rounded-md" />
        </div>
        <Skeleton className="h-[420px] w-full rounded-2xl" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[420px_1fr]">
          <div className="surface h-fit space-y-3 rounded-2xl p-5">
            <div className="flex gap-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-16 shrink-0 rounded-lg" />
              ))}
            </div>
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-10 w-full rounded-xl" />
          </div>
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </div>
    );
  }

  const hasSound = !!(sourceVideo?.song_title || sourceVideo?.song_artist);

  return (
    <div className="space-y-5">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate(`/customize/${customization.video_id}`)}
        className="-ml-2 gap-1 text-muted-foreground"
        data-testid="back-to-customize-button"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back
      </Button>

      <PageHeader
        icon={Sparkles}
        title="Content Remixer"
        description="Remix this viral hook for your brand with AI-powered scriptwriting."
        actions={
          !brandLoading && brandProfile ? (
            <Badge variant="indigo" className="px-3 py-1">
              <CheckCircle2 className="h-3 w-3" /> {brandProfile.brand_name || "Brand profile"} loaded
            </Badge>
          ) : null
        }
      />

      {/* ---------- Conversational brief ---------- */}
      <div className="h-[420px] md:h-[480px]">
        <RemixChat
          messages={remixMessages}
          onSend={handleSendRemixMessage}
          sending={remixSending}
          readyToGenerate={remixReady}
          emptyState={<RemixChatEmptyState />}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[420px_1fr]">
        {/* ---------- Left: the brief form ---------- */}
        <div className="surface h-fit space-y-5 rounded-2xl p-5">
          <div>
            <span className="eyebrow block">Reference frames</span>
            <div className="mt-2 flex gap-2 overflow-x-auto pb-1" data-testid="reference-images-row">
              {(customization.generated_images || []).length > 0 ? (
                (customization.generated_images || []).map((img) => (
                  <img
                    key={img.id}
                    src={mediaUrl(img.image_url)}
                    alt="Face-swapped reference"
                    className="h-20 w-16 shrink-0 rounded-lg border border-[color:var(--hairline)] object-cover"
                  />
                ))
              ) : (
                <div className="flex h-20 w-16 shrink-0 items-center justify-center rounded-lg border border-dashed border-[color:var(--hairline-strong)]">
                  <ImageOff className="h-4 w-4 text-muted-foreground/50" />
                </div>
              )}
            </div>
          </div>

          <div className="h-px bg-border/60" />

          <Field label="Brand name">
            <Input
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="e.g. Voxel — Voice Journaling App"
              data-testid="brand-name-input"
            />
          </Field>

          <Field label="Brand goal">
            <Input
              value={brandGoal}
              onChange={(e) => setBrandGoal(e.target.value)}
              placeholder="e.g. Drive app installs"
              data-testid="brand-goal-input"
            />
          </Field>

          <Field label="Brand details">
            <Textarea
              value={brandDetails}
              onChange={(e) => setBrandDetails(e.target.value)}
              placeholder="What does the brand offer? What should the video communicate?"
              className="min-h-[90px]"
              data-testid="brand-details-textarea"
            />
          </Field>

          <Field label="Target duration (seconds, max 30)" icon={Clock}>
            <Input
              type="number"
              min={5}
              max={30}
              value={duration}
              onChange={(e) => setDuration(Math.max(5, Math.min(30, Number(e.target.value) || 30)))}
              data-testid="duration-input"
            />
          </Field>

          {hasSound ? (
            <div
              className="flex items-center justify-between gap-3 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 px-3 py-2.5"
              data-testid="use-original-sound-toggle-row"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                  <Music2 className="h-3.5 w-3.5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium leading-tight">Use original sound</p>
                  <p
                    className="truncate text-xs text-muted-foreground"
                    title={`${sourceVideo.song_title || ""} ${sourceVideo.song_artist ? `— ${sourceVideo.song_artist}` : ""}`}
                  >
                    {sourceVideo.song_title || "Untitled sound"}
                    {sourceVideo.song_artist ? ` — ${sourceVideo.song_artist}` : ""}
                  </p>
                </div>
              </div>
              <Switch
                checked={useOriginalSound}
                onCheckedChange={setUseOriginalSound}
                data-testid="use-original-sound-switch"
              />
            </div>
          ) : null}

          <div className="space-y-2">
            {brandProfile ? (
              <Button
                onClick={handleRemixForBrand}
                disabled={generatingPrompt}
                variant="brand"
                className="w-full"
                data-testid="remix-for-brand-button"
              >
                <Sparkles className="h-4 w-4" />
                {generatingPrompt ? "Remixing..." : `Remix this hook for ${brandProfile.brand_name || "your brand"}`}
              </Button>
            ) : (
              <Button
                onClick={handleGeneratePrompt}
                disabled={generatingPrompt}
                variant="brand"
                className="w-full"
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
                className="w-full"
                data-testid="generate-prompt-manual-button"
              >
                <Wand2 className="h-4 w-4" /> {generatingPrompt ? "Writing prompt..." : "Generate with manual fields instead"}
              </Button>
            )}
          </div>
        </div>

        {/* ---------- Right: the generated prompt ---------- */}
        <div className="space-y-4">
          {generatingPrompt && (
            <div className="surface rounded-2xl p-6">
              <div className="mb-5 flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                  <Clapperboard className="h-[18px] w-[18px]" />
                </span>
                <div>
                  <h3 className="font-display font-semibold">Writing your video prompt...</h3>
                  <p className="text-xs text-muted-foreground">Adapting the hook's mechanics to your brand</p>
                </div>
              </div>
              <GenerationProgress stages={PROMPT_STAGES} active={true} />
            </div>
          )}

          {promptError && (
            <Alert variant="destructive" data-testid="prompt-error-alert">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Prompt generation failed</AlertTitle>
              <AlertDescription className="space-y-2.5">
                <p>{promptError}</p>
                <Button
                  size="sm"
                  variant="secondary"
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
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="prompt-breakdown">
                {BREAKDOWN_SECTIONS.map(({ key, label, icon: Icon }) => (
                  <div key={key} className="surface surface-interactive rounded-2xl p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <h4 className="font-display text-sm font-semibold">{label}</h4>
                    </div>
                    <p className="line-clamp-4 text-xs leading-relaxed text-muted-foreground">
                      {job.prompt_breakdown?.[key]}
                    </p>
                  </div>
                ))}
              </div>

              <div className="surface space-y-3 rounded-2xl p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="font-display text-sm font-semibold">Full video prompt (editable)</h4>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {usingRemix && (
                      <Badge variant="coral" className="text-xs">
                        Content Remix
                      </Badge>
                    )}
                    {useOriginalSound && hasSound && (
                      <Badge variant="indigo" className="text-xs" data-testid="using-original-sound-badge">
                        <Music2 className="h-2.5 w-2.5" /> Original sound
                      </Badge>
                    )}
                    <Badge variant="secondary" className="text-xs">
                      ~{job.target_duration_seconds}s
                    </Badge>
                  </div>
                </div>
                <Textarea
                  value={editedPrompt}
                  onChange={(e) => setEditedPrompt(e.target.value)}
                  className="min-h-[180px] font-mono text-xs leading-relaxed"
                  data-testid="full-prompt-textarea"
                />
                {useOriginalSound && hasSound && (
                  <Alert
                    className="border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)]"
                    data-testid="original-sound-reminder"
                  >
                    <Music2 className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" />
                    <AlertDescription className="text-xs text-muted-foreground">
                      This prompt is written for the original sound "{sourceVideo.song_title || "Untitled sound"}"
                      {sourceVideo.song_artist ? ` by ${sourceVideo.song_artist}` : ""} playing underneath. Since AI
                      video generation can't embed licensed audio directly, add this sound from{" "}
                      <a
                        href={sourceVideo.tiktok_url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-[color:var(--brand-indigo)] underline"
                      >
                        the original TikTok
                      </a>{" "}
                      when you post your remix.
                    </AlertDescription>
                  </Alert>
                )}
              </div>

              {!videoJob ? (
                <Button
                  onClick={handleGenerateVideo}
                  disabled={submittingVideo}
                  variant="accent"
                  size="lg"
                  className="w-full"
                  data-testid="generate-video-button"
                >
                  <Clapperboard className="h-4 w-4" /> {submittingVideo ? "Saving brief..." : "Generate Video"}
                </Button>
              ) : (
                <Alert
                  className="border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)]"
                  data-testid="video-brief-ready-alert"
                >
                  <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                  <AlertTitle>Video brief ready</AlertTitle>
                  <AlertDescription className="text-muted-foreground">
                    Your face-swapped reference image(s), prompt, and target duration ({videoJob.target_duration_seconds}s)
                    are saved and ready to send to a video-generation provider. Actual video rendering will go live once
                    a provider (e.g. Runway, Kling, Luma) is connected — this brief is saved to your History in the
                    meantime.
                    {useOriginalSound && hasSound && (
                      <>
                        {" "}Remember to add the original sound "{sourceVideo.song_title || "Untitled sound"}"
                        {sourceVideo.song_artist ? ` by ${sourceVideo.song_artist}` : ""} when you post — this is
                        saved on the brief as your chosen audio.
                      </>
                    )}
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
