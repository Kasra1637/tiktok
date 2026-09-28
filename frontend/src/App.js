import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
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
import AppProfiles from "./pages/AppProfiles";
import AppProfileDetail from "./pages/AppProfileDetail";
import Templates from "./pages/Templates";
import TemplateDetail from "./pages/TemplateDetail";
import CreateVideo from "./pages/CreateVideo";
import AssetLibrary from "./pages/AssetLibrary";
import Dashboard from "./pages/Dashboard";
import Analytics from "./pages/Analytics";
import Operations from "./pages/Operations";
import TrendResearch from "./pages/TrendResearch";
import Settings from "./pages/Settings";
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
                        <Route path="/app-profiles" element={<AppProfiles />} />
                        <Route path="/app-profiles/:profileId" element={<AppProfileDetail />} />
                        <Route path="/app-profiles/:profileId/assets" element={<AssetLibrary />} />
                        <Route path="/assets" element={<AssetLibrary />} />
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/analytics" element={<Analytics />} />
                        <Route path="/operations" element={<Operations />} />
                        <Route path="/research" element={<TrendResearch />} />
                        <Route path="/settings" element={<Settings />} />
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
