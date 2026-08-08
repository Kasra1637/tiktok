import "./App.css";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import { ClerkProvider } from "@clerk/clerk-react";
import { Toaster } from "./components/ui/sonner";
import AppShell from "./components/AppShell";
import PageTransition from "./components/PageTransition";
import ProtectedRoute from "./components/ProtectedRoute";
import Landing from "./pages/Landing";
import Privacy from "./pages/Privacy";
import Terms from "./pages/Terms";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import NicheFeed from "./pages/NicheFeed";
import AnalysisDetail from "./pages/AnalysisDetail";
import GenerateVideo from "./pages/GenerateVideo";
import History from "./pages/History";
import BrandSetup from "./pages/BrandSetup";
import FaceSwap from "./pages/FaceSwap";
import HookTemplates from "./pages/HookTemplates";
import { OnboardingProvider } from "./components/onboarding/OnboardingProvider";

const CLERK_PUBLISHABLE_KEY = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;

if (!CLERK_PUBLISHABLE_KEY) {
  console.warn(
    "REACT_APP_CLERK_PUBLISHABLE_KEY is not set. " +
    "Authentication will not work until you add it to your .env file. " +
    "Get it from https://dashboard.clerk.com → API Keys."
  );
}

// Redirect old /customize/:videoId to /face-swap
function CustomizeRedirect() {
  const { videoId } = useParams();
  return <Navigate to={`/face-swap?videoId=${videoId}`} replace />;
}

function App() {
  return (
    <ClerkProvider
      publishableKey={CLERK_PUBLISHABLE_KEY || "pk_test_placeholder"}
      afterSignOutUrl="/"
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
    >
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

            {/* Authenticated app pages — wrapped in ProtectedRoute + AppShell */}
            <Route path="/*" element={
              <ProtectedRoute>
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
              </ProtectedRoute>
            } />
          </Routes>
        </OnboardingProvider>
        <Toaster />
      </BrowserRouter>
    </ClerkProvider>
  );
}

export default App;
