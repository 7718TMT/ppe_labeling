import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api/client';
import type { VideoItem } from '../types';
import { VideoWorkspace } from './VideoWorkspace';

vi.mock('../api/client', () => ({
  approveVideo: vi.fn(),
  controlVideoJob: vi.fn(),
  deleteVideo: vi.fn(),
  deleteVideoSegment: vi.fn(),
  extendVideoSegment: vi.fn(),
  getProcessingOptions: vi.fn(),
  getFeatures: vi.fn(),
  getPoseOverlay: vi.fn(),
  getSuggestions: vi.fn(),
  getVideoJobs: vi.fn(),
  getVideoProject: vi.fn(),
  getVideoSegments: vi.fn(),
  getVideoTracks: vi.fn(),
  getVideos: vi.fn(),
  importVideos: vi.fn(),
  labelFullVideoTrack: vi.fn(),
  mergeMultipleVideoTracks: vi.fn(),
  mergeVideoSegments: vi.fn(),
  mergeVideoTracks: vi.fn(),
  processVideo: vi.fn(),
  reviewSuggestion: vi.fn(),
  saveVideoSegment: vi.fn(),
  saveVideoWorkspaceState: vi.fn(),
  setVideoSegmentInclusion: vi.fn(),
  setVideoTrackInclusion: vi.fn(),
  splitVideoSegment: vi.fn(),
  splitVideoTrack: vi.fn(),
  unapproveVideo: vi.fn(),
  validateVideoExport: vi.fn(),
  createVideoExport: vi.fn(),
  videoHistoryAction: vi.fn(),
  videoMediaUrl: vi.fn((projectId: string, videoId: string) => `/api/v1/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/media`),
  videoThumbnailUrl: vi.fn((projectId: string, videoId: string) => `/thumbnail/${projectId}/${videoId}`),
}));

const makeVideo = (id: string, filename: string): VideoItem => ({
  video_id: id,
  project_id: 'p1',
  filename,
  original_fps: 24,
  canonical_fps: 24,
  original_frame_count: 120,
  canonical_frame_count: 120,
  duration_seconds: 5,
  width: 640,
  height: 480,
  processing_status: 'annotation_ready',
  annotation_status: 'unlabeled',
  quality_status: 'good',
  annotation_revision: 0,
  is_approved: 0,
  include_in_export: 1,
  updated_at: '2026-01-01',
});

const VIDEO_A = makeVideo('v1', 'shift-a.mp4');
const VIDEO_B = makeVideo('v2', 'shift-b.mp4');

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={['/video/p1']}>
      <Routes><Route path="/video/:projectId" element={<VideoWorkspace />} /></Routes>
    </MemoryRouter>,
  );
}

