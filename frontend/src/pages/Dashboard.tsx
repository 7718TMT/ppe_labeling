import { useEffect, useState } from 'react';
import { Activity, CheckCircle2, ChevronRight, HardHat, ShieldAlert, Video } from 'lucide-react';
import { Link } from 'react-router-dom';

import { getImages, getTasks } from '../api/client';

interface ModuleProgress {
  approved: number;
  total: number;
}

const MODULES = [
  {
    id: 'ppe',
    title: 'PPE',
    kind: 'Image labeling',
    description: 'Label workers and personal protective equipment in factory images.',
    path: '/task/ppe',
    icon: HardHat,
  },
  {
    id: 'safety_signs',
    title: 'Sign',
    kind: 'Image labeling',
    description: 'Label workplace safety signs in factory images.',
    path: '/task/safety_signs',
    icon: ShieldAlert,
  },
  {
    id: 'pose',
    title: 'Behavior',
    kind: 'Video labeling',
    description: 'Review worker tracks and label falling, running, or other behavior.',
    path: '/video',
    icon: Video,
  },
] as const;

export function Dashboard() {
  const [progress, setProgress] = useState<Record<string, ModuleProgress>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadProgress() {
      try {
        const tasks = await getTasks();
        const entries = await Promise.all(
          tasks.map(async (task) => {
            const images = await getImages(task.id);
            return [
              task.id,
              {
                total: images.length,
                approved: images.filter((image) => image.is_approved).length,
              },
            ] as const;
          }),
        );

        if (active) {
          setProgress(Object.fromEntries(entries));
        }
      } catch (error) {
        console.error('Failed to load dashboard progress', error);
        if (active) {
          setLoadError(true);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadProgress();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-background text-on-background">
      <header className="flex h-toolbar-height flex-shrink-0 items-center justify-between border-b border-outline-variant bg-surface-container px-gutter z-50 select-none">
        <div className="text-headline-sm font-headline-sm font-bold bg-gradient-to-r from-primary to-primary-container bg-clip-text text-transparent whitespace-nowrap drop-shadow-[0_0_8px_rgba(45,212,191,0.2)]">
          Smart Factory Annotation Tool
        </div>
        <span className="font-label text-label-sm text-on-surface-variant">
          PPE · Sign · Behavior
        </span>
      </header>

      <main className="relative flex-1 overflow-y-auto">
        <div className="pointer-events-none absolute left-1/2 top-0 -z-10 h-64 w-3/4 -translate-x-1/2 rounded-full bg-primary/5 blur-[120px]" />

        <div className="mx-auto max-w-6xl p-8 md:p-12">
          <div className="mb-10 text-center md:text-left">
            <p className="mb-2 font-label text-label-caps uppercase text-primary">
              Labeling modules
            </p>
            <h1 className="mb-3 font-headline-lg text-[2.5rem] font-bold tracking-tight text-on-surface">
              Choose what you want to label
            </h1>
            <p className="max-w-2xl font-body-lg text-lg text-on-surface-variant">
              PPE, safety signs, and worker pose videos are available from this single workspace.
            </p>
          </div>

          {loadError && (
            <div
              role="status"
              className="mb-5 rounded border border-outline-variant bg-surface-container-low px-4 py-3 text-body-md text-on-surface-variant"
            >
              Dataset progress is temporarily unavailable. You can still open any labeling module.
            </div>
          )}

          <section aria-label="Labeling modules" className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {MODULES.map((module) => {
              const Icon = module.icon;
              const moduleProgress = progress[module.id];
              const percent = moduleProgress?.total
                ? Math.round((moduleProgress.approved / moduleProgress.total) * 100)
                : 0;
              const isComplete = Boolean(moduleProgress?.total) && percent === 100;

              return (
                <Link
                  key={module.id}
                  to={module.path}
                  aria-label={`Open ${module.title} labeling`}
                  className="group relative flex min-h-64 flex-col overflow-hidden rounded-lg border border-outline-variant bg-surface-container-low p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/60 hover:bg-surface-container focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

                  <div className="relative z-10 flex h-full flex-col">
                    <div className="mb-5 flex items-start justify-between">
                      <div className="flex h-12 w-12 items-center justify-center rounded bg-primary/10 text-primary">
                        <Icon aria-hidden="true" size={24} />
                      </div>
                      <span className="rounded-sm border border-outline-variant bg-surface-container-high px-2 py-1 font-label text-label-sm text-on-surface-variant">
                        {module.kind}
                      </span>
                    </div>

                    <h2 className="mb-2 font-headline-sm text-2xl font-semibold text-on-surface transition-colors group-hover:text-primary">
                      {module.title}
                    </h2>
                    <p className="font-body-md text-on-surface-variant">
                      {module.description}
                    </p>

                    <div className="mt-auto pt-8">
                      {module.id === 'pose' ? (
                        <div className="flex items-center justify-between border-t border-outline-variant pt-4 font-label text-label-sm">
                          <span className="text-on-surface-variant">Open video projects</span>
                          <ChevronRight className="text-primary transition-transform group-hover:translate-x-1" size={18} />
                        </div>
                      ) : loading ? (
                        <div className="space-y-2" aria-label={`Loading ${module.title} progress`}>
                          <div className="h-2 w-full animate-pulse rounded-full bg-surface-container-highest" />
                          <div className="h-4 w-28 animate-pulse rounded bg-surface-container-highest" />
                        </div>
                      ) : moduleProgress?.total ? (
                        <>
                          <div className="mb-2 flex items-center justify-between font-label text-label-sm">
                            <span className="flex items-center gap-1.5 text-on-surface-variant">
                              {isComplete ? (
                                <CheckCircle2 className="text-primary" size={14} />
                              ) : (
                                <Activity size={14} />
                              )}
                              {isComplete ? 'Completed' : 'Annotation progress'}
                            </span>
                            <span className={isComplete ? 'font-bold text-primary' : 'font-bold text-on-surface'}>
                              {percent}%
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-surface-container-highest">
                            <div
                              className="h-full rounded-full bg-primary transition-[width] duration-500"
                              style={{ width: `${percent}%` }}
                            />
                          </div>
                          <div className="mt-3 flex items-center justify-between font-label text-label-sm text-on-surface-variant">
                            <span>{moduleProgress.approved} / {moduleProgress.total} approved</span>
                            <ChevronRight className="text-primary transition-transform group-hover:translate-x-1" size={18} />
                          </div>
                        </>
                      ) : (
                        <div className="flex items-center justify-between border-t border-outline-variant pt-4 font-label text-label-sm">
                          <span className="text-on-surface-variant">No images yet</span>
                          <ChevronRight className="text-primary transition-transform group-hover:translate-x-1" size={18} />
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </section>
        </div>
      </main>
    </div>
  );
}
