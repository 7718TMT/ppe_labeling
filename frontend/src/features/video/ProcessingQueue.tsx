import type { ProcessingJob } from '../../types';
import { isVisibleQueueJob, userJobStage } from './videoPresentation';

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'paused']);

/** Show one batch-level indicator instead of a bar for every video job. */
export function ProcessingQueue({
  jobs,
  remainingVideos = 0,
  totalVideos = 0,
}: {
  jobs: ProcessingJob[];
  remainingVideos?: number;
  totalVideos?: number;
}) {
  const activeJobs = jobs.filter((job) => ACTIVE_JOB_STATUSES.has(job.status));
  const failedJobs = jobs.filter((job) => job.status === 'failed' && isVisibleQueueJob(job));
  const currentJob = activeJobs.find((job) => job.status === 'running') ?? activeJobs[0];
  const progress = totalVideos > 0
    ? Math.round(((totalVideos - remainingVideos) / totalVideos) * 100)
    : 0;

  return (
    <section className="border-t border-outline-variant" aria-label="Processing queue">
      <div className="px-3 py-2 font-label text-label-caps uppercase text-on-surface-variant">
        <div className="flex items-center justify-between gap-2">
          <span>Processing queue</span>
          {totalVideos > 0 && (
            <span className="normal-case text-[10px]">
              {remainingVideos} remaining / {totalVideos} videos
            </span>
          )}
        </div>
        {totalVideos > 0 ? (
          <>
            <div className="h-1 bg-surface-container-highest mt-2" aria-label={`${remainingVideos} remaining of ${totalVideos} videos`}>
              <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
            </div>
            {currentJob && <p className="normal-case text-[10px] mt-2">{userJobStage(currentJob.stage)}</p>}
          </>
        ) : (
          <p className="normal-case text-label-sm mt-1">No active processing.</p>
        )}
        {failedJobs.length > 0 && (
          <p className="normal-case text-[10px] text-error mt-2">
            {failedJobs.length} video{failedJobs.length === 1 ? '' : 's'} need attention. Select the video to retry or review its error.
          </p>
        )}
      </div>
    </section>
  );
}
