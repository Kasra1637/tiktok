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
  getNicheVideos: (nicheKey, mode = "curated") =>
    client.get(`/niches/${nicheKey}/videos`, { params: { mode } }).then((r) => r.data),
  getTrendingVideos: (nicheKey) =>
    client.get(`/niches/${nicheKey}/trending`).then((r) => r.data),
  searchTrending: (query, limit = 20) =>
    client.get("/trending/search", { params: { q: query, limit } }).then((r) => r.data),
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
  getHistory: () => client.get("/history").then((r) => r.data),
  analyzeBrandWebsite: (websiteUrl) =>
    client.post("/brand/analyze-website", { website_url: websiteUrl }).then((r) => r.data),
  generateVideoPrompt: (customizationId, payload) =>
    client.post(`/customizations/${customizationId}/generate-video-prompt`, payload).then((r) => r.data),
  generateVideo: (jobId, payload) =>
    client.post(`/video-jobs/${jobId}/generate-video`, payload).then((r) => r.data),
  getVideoJob: (jobId) => client.get(`/video-jobs/${jobId}`).then((r) => r.data),
};

export const getErrorMessage = (err) => {
  return (
    err?.response?.data?.detail ||
    err?.message ||
    "Something went wrong. Please try again."
  );
};
