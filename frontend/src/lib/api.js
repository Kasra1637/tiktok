import axios from "axios";
import { isClerkConfigured } from "./clerk";
import { shouldRetryWithFreshToken, shouldForceSignIn } from "./authRecovery";
import { errorMessageFor } from "./errorMessage";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "");
const API = `${BACKEND_URL}/api`;

export const mediaUrl = (path) => {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BACKEND_URL}${path.startsWith("/") ? path : `/${path}`}`;
};

/**
 * The URL the editor can actually fetch, always the durable copy, never the
 * provider's link.
 *
 * `r2_url` holds the finished clip the app saved: the durable R2 upload when
 * it succeeded, or the /api/media/videos/{id}.mp4 path for a local fallback.
 * `video_url` holds the provider's temporary link, and it is the only place
 * that link floats: the browser can never fetch it, because it requires a
 * bearer token and then expires. Never give a provider link to a fetch or a
 * <video>.
 */
export const durableMediaUrl = (row) => {
  if (row?.playback_url) return mediaUrl(row.playback_url);
  const durable = row?.r2_url;
  if (durable && durable.startsWith("http")) return mediaUrl(durable);
  const local = durable || row?.video_url;
  if (local && local.startsWith("/api/media/videos/")) return mediaUrl(local);
  return null;
};

/**
 * A same-origin URL that saves the clip as a file.
 *
 * The playback href cannot be reused directly. A durable clip usually lives in
 * R2, so `r2_url` is an ABSOLUTE cross-origin URL, and browsers ignore the
 * `download` attribute on cross-origin hrefs -- the button opened the video in
 * a tab instead of saving it. `playback_url` is the signed same-origin app
 * route, which is always preferred here for that reason.
 *
 * The signature is minted server-side from MEDIA_URL_SECRET and cannot be
 * computed in the browser, so the signed path is reused and `/download` is
 * spliced in ahead of the query string rather than re-signed here.
 *
 * Returns null when there is no playable same-origin source, so a caller can
 * omit the button rather than offer one that cannot save.
 */
export const downloadMediaUrl = (row) => {
  const signed = row?.playback_url;
  if (signed) return mediaUrl(signed.replace(/(\.mp4)(\?|$)/, "$1/download$2"));
  const durable = durableMediaUrl(row);
  if (durable && durable.startsWith("/api/media/videos/")) {
    return durable.replace(/(\.mp4)(\?|$)/, "$1/download$2");
  }
  return null;
};

const client = axios.create({ baseURL: API, timeout: 120000 });

/**
 * The session token source, registered once from inside <ClerkProvider> (see
 * components/auth/AuthTokenBridge.jsx). A module slot rather than an import of
 * Clerk state, because this module must stay usable in no-auth mode where no
 * provider exists at all.
 *
 * The registered function receives whatever options object the caller passes
 * through, so the 401 path below can force a fresh token with
 * `{ skipCache: true }` using the same source as the first attempt.
 */
let getTokenFn = null;

export function setAuthTokenProvider(fn) {
  getTokenFn = typeof fn === "function" ? fn : null;
}

async function currentToken(forceFresh = false) {
  const opts = forceFresh ? { skipCache: true } : undefined;
  if (getTokenFn) {
    try {
      const t = await getTokenFn(opts);
      if (t) return t;
    } catch {
      // Fall through to the legacy global read below.
    }
  }
  try {
    const clerk = typeof window !== "undefined" ? window.Clerk : null;
    if (clerk && clerk.session) {
      const t = await clerk.session.getToken();
      if (t) return t;
    }
  } catch (e) {
    console.warn("Failed to attach auth token:", e);
  }
  return null;
}

/**
 * Attach the Clerk session JWT to every outgoing request.
 *
 * If no token is available the request goes out without one. In no-auth mode
 * the backend files everything under "anonymous" and that is correct; when
 * auth is configured the backend answers 401, which the response interceptor
 * below handles — never the page-level `.catch(() => setX([]))` handlers.
 */
client.interceptors.request.use(async (config) => {
  const token = await currentToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * A 401 must never resolve as data.
 *
 * The failure this exists for: a request goes out with a stale or missing
 * token (transient refresh failure, expired session mid-use), the backend
 * answers 401, and the page's error handler converts it to an empty list —
 * so a profile that exists renders as "no apps". First the request is
 * retried once with a forced-fresh token, which heals the transient case
 * invisibly. If that still 401s the session is dead: when the request had
 * actually attempted authentication, the user is sent to sign in again
 * instead of staring at someone else's (empty) state. Requests that carried
 * no credentials — public endpoints, no-auth mode — are left alone so a
 * marketing visitor is never bounced to sign-in by a backend misconfiguration.
 */
client.interceptors.response.use(
  (response) => response,
  async (err) => {
    const config = err?.config;
    const status = err?.response?.status;
    if (!config || !shouldRetryWithFreshToken({ status, alreadyRetried: config._authRetried })) {
      throw err;
    }
    config._authRetried = true;
    const fresh = await currentToken(true);
    if (fresh) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${fresh}`;
      return client(config);
    }
    const attemptedAuth = Boolean(
      config.headers && config.headers.Authorization
    );
    if (
      shouldForceSignIn({
        attemptedAuth,
        clerkConfigured: isClerkConfigured,
        pathname:
          typeof window !== "undefined" ? window.location.pathname : "",
      })
    ) {
      window.location.href = "/sign-in";
    }
    throw err;
  }
);

