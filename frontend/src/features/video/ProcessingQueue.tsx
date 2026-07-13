import { PauseCircle, Play, RotateCcw, Square } from 'lucide-react';

import type { ProcessingJob } from '../../types';
import { isVisibleQueueJob, userJobStage, userQueueStatus } from './videoPresentation';

export function ProcessingQueue({
  jobs,
  onControl,
}: {
  jobs: ProcessingJob[];
  onControl: (job: ProcessingJob, action: string) => void;
}) {
  const visibleJobs = jobs.filter(isVisibleQueueJob).slice(0, 12);
  return (
    <section className="border-t border-outline-variant max-h-56 overflow-y-auto" aria-label="Processing queue">
      <div className="px-3 py-2 font-label text-label-caps uppercase text-on-surface-variant sticky top-0 bg-surface-container z-10">
        Processing queue
      </div>
      {visibleJobs.length === 0 ? (
        <p className="px-3 pb-3 text-label-sm text-on-surface-variant">No active processing.</p>
      ) : visibleJobs.map((job) => (
        <div key={job.job_id} className="px-3 py-2 border-t border-outline-variant/60">
          <div className="flex items-center gap-2">
            <span className="truncate font-label text-label-sm flex-1">{userJobStage(job.stage)}</span>
            <span className="text-[10px] uppercase text-on-surface-variant">{userQueueStatus(job)}</span>
          </div>
          <div className="h-1 bg-surface-container-highest mt-2" aria-label={`${userJobStage(job.stage)} ${Math.round(job.progress * 100)}%`}>
            <div className="h-full bg-primary transition-all" style={{ width: `${Math.round(job.progress * 100)}%` }} />
          </div>
          {job.error_message && <p className="text-[10px] text-error mt-1 line-clamp-2">Processing failed. Retry this video or check the application log.</p>}
          <div className="flex gap-2 mt-1 justify-end">
            {job.status === 'running' && <button type="button" title="Pause" onClick={() => onControl(job, 'pause')}><PauseCircle size={14} /></button>}
            {job.status === 'paused' && <button type="button" title="Resume" onClick={() => onControl(job, 'resume')}><Play size={14} /></button>}
            {['queued', 'running', 'paused'].includes(job.status) && <button type="button" title="Cancel" onClick={() => onControl(job, 'cancel')}><Square size={13} /></button>}
            {['failed', 'cancelled'].includes(job.status) && <button type="button" title="Retry" onClick={() => onControl(job, 'retry')}><RotateCcw size={14} /></button>}
          </div>
        </div>
      ))}
    </section>
  );
}
