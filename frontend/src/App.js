import "./App.css";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import AppShell from "./components/AppShell";
import PageTransition from "./components/PageTransition";
import NicheFeed from "./pages/NicheFeed";
import AnalysisDetail from "./pages/AnalysisDetail";
import GenerateVideo from "./pages/GenerateVideo";
import History from "./pages/History";
import BrandSetup from "./pages/BrandSetup";
import FaceSwap from "./pages/FaceSwap";

// Redirect old /customize/:videoId to /face-swap (with videoId so it can load analysis)
function CustomizeRedirect() {
  const { videoId } = useParams();
  return <Navigate to={`/face-swap?videoId=${videoId}`} replace />;
}

function App() {
  return (
    <BrowserRouter>
      <div className="noise-overlay" />
      <AppShell>
        <PageTransition>
          <Routes>
            <Route path="/" element={<NicheFeed />} />
            <Route path="/face-swap" element={<FaceSwap />} />
            <Route path="/analysis/:videoId" element={<AnalysisDetail />} />
            <Route path="/customize/:videoId" element={<CustomizeRedirect />} />
            <Route path="/generate-video/:customizationId" element={<GenerateVideo />} />
            <Route path="/history" element={<History />} />
            <Route path="/brand" element={<BrandSetup />} />
          </Routes>
        </PageTransition>
      </AppShell>
      <Toaster />
    </BrowserRouter>
  );
}

export default App;
