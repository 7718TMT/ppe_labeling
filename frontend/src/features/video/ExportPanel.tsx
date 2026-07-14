import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Download, Loader2, ShieldCheck } from 'lucide-react';

import {
  createVideoExport,
  downloadVideoExport,
  getVideoExports,
  type VideoExportRecord,
  validateVideoExport,
} from '../../api/client';

type Validation = { errors: string[]; warnings: string[] };

/** Queue an atomic export, then deliver its ZIP once the worker completes it. */
export function ExportPanel({ projectId }: { projectId: string }) {
  const [validation, setValidation] = useState<Validation | null>(null);
  const [message, setMessage] = useState('');
  const [activeExport, setActiveExport] = useState<VideoExportRecord | null>(null);
  const downloadedIds = useRef(new Set<string>());

  useEffect(() => {
    const exportId = activeExport?.export_id;
    if (!exportId || ['completed', 'failed'].includes(activeExport.status)) return undefined;
    let cancelled = false;
    async function refreshExport() {
      try {
        const exports = await getVideoExports(projectId);
        const current = exports.find((item) => item.export_id === exportId);
        if (!current || cancelled) return;
        setActiveExport(current);
        if (current.status === 'completed' && !downloadedIds.current.has(current.export_id)) {
          downloadedIds.current.add(current.export_id);
          downloadVideoExport(projectId, current.export_id);
          setMessage('Export is ready. Your dataset download has started.');
        } else if (current.status === 'failed') {
          setMessage('Export failed in the background. Validate the project and try again.');
        }
      } catch {
        if (!cancelled) setMessage('Could not check export progress. You can reopen Export to try again.');
      }
    }
    void refreshExport();
    const timer = window.setInterval(() => void refreshExport(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeExport?.export_id, activeExport?.status, projectId]);

  async function validate() {
    setValidation(await validateVideoExport(projectId));
  }

  async function create() {
    const result = await createVideoExport(projectId);
    setValidation(result.validation);
    if (!result.queued) {
      setMessage('Resolve validation errors first.');
      return;
    }
    setActiveExport(result.export);
    setMessage('Preparing your export. The download will start when it is ready.');
  }

  const creating = activeExport?.status === 'queued' || activeExport?.status === 'running';
  return (
    <div className="p-3 space-y-3">
      <div className="flex gap-2">
        <button type="button" onClick={() => void validate()} className="h-8 px-3 border border-outline-variant rounded flex items-center gap-2">
          <ShieldCheck size={14} />Validate
        </button>
        <button type="button" disabled={creating} onClick={() => void create()} className="h-8 px-3 bg-primary-container text-on-primary-container rounded flex items-center gap-2 disabled:opacity-40">
          {creating ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          {creating ? 'Preparing export' : 'Create export'}
        </button>
        {activeExport?.status === 'completed' && (
          <button type="button" onClick={() => downloadVideoExport(projectId, activeExport.export_id)} className="h-8 px-3 border border-primary rounded text-primary flex items-center gap-2">
            <Download size={14} />Download ZIP
          </button>
        )}
      </div>
      {message && <p className="text-label-sm" role="status">{message}</p>}
      {validation && (
        <div className="space-y-2">
          <p className="flex gap-2 items-center text-label-sm"><CheckCircle2 size={14} className={validation.errors.length ? 'text-error' : 'text-emerald-400'} />{validation.errors.length ? 'Blocked' : 'Ready for atomic export'}</p>
          {validation.errors.map((item) => <p key={item} className="text-label-sm text-error">{item}</p>)}
          {validation.warnings.map((item) => <p key={item} className="text-label-sm text-amber-300">{item}</p>)}
        </div>
      )}
      <p className="text-[10px] text-on-surface-variant">Downloads one training-sample ZIP: annotations.jsonl, keypoint_windows.npz, and manifest.json. No splits are created.</p>
    </div>
  );
}
