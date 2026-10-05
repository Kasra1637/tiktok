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
import GenerationHistory from "./pages/GenerationHistory";
import BrandSetup from "./pages/BrandSetup";
import AppProfileDetail from "./pages/AppProfileDetail";
import CreateVideo from "./pages/CreateVideo";
import DemoCtaStudio from "./pages/DemoCtaStudio";
import AssetLibrary from "./pages/AssetLibrary";
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
                        {/* Primary workflow: profiles -> studio */}
                        {/* The App Profiles list is gone: the editor was where
                            you went to do the work anyway. This redirect keeps
                            the public footer, the Dashboard, the studio's
                            "Review and approve", and the profile detail back
                            link all landing somewhere real instead of a 404. */}
                        <Route path="/app-profiles" element={<Navigate to="/brand" replace />} />
                        <Route path="/app-profiles/:profileId" element={<AppProfileDetail />} />
                        <Route path="/app-profiles/:profileId/assets" element={<AssetLibrary />} />
                        <Route path="/assets" element={<AssetLibrary />} />
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
                        {/* Analytics is gone. It reported this operator's own
                            activity and what it cost them, and the product does
                            not meter that. A redirect rather than a dead route,
                            so a bookmark lands where the work is. */}
                        <Route path="/analytics" element={<Navigate to="/create" replace />} />
                        {/* The template library is gone: templates are picked
                            per App Profile inside the Create Video wizard, so
                            there is nowhere standalone left to land. Redirects
                            rather than dead routes, so bookmarks land where
                            the work is. */}
                        <Route path="/templates" element={<Navigate to="/create" replace />} />
                        <Route path="/templates/:templateId" element={<Navigate to="/create" replace />} />
                        <Route path="/create" element={<CreateVideo />} />
                        {/* Native Product Demo + CTA editor. The picker lives at
                            /demo-cta and the editor at /demo-cta/:generationId,
                            so a finished render is the input and the export is
                            saved beside it in History. */}
                        <Route path="/demo-cta" element={<DemoCtaStudio />} />
                        <Route path="/demo-cta/:generationId" element={<DemoCtaStudio />} />
                        <Route path="/brand" element={<BrandSetup />} />
                        {/* Generation History is the history view. */}
                        <Route path="/history" element={<GenerationHistory />} />
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
