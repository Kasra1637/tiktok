import "./App.css";
import { Suspense, lazy, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import AppShell from "./components/AppShell";
import PageTransition from "./components/PageTransition";
import { Skeleton } from "./components/ui/skeleton";
import ProtectedRoute from "./components/ProtectedRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import AuthProvider from "./components/auth/AuthProvider";
import Landing from "./pages/Landing";
import Features from "./pages/Features";
import Privacy from "./pages/Privacy";
import Terms from "./pages/Terms";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
// The dashboard pages are the heavy half of the app (CreateVideo alone is
// thousands of lines, all eager before this change), so each rides its own
// lazy chunk: the landing page and auth gates never download them, and
// navigating between pages only fetches the one opened. Public pages stay
// eager — they are light and most visits start there.
const GenerationHistory = lazy(() => import("./pages/GenerationHistory"));
const BrandSetup = lazy(() => import("./pages/BrandSetup"));
const AppProfileDetail = lazy(() => import("./pages/AppProfileDetail"));
const CreateVideo = lazy(() => import("./pages/CreateVideo"));
const AssetLibrary = lazy(() => import("./pages/AssetLibrary"));
const Analytics = lazy(() => import("./pages/Analytics"));
// Split out of the landing chunk: the editor pulls in mediabunny, which the
// landing page must never download. Both /demo-cta routes resolve through
// this one component, so one lazy boundary covers them.
const DemoCtaStudio = lazy(() => import("./pages/DemoCtaStudio"));
// Video Upscaler is a separate lazy chunk for the same reason: it pulls in
// mediabunny, which the landing page must never download.
const VideoUpscaler = lazy(() => import("./pages/VideoUpscaler"));
import { OnboardingProvider } from "./components/onboarding/OnboardingProvider";
import { initVitals } from "./lib/vitals";

// The editor chunk is fetched on first navigation here, so the fallback
// mirrors the editor layout with shimmer skeletons — the same loading
// language every other page speaks — rather than a static line. Shared by
// both /demo-cta routes: only one can match at a time, so one element
// covers them.
function EditorLoading() {
  return (
    <div
      className="grid items-start gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.3fr)] xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)]"
      role="status"
      aria-label="Loading the editor"
    >
      <div className="space-y-3">
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-10 w-2/3 rounded-xl" />
      </div>
      <div className="space-y-3">
        <Skeleton className="aspect-[9/16] w-full max-w-sm rounded-xl" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <span className="sr-only">Loading the editor…</span>
    </div>
  );
}
const editorElement = (
  <Suspense fallback={<EditorLoading />}>
    <DemoCtaStudio />
  </Suspense>
);
// Neutral loading language for the lazy dashboard pages: the editor gets its
// own layout-mirroring fallback above, everything else gets shimmer blocks.
function PageLoading() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading the page">
      <Skeleton className="h-10 w-1/3 rounded-xl" />
      <Skeleton className="h-40 w-full rounded-xl" />
      <Skeleton className="h-24 w-full rounded-xl" />
      <span className="sr-only">Loading…</span>
    </div>
  );
}
function LazyPage({ children }) {
  return <Suspense fallback={<PageLoading />}>{children}</Suspense>;
}

function App() {
  // Real-user timing, once per tab: LCP/INP/CLS via PerformanceObserver,
  // logged in dev and exposed on window for manual profiling. No backend
  // sink and no dependency — the numbers exist to guide the next perf pass,
  // not to surveil founders.
  useEffect(() => {
    initVitals();
  }, []);
  return (
    // ErrorBoundary is the outermost layer on purpose: if anything below it
    // throws (including auth setup), the user gets a readable error screen
    // instead of a blank page.
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <div className="noise-overlay" />
          <OnboardingProvider>
            <Routes>
              {/* Public pages — render immediately, no auth gate */}
              <Route path="/" element={<Landing />} />
              <Route path="/features" element={<Features />} />
              <Route path="/privacy" element={<Privacy />} />
              <Route path="/terms" element={<Terms />} />
              <Route path="/sign-in/*" element={<SignIn />} />
              <Route path="/sign-up/*" element={<SignUp />} />

              {/* Authenticated app pages */}
              <Route path="/*" element={
                <ProtectedRoute>
                  <AppShell>
                    <PageTransition>
                      <Routes>
                        {/* Primary workflow: profiles -> studio */}
                        {/* The App Profiles list is gone: the editor was where
                            you went to do the work anyway. This redirect keeps
                            the public footer, the Dashboard, the studio's
                            "Review and approve", and the profile detail back
                            link all landing somewhere real instead of a 404. */}
                        <Route path="/app-profiles" element={<Navigate to="/brand" replace />} />
                        <Route path="/app-profiles/:profileId" element={<LazyPage><AppProfileDetail /></LazyPage>} />
                        <Route path="/app-profiles/:profileId/assets" element={<LazyPage><AssetLibrary /></LazyPage>} />
                        <Route path="/assets" element={<LazyPage><AssetLibrary /></LazyPage>} />
                        {/* The Dashboard is gone. It restated what Generation
                            History already shows — totals and failed
                            generations with a Retry button — and then linked out
                            to Create Video, App Profiles and Templates, all of
                            which are in the sidebar anyway. "/" now goes where
                            the work is. A redirect rather than a dead route, so
                            the sidebar logo and any bookmark still land somewhere
                            real. The public "/" for signed-out visitors is the
                            landing page, declared above and unaffected. */}
                        <Route path="/" element={<Navigate to="/create" replace />} />
                        {/* Results and what the app learned from them. The page
                            this route used to serve reported what a render cost
                            this operator, and the product stopped metering that,
                            so the route was retired. It is back with a different
                            question: what the founder's own logged results say.
                            That data was already collected and already fed the
                            next strategy — it simply had nowhere to be read. */}
                        <Route path="/analytics" element={<LazyPage><Analytics /></LazyPage>} />
                        {/* The template library is gone: templates are picked
                            per App Profile inside the Create Video wizard, so
                            there is nowhere standalone left to land. Redirects
                            rather than dead routes, so bookmarks land where
                            the work is. */}
                        <Route path="/templates" element={<Navigate to="/create" replace />} />
                        <Route path="/templates/:templateId" element={<Navigate to="/create" replace />} />
                        <Route path="/create" element={<LazyPage><CreateVideo /></LazyPage>} />
                        {/* Native Product Demo + CTA editor. The picker lives at
                            /demo-cta and the editor at /demo-cta/:generationId,
                            so a finished render is the input and the export is
                            saved beside it in History. */}
                        <Route path="/demo-cta" element={editorElement} />
                        <Route path="/demo-cta/:generationId" element={editorElement} />
                        <Route path="/brand" element={<LazyPage><BrandSetup /></LazyPage>} />
                        {/* Standalone client-side upscaler: sub-4K video in, 4K MP4 out. */}
                        <Route path="/upscale" element={(
                          <Suspense fallback={<EditorLoading />}>
                            <VideoUpscaler />
                          </Suspense>
                        )} />
                        {/* Generation History is the history view. */}
                        <Route path="/history" element={<LazyPage><GenerationHistory /></LazyPage>} />
                      </Routes>
                    </PageTransition>
                  </AppShell>
                </ProtectedRoute>
              } />
            </Routes>
          </OnboardingProvider>
          <Toaster />
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
