import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Download, Loader2, ShieldCheck } from 'lucide-react';

import {
  createVideoExport,
  downloadVideoExport,
  type VideoExportRecord,
  validateVideoExport,
} from '../../api/client';

type Validation = { errors: string[]; warnings: string[] };

/** Queue an atomic export, then react to workspace-synchronized export updates. */
export function ExportPanel({
  projectId,
  exports,
}: {
  projectId: string;
  /** Event-synchronized project exports; this avoids a separate polling loop. */
  exports: VideoExportRecord[];
}) {
  const [validation, setValidation] = useState<Validation | null>(null);
  const [message, setMessage] = useState('');
  const [activeExport, setActiveExport] = useState<VideoExportRecord | null>(null);
  const [autoDownloadExportId, setAutoDownloadExportId] = useState<string>();
  const downloadedIds = useRef(new Set<string>());

  useEffect(() => {
    setActiveExport((current) => {
      if (current) {
        return exports.find((item) => item.export_id === current.export_id) ?? current;
      }
      // A reopened dialog can still surface an in-progress or completed
      // export without restoring the removed polling loop.
      return exports.find((item) => item.status === 'queued' || item.status === 'running')
        ?? exports[0]
        ?? null;
    });
  }, [exports]);

  useEffect(() => {
    if (!activeExport || activeExport.export_id !== autoDownloadExportId) return;
    if (activeExport.status === 'completed' && !downloadedIds.current.has(activeExport.export_id)) {
      downloadedIds.current.add(activeExport.export_id);
      downloadVideoExport(projectId, activeExport.export_id);
      setMessage('Export is ready. Your dataset download has started.');
      setAutoDownloadExportId(undefined);
    } else if (activeExport.status === 'failed') {
      setMessage('Export failed in the background. Validate the project and try again.');
      setAutoDownloadExportId(undefined);
    }
  }, [activeExport, autoDownloadExportId, projectId]);

  async function validate() {
    try {
      setValidation(await validateVideoExport(projectId));
      setMessage('Export validation completed.');
    } catch {
      setMessage('Could not validate the export. Please try again.');
    }
  }

  async function create() {
    try {
      const result = await createVideoExport(projectId);
      setValidation(result.validation);
      if (!result.queued) {
        setMessage('Resolve validation errors first.');
        return;
      }
      setActiveExport(result.export);
      setAutoDownloadExportId(result.export.export_id);
      setMessage('Preparing your export. The download will start when it is ready.');
    } catch {
      setMessage('Could not create the export. Please try again.');
    }
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
