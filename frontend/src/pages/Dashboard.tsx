import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getTasks, getImages } from '../api/client';
import type { TaskInfo } from '../types';
import { FolderKanban, CheckCircle2, Image as ImageIcon, ChevronRight, Activity } from 'lucide-react';

export function Dashboard() {
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [progress, setProgress] = useState<Record<string, { approved: number; total: number }>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const taskList = await getTasks();
        setTasks(taskList);
        
        const progressData: Record<string, { approved: number; total: number }> = {};
        for (const task of taskList) {
          const images = await getImages(task.id);
          progressData[task.id] = {
            total: images.length,
            approved: images.filter(img => img.is_approved).length
          };
        }
        setProgress(progressData);
      } catch (error) {
        console.error("Failed to load dashboard data", error);
      } finally {
        setLoading(false);
      }
    }
    
    void loadData();
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-background text-on-background">
      {/* Dashboard Top Navbar */}
      <header className="bg-surface-container border-b border-outline-variant h-toolbar-height flex justify-between items-center px-gutter z-50 flex-shrink-0 select-none">
        <div className="flex items-center gap-4 h-full">
          <div className="text-headline-sm font-headline-sm font-bold bg-gradient-to-r from-primary to-primary-container bg-clip-text text-transparent whitespace-nowrap drop-shadow-[0_0_8px_rgba(45,212,191,0.2)]">
            Image Annotator
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto relative">
        {/* Subtle background glow effect */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-64 bg-primary/5 blur-[120px] rounded-full pointer-events-none -z-10" />

        <div className="max-w-6xl mx-auto p-8 md:p-12">
          <div className="mb-12 text-center md:text-left">
            <h1 className="font-headline-lg text-[2.5rem] font-bold text-on-surface mb-3 tracking-tight">
              Active Tasks
            </h1>
            <p className="font-body-lg text-lg text-on-surface-variant max-w-2xl">
              Select a task below to continue labeling and refining your object detection datasets.
            </p>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-surface-container-low border border-outline-variant rounded-2xl p-6 h-64 flex flex-col justify-between animate-pulse">
                  <div className="space-y-4">
                    <div className="flex justify-between">
                      <div className="w-3/5 h-6 bg-surface-container-highest rounded-md" />
                      <div className="w-16 h-6 bg-surface-container-highest rounded-md" />
                    </div>
                    <div className="flex gap-2">
                      <div className="w-16 h-5 bg-surface-container-highest rounded-full" />
                      <div className="w-20 h-5 bg-surface-container-highest rounded-full" />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="w-full h-2 bg-surface-container-highest rounded-full" />
                    <div className="w-24 h-4 bg-surface-container-highest rounded-md" />
                  </div>
                </div>
              ))}
            </div>
          ) : tasks.length === 0 ? (
             <div className="flex flex-col items-center justify-center py-20 px-4 border border-dashed border-outline-variant rounded-2xl bg-surface-container-low/50">
               <FolderKanban className="text-on-surface-variant/50 w-16 h-16 mb-4" />
               <h3 className="text-headline-sm text-on-surface mb-2">No Projects Found</h3>
               <p className="text-body-md text-on-surface-variant">Update your config.yaml and restart the server to see projects here.</p>
             </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {tasks.map(task => {
                const prog = progress[task.id] || { total: 0, approved: 0 };
                const percent = prog.total > 0 ? Math.round((prog.approved / prog.total) * 100) : 0;
                const isComplete = percent === 100 && prog.total > 0;
                
                return (
                  <Link 
                    key={task.id}
                    to={`/task/${task.id}`}
                    className="block relative bg-surface-container-low border border-outline-variant rounded-2xl p-6 hover:bg-surface-container hover:border-primary/50 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)] hover:shadow-primary/10 hover:-translate-y-1 transition-all duration-300 group overflow-hidden"
                  >
                    {/* Hover Glow Background */}
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />

                    <div className="relative z-10 flex flex-col h-full justify-between">
                      <div>
                        <div className="flex justify-between items-start mb-4">
                          <h2 className="font-headline-sm text-xl font-bold text-on-surface group-hover:text-primary transition-colors pr-2 flex items-center gap-2">
                            <FolderKanban size={20} className="text-primary opacity-80" />
                            {task.name}
                          </h2>
                          {prog.total > 0 && (
                          <div className="bg-surface-container-highest px-2.5 py-1 rounded-md text-label-sm font-medium text-on-surface-variant flex items-center gap-1.5 flex-shrink-0 border border-outline-variant/50">
                            <ImageIcon size={14} />
                            {prog.total}
                          </div>
                          )}
                        </div>
                        
                        <div className="flex flex-wrap gap-2 mb-8">
                          {Object.values(task.class_names).map((className, idx) => (
                            <span 
                              key={idx}
                              className="text-[11px] font-medium tracking-wide uppercase bg-background text-on-surface-variant px-2.5 py-1 rounded-full border border-outline-variant/60 shadow-sm"
                            >
                              {className}
                            </span>
                          ))}
                        </div>
                      </div>
                      
                      {prog.total > 0 ? (
                      <div className="mt-auto">
                        <div className="flex justify-between text-label-sm mb-2 items-center">
                          <span className="text-on-surface-variant flex items-center gap-1.5">
                            {isComplete ? (
                              <><CheckCircle2 size={14} className="text-primary" /> Completed</>
                            ) : (
                              <><Activity size={14} /> Progress</>
                            )}
                          </span>
                          <span className={`font-bold ${isComplete ? 'text-primary' : 'text-on-surface'}`}>
                            {percent}%
                          </span>
                        </div>
                        
                        <div className="h-2 bg-surface-container-highest rounded-full overflow-hidden shadow-inner">
                          <div 
                            className={`h-full rounded-full transition-all duration-1000 ease-out relative ${
                              isComplete ? 'bg-primary' : 'bg-gradient-to-r from-primary to-primary-container'
                            }`}
                            style={{ width: `${percent}%` }}
                          >
                            {/* Inner glow for the progress bar */}
                            <div className="absolute inset-0 bg-white/20 w-full h-full rounded-full" />
                          </div>
                        </div>
                        
                        <div className="mt-4 flex justify-between items-center">
                          <div className="text-label-sm text-on-surface-variant font-medium">
                            <span className={isComplete ? 'text-primary' : 'text-on-surface'}>{prog.approved}</span> / {prog.total} Approved
                          </div>
                          <div className="text-primary opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 transition-all duration-300">
                            <ChevronRight size={18} />
                          </div>
                        </div>
                      </div>
                      ) : (
                        <div className="mt-auto flex justify-between items-end">
                          <div className="text-label-sm text-on-surface-variant font-medium italic">
                            No images uploaded yet.
                          </div>
                          <div className="text-primary opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 transition-all duration-300">
                            <ChevronRight size={18} />
                          </div>
                        </div>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
