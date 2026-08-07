import "./App.css";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import AppShell from "./components/AppShell";
import PageTransition from "./components/PageTransition";
import Landing from "./pages/Landing";
import Privacy from "./pages/Privacy";
import Terms from "./pages/Terms";
import NicheFeed from "./pages/NicheFeed";
import AnalysisDetail from "./pages/AnalysisDetail";
import GenerateVideo from "./pages/GenerateVideo";
import History from "./pages/History";
import BrandSetup from "./pages/BrandSetup";
import FaceSwap from "./pages/FaceSwap";
import HookTemplates from "./pages/HookTemplates";
import { OnboardingProvider } from "./components/onboarding/OnboardingProvider";

// Redirect old /customize/:videoId to /face-swap
function CustomizeRedirect() {
  const { videoId } = useParams();
  return <Navigate to={`/face-swap?videoId=${videoId}`} replace />;
}

function App() {
  return (
    <BrowserRouter>
      <div className="noise-overlay" />
      <OnboardingProvider>
        <Routes>
          {/* Landing + legal pages — no AppShell wrapper */}
          <Route path="/" element={<Landing />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/terms" element={<Terms />} />

          {/* App pages — wrapped in AppShell */}
          <Route path="/*" element={
            <AppShell>
              <PageTransition>
                <Routes>
                  <Route path="/discover" element={<NicheFeed />} />
                  <Route path="/face-swap" element={<FaceSwap />} />
                  <Route path="/analysis/:videoId" element={<AnalysisDetail />} />
                  <Route path="/customize/:videoId" element={<CustomizeRedirect />} />
                  <Route path="/generate-video/:customizationId" element={<GenerateVideo />} />
                  <Route path="/templates" element={<HookTemplates />} />
                  <Route path="/history" element={<History />} />
                  <Route path="/brand" element={<BrandSetup />} />
                </Routes>
              </PageTransition>
            </AppShell>
          } />
        </Routes>
      </OnboardingProvider>
      <Toaster />
    </BrowserRouter>
  );
}

export default App;