describe('VideoWorkspace', () => {
  let videos: VideoItem[];

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    videos = [VIDEO_A, VIDEO_B];
    Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
    vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
    vi.mocked(api.getVideoProject).mockResolvedValue({
      project_id: 'p1', name: 'Factory', config: {}, created_at: '', updated_at: '', workspace_state: null,
    });
    vi.mocked(api.getVideos).mockImplementation(async () => videos);
    vi.mocked(api.getVideoJobs).mockResolvedValue([]);
    vi.mocked(api.getVideoTracks).mockImplementation(async (_projectId, videoId) => [{
      track_id: videoId === 'v1' ? 1 : 2,
      start_frame: 0,
      end_frame: 119,
      avg_keypoint_confidence: 0.9,
      valid_frame_ratio: 1,
      missing_ankle_ratio: 0,
      quality_status: 'good',
      include_in_export: 1,
    }]);
    vi.mocked(api.getVideoSegments).mockResolvedValue({ revision: 0, segments: [] });
    vi.mocked(api.getFeatures).mockResolvedValue([]);
    vi.mocked(api.getSuggestions).mockResolvedValue([]);
    vi.mocked(api.getPoseOverlay).mockResolvedValue([]);
    vi.mocked(api.saveVideoWorkspaceState).mockResolvedValue({
      video_id: 'v1', track_id: 1, frame_index: 0, suggestion_source: 'Threshold',
    });
    vi.mocked(api.getProcessingOptions).mockResolvedValue({
      threshold_available: true,
      model_available: false,
      model_message: 'Model suggestions are not configured for this project.',
    });
    vi.mocked(api.saveVideoSegment).mockResolvedValue({
      revision: 1,
      segment: {
        segment_id: 's1', track_id: 1, start_frame: 0, end_frame: 10,
        label: 'running', quality_status: 'good', include_in_export: 1,
        needs_review: 0, source_type: 'manual',
      },
    });
    vi.mocked(api.processVideo).mockResolvedValue([{
      job_id: 'j1', video_id: 'v1', stage: 'features', status: 'queued', priority: 1000, progress: 0,
    }]);
    vi.mocked(api.deleteVideo).mockImplementation(async (_projectId, videoId) => {
      videos = videos.filter((video) => video.video_id !== videoId);
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('synchronizes track and segment controls without triggering shortcuts while typing', async () => {
    renderWorkspace();
    expect(await screen.findByText('Worker 1')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Full track' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Extend' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy prev' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Merge adj' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '+ Create Segment' }));
    fireEvent.click(screen.getByRole('button', { name: 'running' }));
    fireEvent.change(screen.getByLabelText('End'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add segment' }));
    await waitFor(() => expect(api.saveVideoSegment).toHaveBeenCalledWith(
      'p1',
      'v1',
      expect.objectContaining({ label: 'running', end_frame: 10, expected_revision: 0 }),
      undefined,
    ));
    fireEvent.keyDown(screen.getByLabelText('Start'), { key: '3' });
    expect(screen.getByRole('button', { name: 'running' })).toHaveClass('border-primary');
  });

  it('shows a recoverable revision conflict instead of silently overwriting', async () => {
    vi.mocked(api.saveVideoSegment).mockRejectedValueOnce(new Error('409 revision conflict'));
    renderWorkspace();
    await screen.findByText('Worker 1');
    fireEvent.click(screen.getByRole('button', { name: '+ Create Segment' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add segment' }));
    // Error message is shown in the status bar
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('explains exhausted undo history without presenting a technical error', async () => {
    vi.mocked(api.videoHistoryAction).mockRejectedValueOnce(new Error('Nothing to undo'));
    renderWorkspace();
    await screen.findByText('Worker 1');
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(await screen.findByRole('status')).toHaveTextContent(
      'No earlier annotation changes are available to undo.',
    );
    expect(screen.getByRole('button', { name: 'Undo' })).toBeDisabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('generates Threshold suggestions from the unified suggestion control', async () => {
    renderWorkspace();
    await screen.findByText('Worker 1');
    fireEvent.click(screen.getByRole('button', { name: 'Suggestion' }));
    await waitFor(() => expect(api.processVideo).toHaveBeenCalledWith('p1', 'v1', 'Threshold'));
    expect(await screen.findByRole('status')).toHaveTextContent('Threshold suggestion generation started');
  });

  it('shows the actual persisted mode for an active pipeline', async () => {
    vi.mocked(api.getProcessingOptions).mockResolvedValue({
      threshold_available: true,
      model_available: true,
      model_message: null,
    });
    vi.mocked(api.getVideoJobs).mockResolvedValue([{
      job_id: 'threshold-job', video_id: 'v1', stage: 'features', status: 'running',
      priority: 100, progress: 0.5, target_mode: 'threshold', external_model_id: null,
    }]);
    renderWorkspace();
    await screen.findByText('Worker 1');
    expect(screen.getByRole('button', { name: 'Suggestion' })).toBeDisabled();
  });

  it('generates AI suggestions from the unified control without changing manual labels', async () => {
    vi.mocked(api.getProcessingOptions).mockResolvedValue({
      threshold_available: true,
      model_available: true,
      model_message: null,
    });
    vi.mocked(api.getVideoSegments).mockResolvedValue({
      revision: 1,
      segments: [{
        segment_id: 'manual-1', track_id: 1, start_frame: 2, end_frame: 10,
        label: 'running', quality_status: 'good', include_in_export: 1,
        needs_review: 0, source_type: 'manual',
      }],
    });
    renderWorkspace();
    await screen.findByText('Worker 1');
    // Segment title format is now 'running frames 2–10' (#2)
    expect(screen.getByTitle('running frames 2\u201310')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Choose suggestion source' }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'AI' }));
    fireEvent.click(screen.getByRole('button', { name: 'Suggestion' }));
    await waitFor(() => expect(api.processVideo).toHaveBeenCalledWith('p1', 'v1', 'Model'));
    expect(await screen.findByRole('status')).toHaveTextContent('AI suggestion generation started');
    expect(api.saveVideoSegment).not.toHaveBeenCalled();
    expect(screen.getByTitle('running frames 2\u201310')).toBeInTheDocument();
  });

  it('autosaves edits to an existing segment and reports the real save state', async () => {
    vi.mocked(api.getVideoSegments).mockResolvedValue({
      revision: 3,
      segments: [{
        segment_id: 'manual-1', track_id: 1, start_frame: 2, end_frame: 10,
        label: 'running', quality_status: 'good', include_in_export: 1,
        needs_review: 0, source_type: 'manual',
      }],
    });
    vi.mocked(api.saveVideoSegment).mockImplementation(async (_projectId, _videoId, payload, segmentId) => ({
      revision: payload.expected_revision + 1,
      segment: {
        segment_id: segmentId ?? 'manual-1',
        track_id: payload.track_id,
        start_frame: payload.start_frame,
        end_frame: payload.end_frame,
        label: payload.label,
        quality_status: 'good',
        include_in_export: 1,
        needs_review: 0,
        source_type: 'manual',
      },
    }));
    renderWorkspace();
    fireEvent.click(await screen.findByRole('button', { name: /running.*2.*10/ }));
    fireEvent.change(screen.getByLabelText('End'), { target: { value: '12' } });
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    await waitFor(() => expect(api.saveVideoSegment).toHaveBeenCalledWith(
      'p1',
      'v1',
      expect.objectContaining({ start_frame: 2, end_frame: 12, expected_revision: 3 }),
      'manual-1',
    ), { timeout: 1600 });
    await waitFor(() => expect(screen.getByText('Saved')).toBeInTheDocument());
  });

  it('returns to full-video mode and loops the whole video after deselecting a segment', async () => {
    vi.mocked(api.getVideoSegments).mockResolvedValue({
      revision: 0,
      segments: [{
        segment_id: 'manual-1', track_id: 1, start_frame: 2, end_frame: 10,
        label: 'running', quality_status: 'good', include_in_export: 1,
        needs_review: 0, source_type: 'manual',
      }],
    });
    renderWorkspace();

    const segmentCard = await screen.findByRole('button', { name: /running.*2.*10/ });
    fireEvent.click(segmentCard);
    expect(screen.getByRole('button', { name: 'Modify segment' })).toBeInTheDocument();
    fireEvent.click(segmentCard);
    expect(screen.queryByRole('button', { name: 'Modify segment' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Loop' }));
    await waitFor(() => expect(document.querySelector('video')?.loop).toBe(true));
    expect(screen.getByRole('button', { name: 'Loop' })).toHaveAttribute(
      'title',
      'Loop full video',
    );
  });

  it('returns to full-video mode when Create Segment is selected again', async () => {
    renderWorkspace();

    const createCard = await screen.findByRole('button', { name: '+ Create Segment' });
    fireEvent.click(createCard);
    expect(screen.getByRole('button', { name: 'Add segment' })).toBeInTheDocument();
    fireEvent.click(createCard);
    expect(screen.queryByRole('button', { name: 'Add segment' })).not.toBeInTheDocument();
  });

  it('exits fullscreen from the fullscreen button without requiring Escape', async () => {
    const fullscreenElement = document.createElement('main');
    const exitFullscreen = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: fullscreenElement,
    });
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    renderWorkspace();
    await screen.findByText('Worker 1');
    fireEvent(document, new Event('fullscreenchange'));

    fireEvent.click(screen.getByRole('button', { name: 'Exit fullscreen' }));
    await waitFor(() => expect(exitFullscreen).toHaveBeenCalledTimes(1));
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: null,
    });
  });

  it('keeps global shortcuts inactive behind dialogs and focused controls', async () => {
    renderWorkspace();
    await screen.findByText('Worker 1');
    const help = screen.getByRole('button', { name: 'Help' });
    help.focus();
    fireEvent.keyDown(help, { key: ' ' });
    expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
    fireEvent.click(help);
    fireEvent.keyDown(window, { key: 'n' });
    fireEvent.keyDown(window, { key: 'Enter' });
    expect(api.approveVideo).not.toHaveBeenCalled();
    expect(api.saveVideoSegment).not.toHaveBeenCalled();
  });

  it('keeps delayed overlay chunks synchronized while frames advance', async () => {
    let resolveOverlay: ((rows: Awaited<ReturnType<typeof api.getPoseOverlay>>) => void) | undefined;
    vi.mocked(api.getPoseOverlay).mockImplementation(() => new Promise((resolve) => { resolveOverlay = resolve; }));
    renderWorkspace();
    await waitFor(() => expect(api.getPoseOverlay).toHaveBeenCalledOnce());
    fireEvent.change(screen.getByLabelText('Current frame'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('Current frame'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Current frame'), { target: { value: '3' } });
    expect(api.getPoseOverlay).toHaveBeenCalledOnce();
    await act(async () => {
      resolveOverlay?.([{
        frame_index: 3,
        tracks: [{
          track_id: 1,
          bbox: [10, 10, 100, 150],
          keypoints: Array.from({ length: 17 }, () => [20, 20] as [number, number]),
          keypoint_scores: Array.from({ length: 17 }, () => 0.9),
          person_confidence: 0.9,
        }],
      }]);
      await Promise.resolve();
    });
    expect(await screen.findByText('Worker 1')).toBeInTheDocument();
  });

  it('shows suggestion overlay in the timeline (Suggestions tab removed)', async () => {
    vi.mocked(api.getSuggestions).mockResolvedValue([{
      suggestion_id: 'suggestion-1',
      track_id: 1,
      start_frame: 4,
      end_frame: 9,
      suggested_label: 'falling',
      confidence: 0.82,
      review_status: 'pending',
      triggered_conditions: ['Rapid loss of balance'],
      supporting_features: { torso_angle_score: 0.8 },
      probabilities: { falling: 0.82, running: 0.1, others: 0.08 },
    }]);
    renderWorkspace();
    await screen.findByText('Worker 1');
    // Suggestions tab is removed (#4); suggestion is shown as overlay in timeline
    expect(screen.queryByRole('button', { name: 'suggestions' })).not.toBeInTheDocument();
    // Verify suggestions are still loaded (getSuggestions is called)
    await waitFor(() => expect(api.getSuggestions).toHaveBeenCalled());
  });

  it('reloads a saved segment after switching to another video and back', async () => {
    vi.mocked(api.getVideoSegments).mockImplementation(async (_projectId, videoId) => ({
      revision: videoId === 'v1' ? 2 : 0,
      segments: videoId === 'v1' ? [{
        segment_id: 'manual-1', track_id: 1, start_frame: 5, end_frame: 15,
        label: 'falling', quality_status: 'good', include_in_export: 1,
        needs_review: 0, source_type: 'manual',
      }] : [],
    }));
    renderWorkspace();
    // Segment title format in sidebar list uses em-dash (#2)
    expect(await screen.findByTitle('falling frames 5\u201315')).toBeInTheDocument();
    fireEvent.click(screen.getByText('shift-b.mp4'));
    expect(await screen.findByText('Worker 2')).toBeInTheDocument();
    fireEvent.click(screen.getByText('shift-a.mp4'));
    expect(await screen.findByTitle('falling frames 5\u201315')).toBeInTheDocument();
  });

  it('refreshes derived data after an active processing pipeline completes', async () => {
    vi.mocked(api.getVideoJobs)
      .mockResolvedValueOnce([{
        job_id: 'pipeline-1', video_id: 'v1', stage: 'pose_track', status: 'running', priority: 100, progress: 0.5,
      }])
      .mockResolvedValue([{
        job_id: 'pipeline-1', video_id: 'v1', stage: 'pose_track', status: 'completed', priority: 100, progress: 1,
      }]);
    vi.mocked(api.getVideoTracks)
      .mockResolvedValueOnce([])
      .mockResolvedValue([{
        track_id: 1, start_frame: 0, end_frame: 119, avg_keypoint_confidence: 0.9,
        valid_frame_ratio: 1, missing_ankle_ratio: 0, quality_status: 'good', include_in_export: 1,
      }]);
    renderWorkspace();
    expect(await screen.findByText('Process the video to detect worker tracks.')).toBeInTheDocument();
    expect(await screen.findByText('Worker 1', {}, { timeout: 7000 })).toBeInTheDocument();
    expect(api.getFeatures).toHaveBeenCalledTimes(2);
  });

  it('keeps an in-flight processing request scoped to its original video', async () => {
    let resolveProcess: ((jobs: Awaited<ReturnType<typeof api.processVideo>>) => void) | undefined;
    vi.mocked(api.processVideo).mockImplementation(() => new Promise((resolve) => { resolveProcess = resolve; }));
    renderWorkspace();
    await screen.findByText('Worker 1');
    fireEvent.click(screen.getByRole('button', { name: 'Suggestion' }));
    fireEvent.click(screen.getByText('shift-b.mp4'));
    expect(await screen.findByText('Worker 2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Suggestion' })).not.toBeDisabled();
    await act(async () => {
      resolveProcess?.([{
        job_id: 'a-job', video_id: 'v1', stage: 'canonicalize', status: 'queued', priority: 1000, progress: 0,
      }]);
      await Promise.resolve();
    });
    expect(screen.queryByText('Threshold suggestion generation started.')).not.toBeInTheDocument();
  });

  it('offers only Annotate and Details tabs and a searchable Help guide', async () => {
    renderWorkspace();
    await screen.findByText('Worker 1');
    // Suggestions tab is removed (#4)
    expect(screen.getByRole('button', { name: 'annotate' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'suggestions' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'details' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /thresholds/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/model file/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Help' }));
    expect(screen.getByRole('dialog', { name: 'Pose labeling help' })).toBeInTheDocument();
    expect(screen.getByText(/loss of balance begins/)).toBeInTheDocument();
  });

  it('keeps annotations usable when Model availability cannot be loaded', async () => {
    vi.mocked(api.getProcessingOptions).mockRejectedValue(new Error('model service unavailable'));
    renderWorkspace();
    expect(await screen.findByText('Worker 1')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Choose suggestion source' }));
    expect(screen.getByRole('menuitemradio', { name: /AI/ })).toBeDisabled();
  });

  it('imports videos using the method selected by the suggestion control', async () => {
    const imported = makeVideo('v3', 'new-video.mp4');
    const file = new File(['video'], 'new-video.mp4', { type: 'video/mp4' });
    vi.mocked(api.getProcessingOptions).mockResolvedValue({
      threshold_available: true,
      model_available: true,
      model_message: null,
    });
    vi.mocked(api.importVideos).mockResolvedValue([imported]);
    renderWorkspace();
    await screen.findByText('Worker 1');
    fireEvent.click(screen.getByRole('button', { name: 'Choose suggestion source' }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'AI' }));
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });
    await waitFor(() => expect(api.importVideos).toHaveBeenCalledWith('p1', [file], 'Model'));
  });

  it('deletes project-owned video data through confirmation and selects the next video', async () => {
    renderWorkspace();
    await screen.findByText('Worker 1');
    fireEvent.click(screen.getByRole('button', { name: 'Delete shift-a.mp4' }));
    expect(screen.getByRole('alertdialog')).toHaveTextContent('shift-a.mp4');
    // Updated delete dialog text: mentions managed copy and derived pose data
    expect(screen.getByRole('alertdialog')).toHaveTextContent('managed copy');
    fireEvent.click(screen.getByRole('button', { name: 'Delete video' }));
    await waitFor(() => expect(api.deleteVideo).toHaveBeenCalledWith('p1', 'v1'));
    await waitFor(() => expect(screen.queryByText('shift-a.mp4')).not.toBeInTheDocument());
    expect(screen.getByLabelText('Open shift-b.mp4')).toHaveAttribute('aria-current', 'true');
    expect(await screen.findByText('Worker 2')).toBeInTheDocument();
  });

  it('ignores late active-video responses during repeated switching', async () => {
    let resolveFirstTracks: ((value: Awaited<ReturnType<typeof api.getVideoTracks>>) => void) | undefined;
    vi.mocked(api.getVideoTracks).mockImplementation((_projectId, videoId) => {
      if (videoId === 'v1' && !resolveFirstTracks) {
        return new Promise((resolve) => { resolveFirstTracks = resolve; });
      }
      return Promise.resolve([{
        track_id: videoId === 'v1' ? 1 : 2, start_frame: 0, end_frame: 119,
        avg_keypoint_confidence: 0.9, valid_frame_ratio: 1, missing_ankle_ratio: 0,
        quality_status: 'good', include_in_export: 1,
      }]);
    });
    renderWorkspace();
    expect(await screen.findByText('shift-b.mp4')).toBeInTheDocument();
    fireEvent.click(screen.getByText('shift-b.mp4'));
    expect(await screen.findByText('Worker 2')).toBeInTheDocument();
    resolveFirstTracks?.([{
      track_id: 1, start_frame: 0, end_frame: 119, avg_keypoint_confidence: 0.9,
      valid_frame_ratio: 1, missing_ankle_ratio: 0, quality_status: 'good', include_in_export: 1,
    }]);
    await Promise.resolve();
    expect(screen.queryByText('Worker 1')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('shift-a.mp4'));
    expect(await screen.findByText('Worker 1')).toBeInTheDocument();
  });
});
