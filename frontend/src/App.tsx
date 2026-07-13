import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Dashboard } from './pages/Dashboard';
import { Workspace } from './pages/Workspace';

const VideoProjects = lazy(() => import('./pages/VideoProjects').then((module) => ({ default: module.VideoProjects })));
const VideoWorkspace = lazy(() => import('./pages/VideoWorkspace').then((module) => ({ default: module.VideoWorkspace })));

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/task/:taskId" element={<Workspace />} />
        <Route path="/video" element={<Suspense fallback={<div className="min-h-screen bg-background text-on-background p-8">Loading video projects…</div>}><VideoProjects /></Suspense>} />
        <Route path="/video/:projectId" element={<Suspense fallback={<div className="min-h-screen bg-background text-on-background p-8">Loading video workspace…</div>}><VideoWorkspace /></Suspense>} />
      </Routes>
    </BrowserRouter>
  );
}
