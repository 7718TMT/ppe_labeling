import { describe, expect, it } from 'vitest';

import type { ProcessingJob, VideoItem } from '../../types';
import {
  userAnnotationStatus,
  userJobStage,
  userQueueStatus,
  userVideoStatus,
} from './videoPresentation';

const VIDEO: VideoItem = {
  video_id: 'v1', project_id: 'p1', filename: 'clip.mp4', original_fps: 24,
  canonical_fps: 24, original_frame_count: 120, canonical_frame_count: 120,
  duration_seconds: 5, width: 640, height: 480, processing_status: 'imported',
  annotation_status: 'unlabeled', quality_status: 'good', annotation_revision: 0,
  is_approved: 0, include_in_export: 1, updated_at: '2026-01-01',
};

const job = (status: string, stage = 'canonicalize'): ProcessingJob => ({
  job_id: `${stage}-${status}`, video_id: 'v1', stage, status, priority: 100, progress: 0.4,
});

describe('video presentation mappings', () => {
  it('shows only the four end-user processing states', () => {
    expect(userVideoStatus(VIDEO)).toBe('Unprocessed');
    expect(userVideoStatus(VIDEO, [job('running')])).toBe('Processing');
    expect(userVideoStatus({ ...VIDEO, processing_status: 'threshold_suggestion_ready' })).toBe('Ready');
    expect(userVideoStatus({ ...VIDEO, processing_status: 'failed' })).toBe('Failed');
    expect(userVideoStatus(
      { ...VIDEO, processing_status: 'feature_ready' },
      [job('failed')],
    )).toBe('Ready');
    expect(userVideoStatus({ ...VIDEO, processing_status: 'canonical_ready' })).toBe('Unprocessed');
  });

  it('keeps annotation state separate and simple', () => {
    expect(userAnnotationStatus(VIDEO)).toBe('Unlabeled');
    expect(userAnnotationStatus({ ...VIDEO, annotation_status: 'labeled' })).toBe('Labeled');
    expect(userAnnotationStatus({ ...VIDEO, is_approved: 1 })).toBe('Approved');
  });

  it('uses one clear label for every worker stage', () => {
    expect(userJobStage('canonicalize')).toBe('Preparing video');
    expect(userJobStage('pose_track')).toBe('Detecting and tracking workers');
    expect(userJobStage('features')).toBe('Extracting motion features');
    expect(userJobStage('threshold')).toBe('Generating suggestions');
    expect(userJobStage('model')).toBe('Generating suggestions');
    expect(userJobStage('model:m1')).toBe('Generating suggestions');
  });

  it('uses the same four states in the processing queue', () => {
    expect(userQueueStatus(job('queued'))).toBe('Processing');
    expect(userQueueStatus(job('paused'))).toBe('Processing');
    expect(userQueueStatus(job('cancelled'))).toBe('Unprocessed');
    expect(userQueueStatus(job('failed'))).toBe('Failed');
    expect(userQueueStatus(job('completed'))).toBe('Ready');
  });
});
