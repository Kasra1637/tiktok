import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import AppShell from "./components/AppShell";
import PageTransition from "./components/PageTransition";
import ProtectedRoute from "./components/ProtectedRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import AuthProvider from "./components/auth/AuthProvider";
import Landing from "./pages/Landing";
import Privacy from "./pages/Privacy";
import Terms from "./pages/Terms";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import NicheFeed from "./pages/NicheFeed";
import AnalysisDetail from "./pages/AnalysisDetail";
import History from "./pages/History";
import GenerationHistory from "./pages/GenerationHistory";
import BrandSetup from "./pages/BrandSetup";
import HookTemplates from "./pages/HookTemplates";
import AppProfileDetail from "./pages/AppProfileDetail";
import Templates from "./pages/Templates";
import TemplateDetail from "./pages/TemplateDetail";
import CreateVideo from "./pages/CreateVideo";
import AssetLibrary from "./pages/AssetLibrary";
import Analytics from "./pages/Analytics";
import TrendResearch from "./pages/TrendResearch";
import { OnboardingProvider } from "./components/onboarding/OnboardingProvider";

function App() {
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
                        {/* Primary workflow: profiles -> templates -> studio (Phase 4) */}
                        {/* The App Profiles list is gone: the editor was where
                            you went to do the work anyway. This redirect keeps
                            the public footer, the Dashboard, the studio's
                            "Review and approve", and the profile detail back
                            link all landing somewhere real instead of a 404. */}
                        <Route path="/app-profiles" element={<Navigate to="/brand" replace />} />
                        <Route path="/app-profiles/:profileId" element={<AppProfileDetail />} />
                        <Route path="/app-profiles/:profileId/assets" element={<AssetLibrary />} />
                        <Route path="/assets" element={<AssetLibrary />} />
                        {/* The Dashboard is gone. It restated what Analytics and
                            History already show — totals, spend, and failed
                            generations with a Retry button — and then linked out
                            to Create Video, App Profiles and Templates, all of
                            which are in the sidebar anyway. "/" now goes where
                            the work is. A redirect rather than a dead route, so
                            the sidebar logo and any bookmark still land somewhere
                            real. The public "/" for signed-out visitors is the
                            landing page, declared above and unaffected. */}
                        <Route path="/" element={<Navigate to="/create" replace />} />
                        <Route path="/analytics" element={<Analytics />} />
                        <Route path="/research" element={<TrendResearch />} />
                        <Route path="/templates" element={<Templates />} />
                        <Route path="/templates/:templateId" element={<TemplateDetail />} />
                        <Route path="/create" element={<CreateVideo />} />
                        <Route path="/brand" element={<BrandSetup />} />
                        {/* Generation History is now the primary /history view;
                            the legacy exact-match history is kept at
                            /legacy-history for the research flow. */}
                        <Route path="/history" element={<GenerationHistory />} />
                        <Route path="/legacy-history" element={<History />} />

                        {/* Research archive: discovery, analysis, bookmarks, and
                            legacy records remain readable, but exact-match
                            video creation is disabled. */}
                        <Route path="/discover" element={<NicheFeed />} />
                        <Route path="/analysis/:videoId" element={<AnalysisDetail />} />
                        <Route path="/bookmarks" element={<HookTemplates />} />
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
