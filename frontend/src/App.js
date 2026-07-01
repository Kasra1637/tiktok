import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import AppShell from "./components/AppShell";
import NicheFeed from "./pages/NicheFeed";
import AnalysisDetail from "./pages/AnalysisDetail";
import Customize from "./pages/Customize";
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
          <Route path="/history" element={<History />} />
        </Routes>
      </AppShell>
      <Toaster />
    </BrowserRouter>
  );
}

export default App;
