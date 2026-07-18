import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { NavBar } from "./components/NavBar";
import { Hero } from "./pages/Hero";
import { JDsPage } from "./pages/JDsPage";
import { JDDetailPage } from "./pages/JDDetailPage";
import { ResumesPage } from "./pages/ResumesPage";
import { ResumeDetailPage } from "./pages/ResumeDetailPage";

export default function App() {
  return (
    <HashRouter>
      <NavBar />
      <Routes>
        <Route path="/" element={<Hero />} />
        <Route path="/jds" element={<JDsPage />} />
        <Route path="/jds/:jdId" element={<JDDetailPage />} />
        <Route path="/resumes" element={<ResumesPage />} />
        <Route path="/resumes/:resumeId" element={<ResumeDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}