export const api = {
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
  // Per-template view aggregates from the founder's own manual numbers. Read
  // only, no video text or source URL, and manual entries only.
  getProfileWhatWorks: (id) =>
    client.get(`/app-profiles/${id}/what-works`).then((r) => r.data),
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

  // Hook templates. The standalone library is gone: the wizard picks from
  // profile-scoped recommendations. Only the read endpoints the wizard needs
  // survive here.
  getTemplates: (params = {}) => client.get("/templates", { params }).then((r) => r.data),
  getTemplateFacets: () => client.get("/templates/facets").then((r) => r.data),

  // Template recommendations
  getTemplateRecommendations: (profileId, params = {}) =>
    client.get(`/app-profiles/${profileId}/template-recommendations`, { params }).then((r) => r.data),
  // Tailored templates for one profile + objective. Called when the template
  // step loads (fast on cache hit) and on explicit regenerate.
  ensureObjectiveTemplates: (profileId, payload) =>
    client.post(`/app-profiles/${profileId}/objective-templates`, payload).then((r) => r.data),

  // Studio projects (guided creation)
  getStudioProjects: (params = {}) => client.get("/studio/projects", { params }).then((r) => r.data),
  getStudioProject: (id) => client.get(`/studio/projects/${id}`).then((r) => r.data),
  createStudioProject: (payload) => client.post("/studio/projects", payload).then((r) => r.data),
  updateStudioProject: (id, payload) => client.patch(`/studio/projects/${id}`, payload).then((r) => r.data),
  generatePlan: (id, payload = {}) => client.post(`/studio/projects/${id}/plan`, payload).then((r) => r.data),
  markProjectReady: (id) => client.post(`/studio/projects/${id}/ready`).then((r) => r.data),
  // `duration_seconds` is not sent from here. The length is computed — a template
  // declares a `default_duration` and the project seeds from it — and the plan
  // step clamps the beats it writes to whatever the project already holds.
  // `setProjectExtendIntent` used to sit beside this: the column survives in
  // SQLite but is written nowhere and read by nothing, so a method that patched
  // it would look like it did something and change nothing.
  //
  // `setProjectHookLength` went for a different reason. It was already dead, and
  // the hook boundary is the template's call: the clamp behind it is a safety
  // net for a hand-typed value, not a control the product offers.

  // Video generation. ONE request renders the whole piece — a hook and a middle
  // — in a single pass, and the server answers 400 for a duration past the
  // model's single-pass ceiling rather than splitting or shortening it. There is
  // no `duration_plan` in the response any more, because there is no plan to
  // return: nothing is left to do after this render except the founder's own
  // demo and call to action.
  getStudioVideoModels: () => client.get("/studio/video-models").then((r) => r.data),
  generateVideo: (projectId, payload = {}) =>
    client.post(`/studio/projects/${projectId}/generate`, payload).then((r) => r.data),
  getGenerations: (params = {}) => client.get("/generations", { params }).then((r) => r.data),
  getGeneration: (id) => client.get(`/generations/${id}`).then((r) => r.data),
  pollGeneration: (id) => client.post(`/generations/${id}/poll`).then((r) => r.data),
  retryGeneration: (id) => client.post(`/generations/${id}/retry`).then((r) => r.data),
  retryGenerationStorage: (id) =>
    // Not a bare re-upload: when the provider download was what failed there is
    // no local file left, so this re-fetches, trims, rescales and uploads. That
    // is a full render's worth of transfer, comfortably past the 120s default —
    // and a client-side abort would leave the server working on a repair the
    // founder was already told had failed.
    client.post(`/generations/${id}/storage/retry`, null, { timeout: 600000 })
      .then((r) => r.data),
  archiveGeneration: (id) => client.post(`/generations/${id}/archive`).then((r) => r.data),

  // App-specific creative direction for the one render.
  //
  // Free — text only, no video. What is left of the old
  // strategy -> hook -> approve -> extend -> assemble chain is this and the
  // single generate above. `generateHook`, `approveGeneration`,
  // `extendGeneration`, `assembleChain` and `getGenerationContinuity` are gone
  // from the server and gone here: a hook-only render, a per-segment approval
  // gate, a repeatable extension, a join, and a seam-continuity readout were
  // five ways of describing a workflow that no longer exists, and every one of
  // them was a button a founder could click to start a render.
  generateStrategy: (id, payload = {}) =>
    client.post(`/studio/projects/${id}/strategy`, payload).then((r) => r.data),

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

  // Native Product Demo + CTA export. The editor lives inside HookForge, so the
  // finished clip is posted as multipart from the same origin. FormData is
  // passed straight through: the client sets the boundary itself, and setting
  // it by hand is what breaks.
  //
  // `generationId` is optional. With one, the export is filed beside that render
  // and inherits its lineage; without one it is saved as a standalone clip, which
  // is the bring-your-own-footage path through the editor.
  saveDemoCtaExport: (generationId, blob, filename = "demo-cta.mp4") => {
    const form = new FormData();
    form.append("file", blob, filename);
    const path = generationId
      ? `/generations/${generationId}/demo-cta-result`
      : "/demo-cta-result";
    return client.post(path, form).then((r) => r.data);
  },

  // History + manual performance
  getGenerationHistory: (params = {}) =>
    client.get("/history/generations", { params }).then((r) => r.data),
  deleteGeneration: (id) => client.delete(`/generations/${id}`).then((r) => r.data),
  getPerformance: (id) => client.get(`/generations/${id}/performance`).then((r) => r.data),
  recordPerformance: (id, payload) =>
    client.post(`/generations/${id}/performance`, payload).then((r) => r.data),

  // Feedback
  getFeedbackCatalog: () => client.get("/feedback/catalog").then((r) => r.data),
  recordFeedback: (payload) => client.post("/feedback", payload).then((r) => r.data),
  getFeedback: (params = {}) => client.get("/feedback", { params }).then((r) => r.data),
};

/**
 * The message to show for a failed request.
 *
 * The rule lives in lib/errorMessage.js so it can be asserted directly rather
 * than through a duplicated copy in a test harness.
 */
export const getErrorMessage = (err) => errorMessageFor(err);
