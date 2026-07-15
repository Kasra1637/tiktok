import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const API = `${BACKEND_URL}/api`;

export const mediaUrl = (path) => {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BACKEND_URL}${path}`;
};

const client = axios.create({ baseURL: API, timeout: 120000 });

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
  getHistory: () => client.get("/history").then((r) => r.data),
  getRemixChat: (customizationId) =>
    client.get(`/customizations/${customizationId}/remix-chat`).then((r) => r.data),
  sendRemixChatMessage: (customizationId, message) =>
    client.post(`/customizations/${customizationId}/remix-chat`, { message }).then((r) => r.data),
  generateVideoPrompt: (customizationId, payload) =>
    client.post(`/customizations/${customizationId}/generate-video-prompt`, payload).then((r) => r.data),
  generateVideo: (jobId, payload) =>
    client.post(`/video-jobs/${jobId}/generate-video`, payload).then((r) => r.data),
  getVideoJob: (jobId) => client.get(`/video-jobs/${jobId}`).then((r) => r.data),

  // Standalone face swap (Higgsfield-style 3-step flow)
  faceSwap: (formData) =>
    client
      .post("/face-swap", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 240000,
      })
      .then((r) => r.data),

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
  faceSwapGenerateHook: (imageId, motionStyle, model) => {
    const formData = new FormData();
    formData.append("image_id", imageId);
    formData.append("motion_style", motionStyle || "lean-in");
    formData.append("model", model || "");
    return client
      .post("/face-swap/generate-hook-video", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      })
      .then((r) => r.data);
  },
  faceSwapExtendVideo: (imageId, hookJobId, brandUrl, duration, model) => {
    const formData = new FormData();
    formData.append("image_id", imageId);
    formData.append("hook_job_id", hookJobId || "");
    formData.append("brand_url", brandUrl || "");
    formData.append("duration", String(duration || 10));
    formData.append("model", model || "");
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

  // Brand profile / Content Remixer
  analyzeBrandUrl: (url) => client.post("/brand/analyze-url", { url }).then((r) => r.data),
  getActiveBrand: () => client.get("/brand/active").then((r) => r.data),
  getBrand: (id) => client.get(`/brand/${id}`).then((r) => r.data),
  updateBrand: (id, payload) => client.patch(`/brand/${id}`, payload).then((r) => r.data),
  generateRemixScript: (customizationId, payload) =>
    client.post(`/customizations/${customizationId}/generate-remix-script`, payload).then((r) => r.data),
};

export const getErrorMessage = (err) => {
  return (
    err?.response?.data?.detail ||
    err?.message ||
    "Something went wrong. Please try again."
  );
};
