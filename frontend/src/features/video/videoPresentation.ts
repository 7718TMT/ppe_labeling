import type { ProcessingJob, VideoItem } from '../../types';

export type UserVideoStatus = 'Unprocessed' | 'Processing' | 'Ready' | 'Failed';
export type UserAnnotationStatus = 'Unlabeled' | 'Labeled' | 'Approved';

const READY_STATUSES = new Set([
  'annotation_ready',
  'feature_ready',
  'threshold_suggestion_ready',
  'model_suggestion_ready',
]);

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'paused']);

/** Map detailed pipeline state to the small vocabulary shown to annotators. */
export function userVideoStatus(video: VideoItem, jobs: ProcessingJob[] = []): UserVideoStatus {
  const videoJobs = jobs.filter((job) => job.video_id === video.video_id);
  if (videoJobs.some((job) => ACTIVE_JOB_STATUSES.has(job.status))) {
    return 'Processing';
  }
  if (video.processing_status === 'failed') {
    return 'Failed';
  }
  if (READY_STATUSES.has(video.processing_status)) {
    return 'Ready';
  }
  return 'Unprocessed';
}

/** Keep annotation progress separate from media processing state. */
export function userAnnotationStatus(video: VideoItem): UserAnnotationStatus {
  if (video.is_approved || video.annotation_status === 'approved') {
    return 'Approved';
  }
  if (video.annotation_status === 'unlabeled') {
    return 'Unlabeled';
  }
  return 'Labeled';
}

/** Translate persistent worker stages into plain language. */
export function userJobStage(stage: string): string {
  if (stage === 'canonicalize') return 'Preparing video';
  if (stage === 'pose_track') return 'Detecting and tracking workers';
  if (stage === 'features') return 'Extracting motion features';
  if (stage === 'threshold') return 'Generating suggestions';
  if (stage === 'model' || stage.startsWith('model:')) return 'Generating suggestions';
  if (stage.startsWith('export:')) return 'Preparing export';
  return 'Processing video';
}

export function isVisibleQueueJob(job: ProcessingJob): boolean {
  return job.status !== 'completed';
}

/** Keep queue state in the same four-term vocabulary as video cards. */
export function userQueueStatus(job: ProcessingJob): UserVideoStatus {
  if (job.status === 'failed') return 'Failed';
  if (job.status === 'cancelled') return 'Unprocessed';
  if (job.status === 'completed') return 'Ready';
  return 'Processing';
}
