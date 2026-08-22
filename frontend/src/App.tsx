import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Dashboard } from './pages/Dashboard';
import { Workspace } from './pages/Workspace';

const VideoProjects = lazy(() => import('./pages/VideoProjects').then((module) => ({ default: module.VideoProjects })));
const VideoWorkspace = lazy(() => import('./pages/VideoWorkspace').then((module) => ({ default: module.VideoWorkspace })));
const BehaviorHome = lazy(() => import('./pages/BehaviorHome').then((module) => ({ default: module.BehaviorHome })));
const BehaviorInference = lazy(() => import('./pages/BehaviorInference').then((module) => ({ default: module.BehaviorInference })));

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/task/:taskId" element={<Workspace />} />
        <Route path="/behavior" element={<Suspense fallback={<div className="min-h-screen bg-background p-8">Loading behavior tools…</div>}><BehaviorHome /></Suspense>} />
        <Route path="/behavior/inference" element={<Suspense fallback={<div className="min-h-screen bg-background p-8">Loading inference…</div>}><BehaviorInference /></Suspense>} />
        <Route path="/video" element={<Suspense fallback={<div className="min-h-screen bg-background text-on-background p-8">Loading video projects…</div>}><VideoProjects /></Suspense>} />
        <Route path="/video/:projectId" element={<Suspense fallback={<div className="min-h-screen bg-background text-on-background p-8">Loading video workspace…</div>}><VideoWorkspace /></Suspense>} />
      </Routes>
    </BrowserRouter>
  );
}
