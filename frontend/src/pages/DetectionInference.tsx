import { useEffect, useMemo, useRef, useState } from 'react';
import { FileImage, Film, Image, ScanSearch, Trash2, Upload } from 'lucide-react';
import { Link, Navigate, useParams } from 'react-router-dom';

import { deleteDetectionInferenceItem, getDetectionInferenceItems, getTasks, uploadDetectionInferenceMedia } from '../api/client';
import type { DetectionInferenceItem, TaskInfo } from '../types';

const TASKS = {
  ppe: { id: 'ppe', title: 'PPE', model: 'weights/ppe.pt' },
  sign: { id: 'safety_signs', title: 'Sign', model: 'weights/sign.pt' },
} as const;
type Filter = 'all' | 'image' | 'video';
const DETECTION_COLORS = ['#2dd4bf', '#3b82f6', '#f59e0b', '#ef4444', '#a855f7'];

export function DetectionInference() {
  const { taskKey } = useParams<{ taskKey: string }>();
  const task = taskKey ? TASKS[taskKey as keyof typeof TASKS] : undefined;
  const [items, setItems] = useState<DetectionInferenceItem[]>([]);
  const [taskInfo, setTaskInfo] = useState<TaskInfo>();
  const [activeId, setActiveId] = useState<string>();
  const [filter, setFilter] = useState<Filter>('all');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!task) return;
    let mounted = true;
    void getDetectionInferenceItems(task.id).then((next) => {
      if (!mounted) return;
      setItems(next);
      setActiveId(next[0]?.id);
    }).catch((reason) => mounted && setError(String(reason)));
    return () => { mounted = false; };
  }, [task?.id]);

  useEffect(() => {
    if (!task) return;
    let mounted = true;
    void getTasks().then((tasks) => {
      if (mounted) setTaskInfo(tasks.find((candidate) => candidate.id === task.id));
    }).catch(() => undefined);
    return () => { mounted = false; };
  }, [task?.id]);

  const visible = useMemo(() => items.filter((item) => filter === 'all' || item.media_type === filter), [filter, items]);
  const active = visible.find((item) => item.id === activeId) ?? visible[0];
  if (!task) return <Navigate to="/" replace />;

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true); setError('');
    try {
      const uploaded = await uploadDetectionInferenceMedia(task!.id, Array.from(files));
      setItems((current) => [...uploaded, ...current]);
      setActiveId(uploaded[0]?.id);
      if (input.current) input.current.value = '';
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setUploading(false); }
  }

  async function remove(item: DetectionInferenceItem) {
    if (!window.confirm(`Delete "${item.filename}"?`)) return;
    try {
      await deleteDetectionInferenceItem(task!.id, item.id);
      setItems((current) => current.filter((candidate) => candidate.id !== item.id));
      if (activeId === item.id) setActiveId(undefined);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  return <div className="h-screen flex flex-col bg-background text-on-background">
    <header className="h-toolbar-height shrink-0 bg-surface-container border-b border-outline-variant flex items-center justify-between px-gutter">
      <div className="flex items-center gap-3"><Link to="/" className="font-bold text-primary">Home</Link><span className="text-on-surface-variant">/</span><Link to={`/${taskKey}`} className="hover:text-primary">{task.title}</Link><span className="text-on-surface-variant">/</span><span>Inference</span></div>
      <div className="flex items-center gap-2 font-label text-label-sm text-on-surface-variant"><ScanSearch size={16} className="text-primary" /><span>{task.model}</span></div>
    </header>
    {error && <div role="alert" className="status-message border-b border-error/40 bg-error/10 px-5 py-2 text-sm text-error">{error}</div>}
    <main className="min-h-0 flex-1 flex">
      <aside className="w-72 shrink-0 border-r border-outline-variant bg-surface-container-low flex flex-col">
        <div className="p-4 border-b border-outline-variant">
          <input ref={input} type="file" multiple accept="image/*,video/*" className="hidden" onChange={(event) => void upload(event.target.files)} />
          <button type="button" onClick={() => input.current?.click()} disabled={uploading} className="w-full h-10 rounded bg-primary text-on-primary font-semibold flex items-center justify-center gap-2 hover:bg-primary/90 disabled:opacity-60">
            <Upload size={17} />{uploading ? 'Running inference…' : 'Upload media'}
          </button>
          <p className="mt-2 text-xs text-on-surface-variant">Images and videos are processed with {task.title} detection.</p>
        </div>
        <div className="p-3 border-b border-outline-variant" aria-label="Media filters">
          <p className="px-1 mb-2 text-[10px] uppercase tracking-wider text-on-surface-variant">Filter media</p>
          <div className="grid grid-cols-3 gap-1">
            {([['all', 'All', ScanSearch], ['image', 'Images', Image], ['video', 'Videos', Film]] as const).map(([value, label, Icon]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)} className={`rounded px-2 py-2 text-xs flex flex-col items-center gap-1 border transition-colors ${filter === value ? 'border-primary bg-primary/10 text-primary' : 'border-transparent text-on-surface-variant hover:bg-surface-container-high'}`}><Icon size={16} />{label}</button>)}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-2 space-y-2">
          {visible.map((item) => <div key={item.id} className={`video-card relative rounded border ${active?.id === item.id ? 'video-card-active border-primary bg-primary/5' : 'border-outline-variant bg-surface-container'} `}>
            <button type="button" aria-label={`Open ${item.filename}`} onClick={() => setActiveId(item.id)} className="w-full text-left p-2 pr-9">
              <div className="aspect-video rounded bg-surface-container-lowest overflow-hidden flex items-center justify-center">
                {item.media_type === 'image' ? <img src={item.result_url} alt="" className="w-full h-full object-cover" /> : <Film size={26} className="text-primary" />}
              </div>
              <p className="mt-2 text-sm font-medium truncate">{item.filename}</p>
              <p className="text-xs text-on-surface-variant capitalize">{item.media_type} · {item.detections} detections</p>
            </button>
            <button type="button" aria-label={`Delete ${item.filename}`} onClick={() => void remove(item)} className="absolute right-2 bottom-7 p-1 text-on-surface-variant hover:text-error"><Trash2 size={15} /></button>
          </div>)}
          {!visible.length && <div className="px-4 py-10 text-center text-sm text-on-surface-variant">No {filter === 'all' ? 'media' : `${filter}s`} yet.</div>}
        </div>
      </aside>
      <section className="min-w-0 flex-1 flex flex-col stage-ambient technical-grid">
        {active ? <>
          <div className="h-12 shrink-0 border-b border-outline-variant bg-surface-container/80 px-5 flex items-center justify-between">
            <p className="truncate font-medium">{active.filename}</p><span className="status-pill border-primary/40 text-primary">{active.detections} detections</span>
          </div>
          <div className="min-h-0 flex-1 p-5 flex items-center justify-center">
            <div className="max-w-full max-h-full overflow-hidden rounded-lg border border-outline-variant bg-black shadow-2xl">
              {active.media_type === 'image' ? <img src={active.result_url} alt={`Inference result for ${active.filename}`} className="max-w-full max-h-[calc(100vh-10rem)] object-contain" /> : <video key={active.id} src={active.result_url} controls className="max-w-full max-h-[calc(100vh-10rem)]" />}
            </div>
          </div>
        </> : <div className="m-auto max-w-md text-center p-8">
          <div className="empty-state-illustration mx-auto mb-5 flex items-center justify-center"><FileImage className="text-primary relative z-10" size={28} /></div>
          <h1 className="text-headline-sm font-semibold">Upload an image or video</h1>
          <p className="mt-2 text-on-surface-variant">The annotated result will appear here after {task.title} inference finishes.</p>
          <button type="button" onClick={() => input.current?.click()} className="mt-5 panel-button h-10 px-4 text-primary">Choose media</button>
        </div>}
      </section>

      <aside className="w-64 shrink-0 border-l border-outline-variant bg-surface-container-low p-4 overflow-y-auto">
        <p className="font-label text-[10px] uppercase tracking-wider text-on-surface-variant">Color legend</p>
        <h2 className="mt-1 font-semibold">Detection classes</h2>
        <div className="mt-4 space-y-3">
          {Object.entries(taskInfo?.class_names ?? {}).map(([classId, className]) => (
            <div key={classId} className="flex items-start gap-3 text-sm">
              <span
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 shrink-0 rounded-sm border border-white/20"
                style={{ backgroundColor: DETECTION_COLORS[Number(classId) % DETECTION_COLORS.length] }}
              />
              <span className="leading-5 text-on-surface">{className}</span>
            </div>
          ))}
          {!taskInfo && <p className="text-sm text-on-surface-variant">Loading classes…</p>}
        </div>
        <p className="mt-6 border-t border-outline-variant pt-4 text-xs leading-5 text-on-surface-variant">
          Boxes use class colors only so the detected object stays unobstructed.
        </p>
      </aside>
    </main>
  </div>;
}
