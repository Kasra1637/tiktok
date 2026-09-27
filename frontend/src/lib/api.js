import axios from "axios";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "");
const API = `${BACKEND_URL}/api`;

export const mediaUrl = (path) => {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BACKEND_URL}${path.startsWith("/") ? path : `/${path}`}`;
};

const client = axios.create({ baseURL: API, timeout: 120000 });

/**
 * Attach the Clerk session JWT to every outgoing request.
 *
 * @clerk/clerk-react exposes `window.Clerk` after initialization. We call
 * `session.getToken()` which returns the current short-lived JWT (and
 * silently refreshes it when needed). If Clerk isn't loaded yet or the user
 * is not signed in, the request goes out without a token — the backend will
 * return 401 which the ProtectedRoute wrapper prevents from ever reaching
 * the UI in normal use.
 */
client.interceptors.request.use(async (config) => {
  try {
    const clerk = window.Clerk;
    if (clerk && clerk.session) {
      const token = await clerk.session.getToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
  } catch (e) {
    // Token fetch failed — let the request proceed unauthenticated.
    // The backend will reject it if the route requires auth.
    console.warn("Failed to attach auth token:", e);
  }
  return config;
});

export const api = {
  getNiches: () => client.get("/niches").then((r) => r.data),
  getNicheVideos: (nicheKey, mode = "curated", includeAds = true) =>
    client.get(`/niches/${nicheKey}/videos`, { params: { mode, include_ads: includeAds } }).then((r) => r.data),
  getTrendingVideos: (nicheKey, includeAds = true) =>
    client.get(`/niches/${nicheKey}/trending`, { params: { include_ads: includeAds } }).then((r) => r.data),
  searchTrending: (query, limit = 20, includeAds = true) =>
    client.get("/trending/search", { params: { q: query, limit, include_ads: includeAds } }).then((r) => r.data),
  ingestVideo: (tiktok_url, niche = null) =>
    client.post("/videos/ingest", { tiktok_url, niche }).then((r) => r.data),
  getVideo: (videoId) => client.get(`/videos/${videoId}`).then((r) => r.data),
  analyzeHook: (videoId) => client.post(`/videos/${videoId}/analyze-hook`).then((r) => r.data),
  getAnalysis: (videoId) => client.get(`/videos/${videoId}/analysis`).then((r) => r.data),
  customize: (videoId, formData) =>
    client
      .post(`/videos/${videoId}/customize`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data),
  getCustomizations: () => client.get("/customizations").then((r) => r.data),
  getCustomization: (id) => client.get(`/customizations/${id}`).then((r) => r.data),
  getVideoInfo: (videoId) => client.get(`/videos/${videoId}`).then((r) => r.data),
  // Structural availability of Aleph's exact-edit path for this video. Cheap
  // and side-effect free; the caller ANDs it with its own style inputs.
  getHookEngine: (videoId) =>
    client.get(`/videos/${videoId}/hook-engine`).then((r) => r.data),
  // Motion styles + the exact prompt text each one sends, so the UI can show
  // the real instruction rather than a separately maintained paraphrase.
  getHookMotionStyles: () =>
    client.get("/hook-motion-styles").then((r) => r.data),
  getHistory: () => client.get("/history").then((r) => r.data),
  deleteVideo: (videoId) => client.delete(`/videos/${videoId}`).then((r) => r.data),
  getRemixChat: (customizationId) =>
    client.get(`/customizations/${customizationId}/remix-chat`).then((r) => r.data),
  sendRemixChatMessage: (customizationId, message) =>
    client.post(`/customizations/${customizationId}/remix-chat`, { message }).then((r) => r.data),
  generateVideoPrompt: (customizationId, payload) =>
    client.post(`/customizations/${customizationId}/generate-video-prompt`, payload).then((r) => r.data),
  generateVideo: (jobId, payload) =>
    client.post(`/video-jobs/${jobId}/generate-video`, payload).then((r) => r.data),
  getVideoJob: (jobId) => client.get(`/video-jobs/${jobId}`).then((r) => r.data),

  // Standalone face swap: submit quickly, then poll the app job while GPT renders.
  faceSwap: (formData) =>
    client
      .post("/face-swap", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      })
      .then((r) => r.data),
  faceSwapStatus: (jobId) =>
    client.get(`/face-swap/status/${jobId}`).then((r) => r.data),

  // Face Swap → Video Generation (Phase 2)
  faceSwapGenerateVideo: (imageId, prompt, duration, model) => {
    const formData = new FormData();
    formData.append("image_id", imageId);
    formData.append("prompt", prompt || "");
    formData.append("duration", String(duration || 10));
    formData.append("model", model || "");
    return client
      .post("/face-swap/generate-video", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      })
      .then((r) => r.data);
  },
  faceSwapGenerateHook: (imageId, motionStyle, model, videoId, templateId, includeAudio = false, hookCategory = "", hookCustomPrompt = "") => {
    const formData = new FormData();
    formData.append("image_id", imageId);
    formData.append("motion_style", motionStyle || "lean-in");
    formData.append("model", model || "");
    formData.append("video_id", videoId || "");
    formData.append("template_id", templateId || "");
    formData.append("include_audio", includeAudio ? "true" : "false");
    formData.append("hook_category", hookCategory || "");
    formData.append("hook_custom_prompt", hookCustomPrompt || "");
    return client
      .post("/face-swap/generate-hook-video", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      })
      .then((r) => r.data);
  },
  faceSwapExtendVideo: (imageId, hookJobId, brandUrl, duration, model, videoId, brandId) => {
    const formData = new FormData();
    formData.append("image_id", imageId);
    formData.append("hook_job_id", hookJobId || "");
    formData.append("brand_url", brandUrl || "");
    // Explicitly chosen saved brand. Takes precedence over brand_url server-side
    // so the creator picks the brand instead of re-entering a website.
    formData.append("brand_id", brandId || "");
    formData.append("duration", String(duration || 10));
    formData.append("model", model || "");
    formData.append("video_id", videoId || "");
    return client
      .post("/face-swap/extend-video", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      })
      .then((r) => r.data);
  },
  faceSwapVideoStatus: (jobId) =>
    client.get(`/face-swap/video-status/${jobId}`).then((r) => r.data),
  getVideoModels: () => client.get("/video-models").then((r) => r.data),

  // Persisted video assets (R2 storage)
  getVideoAssets: () => client.get("/video-assets").then((r) => r.data),
  deleteVideoAsset: (jobId) => client.delete(`/video-assets/${jobId}`).then((r) => r.data),

  // Face Swap → Branded Video (Content Remixer)
  faceSwapBrandedPrompt: (imageId, brandUrl, videoId, duration, useOriginalSound = false) => {
    const formData = new FormData();
    formData.append("image_id", imageId);
    formData.append("brand_url", brandUrl || "");
    formData.append("video_id", videoId || "");
    formData.append("duration", String(duration || 15));
    formData.append("use_original_sound", useOriginalSound ? "true" : "false");
    return client
      .post("/face-swap/generate-branded-prompt", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 90000,
      })
      .then((r) => r.data);
  },

  // Bookmarks — save a hook analysis for quick access from history
  getBookmarks: (params = {}) =>
    client.get("/bookmarks", { params }).then((r) => r.data),
  getBookmark: (id) => client.get(`/bookmarks/${id}`).then((r) => r.data),
  createBookmark: (payload) =>
    client.post("/bookmarks", payload).then((r) => r.data),
  updateBookmark: (id, payload) =>
    client.patch(`/bookmarks/${id}`, payload).then((r) => r.data),
  deleteBookmark: (id) => client.delete(`/bookmarks/${id}`).then((r) => r.data),

  // Brand profile / Content Remixer
  analyzeBrandUrl: (url) => client.post("/brand/analyze-url", { url }).then((r) => r.data),
  getActiveBrand: () => client.get("/brand/active").then((r) => r.data),
  // All saved brands for the current user, active first — powers the brand
  // picker so generation flows don't require re-entering a URL.
  getBrands: () => client.get("/brands").then((r) => r.data),
  getBrand: (id) => client.get(`/brand/${id}`).then((r) => r.data),
  createBrand: (payload) => client.post("/brand", payload).then((r) => r.data),
  updateBrand: (id, payload) => client.patch(`/brand/${id}`, payload).then((r) => r.data),
  generateRemixScript: (customizationId, payload) =>
    client.post(`/customizations/${customizationId}/generate-remix-script`, payload).then((r) => r.data),

  // App Profiles (template-studio workflow: research -> review/approve -> refresh)
  researchAppProfile: (payload) => client.post("/app-profiles/research", payload).then((r) => r.data),
  getAppProfiles: () => client.get("/app-profiles").then((r) => r.data),
  getAppProfile: (id) => client.get(`/app-profiles/${id}`).then((r) => r.data),
  updateAppProfile: (id, payload) => client.patch(`/app-profiles/${id}`, payload).then((r) => r.data),
  approveAppProfile: (id, applyPending = true) =>
    client.post(`/app-profiles/${id}/approve`, { apply_pending: applyPending }).then((r) => r.data),
  refreshAppProfile: (id) => client.post(`/app-profiles/${id}/refresh`).then((r) => r.data),

  // Content angles (per App Profile)
  getContentAngles: (profileId) =>
    client.get(`/app-profiles/${profileId}/content-angles`).then((r) => r.data),
  generateContentAngles: (profileId) =>
    client.post(`/app-profiles/${profileId}/content-angles`).then((r) => r.data),
  createContentAngle: (profileId, payload) =>
    client.post(`/app-profiles/${profileId}/content-angles/manual`, payload).then((r) => r.data),
  updateContentAngle: (profileId, angleId, payload) =>
    client.patch(`/app-profiles/${profileId}/content-angles/${angleId}`, payload).then((r) => r.data),
  deleteContentAngle: (profileId, angleId) =>
    client.delete(`/app-profiles/${profileId}/content-angles/${angleId}`).then((r) => r.data),

  // Hook Template Library
  getTemplates: (params = {}) => client.get("/templates", { params }).then((r) => r.data),
  getTemplateFacets: () => client.get("/templates/facets").then((r) => r.data),
  getTemplate: (id) => client.get(`/templates/${id}`).then((r) => r.data),
  createTemplate: (payload) => client.post("/templates", payload).then((r) => r.data),
  updateTemplate: (id, payload) => client.patch(`/templates/${id}`, payload).then((r) => r.data),
  duplicateTemplate: (id) => client.post(`/templates/${id}/duplicate`).then((r) => r.data),
  toggleTemplateFavorite: (id) => client.post(`/templates/${id}/favorite`).then((r) => r.data),
  archiveTemplate: (id, archived = true) =>
    client.post(`/templates/${id}/archive`, null, { params: { archived } }).then((r) => r.data),
  publishTemplate: (id) => client.post(`/templates/${id}/publish`).then((r) => r.data),

  // Template recommendations
  getTemplateRecommendations: (profileId, params = {}) =>
    client.get(`/app-profiles/${profileId}/template-recommendations`, { params }).then((r) => r.data),

  // Studio projects (guided creation)
  getStudioProjects: (params = {}) => client.get("/studio/projects", { params }).then((r) => r.data),
  getStudioProject: (id) => client.get(`/studio/projects/${id}`).then((r) => r.data),
  createStudioProject: (payload) => client.post("/studio/projects", payload).then((r) => r.data),
  updateStudioProject: (id, payload) => client.patch(`/studio/projects/${id}`, payload).then((r) => r.data),
  generatePlan: (id, payload = {}) => client.post(`/studio/projects/${id}/plan`, payload).then((r) => r.data),
  markProjectReady: (id) => client.post(`/studio/projects/${id}/ready`).then((r) => r.data),

  // Video generation (single-pass)
  getStudioVideoModels: () => client.get("/studio/video-models").then((r) => r.data),
  generateVideo: (projectId, payload = {}) =>
    client.post(`/studio/projects/${projectId}/generate`, payload).then((r) => r.data),
  getGenerations: (params = {}) => client.get("/generations", { params }).then((r) => r.data),
  getGeneration: (id) => client.get(`/generations/${id}`).then((r) => r.data),
  pollGeneration: (id) => client.post(`/generations/${id}/poll`).then((r) => r.data),
  retryGeneration: (id) => client.post(`/generations/${id}/retry`).then((r) => r.data),
  extendGeneration: (id, payload = {}) =>
    client.post(`/generations/${id}/extend`, payload).then((r) => r.data),
  archiveGeneration: (id) => client.post(`/generations/${id}/archive`).then((r) => r.data),

  // Asset library (per App Profile)
  getAssets: (profileId, params = {}) =>
    client.get(`/app-profiles/${profileId}/assets`, { params }).then((r) => r.data),
  uploadAsset: (profileId, formData) =>
    client
      .post(`/app-profiles/${profileId}/assets`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 300000,
      })
      .then((r) => r.data),
  updateAsset: (id, payload) => client.patch(`/assets/${id}`, payload).then((r) => r.data),
  deleteAsset: (id) => client.delete(`/assets/${id}`).then((r) => r.data),
  attachAsset: (projectId, payload) =>
    client.post(`/studio/projects/${projectId}/assets`, payload).then((r) => r.data),
  detachAsset: (projectId, assetId) =>
    client.delete(`/studio/projects/${projectId}/assets/${assetId}`).then((r) => r.data),

  // Deterministic overlay composition
  composeOverlays: (generationId, payload = {}) =>
    client.post(`/generations/${generationId}/overlay`, payload).then((r) => r.data),
  getOverlayComposition: (generationId) =>
    client.get(`/generations/${generationId}/overlay`).then((r) => r.data),
};

export const getErrorMessage = (err) => {
  return (
    err?.response?.data?.detail ||
    err?.message ||
    "Something went wrong. Please try again."
  );
};
