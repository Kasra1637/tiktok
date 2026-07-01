import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import AppShell from "./components/AppShell";
import NicheFeed from "./pages/NicheFeed";
import AnalysisDetail from "./pages/AnalysisDetail";
import Customize from "./pages/Customize";
import GenerateVideo from "./pages/GenerateVideo";
import History from "./pages/History";

function App() {
  return (
    <BrowserRouter>
      <div className="noise-overlay" />
      <AppShell>
        <Routes>
          <Route path="/" element={<NicheFeed />} />
          <Route path="/analysis/:videoId" element={<AnalysisDetail />} />
          <Route path="/customize/:videoId" element={<Customize />} />
          <Route path="/generate-video/:customizationId" element={<GenerateVideo />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </AppShell>
      <Toaster />
    </BrowserRouter>
  );
}

export default App;
