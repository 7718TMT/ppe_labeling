import { ArrowRight, ScanSearch, Tags } from 'lucide-react';
import { Link, Navigate, useParams } from 'react-router-dom';

const TASKS = {
  ppe: { id: 'ppe', title: 'PPE', subtitle: 'personal protective equipment', labelingPath: '/task/ppe' },
  sign: { id: 'safety_signs', title: 'Sign', subtitle: 'workplace safety signs', labelingPath: '/task/safety_signs' },
} as const;

export function ImageTaskHome() {
  const { taskKey } = useParams<{ taskKey: string }>();
  const task = taskKey ? TASKS[taskKey as keyof typeof TASKS] : undefined;
  if (!task) return <Navigate to="/" replace />;

  const options = [
    { title: 'Labeling', description: `Create and review ${task.subtitle} annotations.`, path: task.labelingPath, icon: Tags },
    { title: 'Inference', description: 'Upload images or videos and inspect trained-model detections.', path: `/${taskKey}/inference`, icon: ScanSearch },
  ];

  return <div className="min-h-screen bg-background text-on-background">
    <header className="h-toolbar-height bg-surface-container border-b border-outline-variant flex items-center px-gutter gap-3">
      <Link to="/" className="font-bold text-primary">Home</Link>
      <span className="text-on-surface-variant">/</span><span>{task.title}</span>
    </header>
    <main className="max-w-5xl mx-auto p-8 md:p-12">
      <p className="font-label text-label-caps uppercase text-primary">{task.title} detection tools</p>
      <h1 className="mt-2 text-headline-lg font-headline font-semibold">Choose a workflow</h1>
      <p className="mt-2 text-on-surface-variant">Label training data or run the model from the weights directory on new media.</p>
      <div className="grid md:grid-cols-2 gap-5 mt-8">
        {options.map(({ title, description, path, icon: Icon }) => <Link key={title} to={path} aria-label={`Open ${task.title} ${title}`} className="group min-h-56 rounded-lg border border-outline-variant bg-surface-container-low p-6 hover:border-primary/60 hover:-translate-y-0.5 transition-all flex flex-col">
          <div className="w-12 h-12 rounded bg-primary/10 text-primary flex items-center justify-center"><Icon /></div>
          <h2 className="mt-6 text-headline-sm font-semibold">{title}</h2>
          <p className="mt-2 text-on-surface-variant">{description}</p>
          <div className="mt-auto pt-5 flex justify-end text-primary"><ArrowRight className="group-hover:translate-x-1 transition-transform" /></div>
        </Link>)}
      </div>
    </main>
  </div>;
}
