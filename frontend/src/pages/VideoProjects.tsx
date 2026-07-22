import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowRight, Plus, Video } from 'lucide-react';

import { createVideoProject, getVideoProjects } from '../api/client';
import type { VideoProject } from '../types';

export function VideoProjects() {
  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { getVideoProjects().then(setProjects).catch((reason) => setError(String(reason))).finally(() => setLoading(false)); }, []);

  async function create() {
    if (!name.trim()) return;
    try {
      const project = await createVideoProject(name.trim());
      setProjects((current) => [project, ...current]);
      setName('');
    } catch (reason) { setError(String(reason)); }
  }

  return (
    <div className="min-h-screen bg-background text-on-background">
      <header className="h-toolbar-height bg-surface-container border-b border-outline-variant flex items-center px-gutter gap-3">
        <Link to="/" className="font-headline-sm font-bold text-primary">Home</Link>
        <span className="text-on-surface-variant">/</span><span>Behavior Video Labeling</span>
      </header>
      <main className="max-w-6xl mx-auto p-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
          <div><p className="font-label text-label-caps uppercase text-primary mb-2">Labeling-only workspace</p><h1 className="text-headline-lg font-headline font-semibold">Behavior Video Projects</h1><p className="text-on-surface-variant mt-2">Frame-accurate worker behavior annotation.</p></div>
          <div className="flex gap-2">
            <label className="sr-only" htmlFor="project-name">Project name</label>
            <input id="project-name" value={name} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void create(); }} placeholder="New project name" className="h-9 w-64 bg-surface-container-lowest border border-outline-variant rounded px-3 focus:border-primary outline-none" />
            <button onClick={() => void create()} className="h-9 px-4 rounded bg-primary-container text-on-primary-container font-label text-label-sm font-bold flex items-center gap-2"><Plus size={16} />Create</button>
          </div>
        </div>
        {error && <div role="alert" className="mb-4 border border-error/40 bg-error-container/30 text-error p-3 rounded">{error}</div>}
        {loading ? <div className="text-on-surface-variant flex items-center gap-2"><Activity className="animate-pulse" />Loading projects…</div> : projects.length === 0 ? (
          <div className="border border-dashed border-outline-variant bg-surface-container-low rounded-lg p-16 text-center"><Video className="mx-auto mb-4 text-on-surface-variant" size={44} /><h2 className="text-headline-sm">No video projects yet</h2><p className="text-on-surface-variant mt-2">Create a project to import videos without a metadata CSV.</p></div>
        ) : <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">{projects.map((project) => (
          <Link key={project.project_id} to={`/video/${project.project_id}`} className="group border border-outline-variant bg-surface-container-low rounded-lg p-5 hover:border-primary/60 transition-colors">
            <div className="flex items-start justify-between"><div className="w-10 h-10 rounded bg-primary/10 text-primary flex items-center justify-center"><Video size={20} /></div><ArrowRight className="text-on-surface-variant group-hover:text-primary" size={18} /></div>
            <h2 className="text-headline-sm font-semibold mt-5">{project.name}</h2><p className="font-label text-label-sm text-on-surface-variant mt-2">Updated {new Date(project.updated_at).toLocaleString()}</p>
          </Link>
        ))}</div>}
      </main>
    </div>
  );
}
