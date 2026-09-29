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
  getHistory: () => client.get("/history").then((r) => r.data),
  deleteVideo: (videoId) => client.delete(`/videos/${videoId}`).then((r) => r.data),

  // Persisted video assets (R2 storage)
  getVideoAssets: () => client.get("/video-assets").then((r) => r.data),
  deleteVideoAsset: (jobId) => client.delete(`/video-assets/${jobId}`).then((r) => r.data),

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

  // App Profiles (template-studio workflow: research -> review/approve -> refresh)
  researchAppProfile: (payload) => client.post("/app-profiles/research", payload).then((r) => r.data),
  getAppProfiles: () => client.get("/app-profiles").then((r) => r.data),
  getAppProfile: (id) => client.get(`/app-profiles/${id}`).then((r) => r.data),
  deleteAppProfile: (id) => client.delete(`/app-profiles/${id}`).then((r) => r.data),
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
  setProjectHookLength: (id, hookSeconds) =>
    client.patch(`/studio/projects/${id}`, { hook_seconds: hookSeconds }).then((r) => r.data),
  setProjectExtendIntent: (id, extendIntent) =>
    client.patch(`/studio/projects/${id}`, { extend_intent: extendIntent }).then((r) => r.data),

  // Video generation (single-pass)
  getStudioVideoModels: () => client.get("/studio/video-models").then((r) => r.data),
  generateVideo: (projectId, payload = {}) =>
    client.post(`/studio/projects/${projectId}/generate`, payload).then((r) => r.data),
  getGenerations: (params = {}) => client.get("/generations", { params }).then((r) => r.data),
  getGeneration: (id) => client.get(`/generations/${id}`).then((r) => r.data),
  pollGeneration: (id) => client.post(`/generations/${id}/poll`).then((r) => r.data),
  retryGeneration: (id) => client.post(`/generations/${id}/retry`).then((r) => r.data),
  retryGenerationStorage: (id) => client.post(`/generations/${id}/storage/retry`).then((r) => r.data),
  extendGeneration: (id, payload = {}) =>
    client.post(`/generations/${id}/extend`, payload).then((r) => r.data),
  archiveGeneration: (id) => client.post(`/generations/${id}/archive`).then((r) => r.data),

  // App-specific influencer workflow:
  // strategy -> hook -> approve -> extend (repeatable) -> assemble
  generateStrategy: (id, payload = {}) =>
    client.post(`/studio/projects/${id}/strategy`, payload).then((r) => r.data),
  generateHook: (id, payload = {}) =>
    client.post(`/studio/projects/${id}/hook`, payload).then((r) => r.data),
  approveGeneration: (id, payload = {}) =>
    client.post(`/generations/${id}/approve`, payload).then((r) => r.data),
  getGenerationContinuity: (id) =>
    client.get(`/generations/${id}/continuity`).then((r) => r.data),
  assembleChain: (id, payload = {}) =>
    client.post(`/generations/${id}/assemble`, payload).then((r) => r.data),

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
  getAssetUsage: (id) => client.get(`/assets/${id}/usage`).then((r) => r.data),
  attachAsset: (projectId, payload) =>
    client.post(`/studio/projects/${projectId}/assets`, payload).then((r) => r.data),
  detachAsset: (projectId, assetId) =>
    client.delete(`/studio/projects/${projectId}/assets/${assetId}`).then((r) => r.data),

  // Deterministic overlay composition
  composeOverlays: (generationId, payload = {}) =>
    client.post(`/generations/${generationId}/overlay`, payload).then((r) => r.data),
  getOverlayComposition: (generationId) =>
    client.get(`/generations/${generationId}/overlay`).then((r) => r.data),

  // Variations
  getVariationKinds: () => client.get("/studio/variations").then((r) => r.data),
  createVariation: (generationId, payload) =>
    client.post(`/generations/${generationId}/variations`, payload).then((r) => r.data),
  getGenerationVariations: (generationId) =>
    client.get(`/generations/${generationId}/variations`).then((r) => r.data),
  duplicateGeneration: (generationId) =>
    client.post(`/generations/${generationId}/duplicate`).then((r) => r.data),

  // History + manual performance
  getGenerationHistory: (params = {}) =>
    client.get("/history/generations", { params }).then((r) => r.data),
  deleteGeneration: (id) => client.delete(`/generations/${id}`).then((r) => r.data),
  getPerformance: (id) => client.get(`/generations/${id}/performance`).then((r) => r.data),
  recordPerformance: (id, payload) =>
    client.post(`/generations/${id}/performance`, payload).then((r) => r.data),

  // Trend research, feedback, analytics, operations
  runResearchScan: (payload) => client.post("/research/scan", payload).then((r) => r.data),
  getResearchRuns: (params = {}) => client.get("/research/runs", { params }).then((r) => r.data),
  getResearchRun: (id) => client.get(`/research/runs/${id}`).then((r) => r.data),
  getFeedbackCatalog: () => client.get("/feedback/catalog").then((r) => r.data),
  recordFeedback: (payload) => client.post("/feedback", payload).then((r) => r.data),
  getFeedback: (params = {}) => client.get("/feedback", { params }).then((r) => r.data),
  getAnalytics: (params = {}) => client.get("/analytics", { params }).then((r) => r.data),
  getOperations: () => client.get("/operations").then((r) => r.data),
  getDashboard: () => client.get("/dashboard").then((r) => r.data),
  getSettings: () => client.get("/settings").then((r) => r.data),
};

export const getErrorMessage = (err) => {
  return (
    err?.response?.data?.detail ||
    err?.message ||
    "Something went wrong. Please try again."
  );
};
