import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FeatureWindow, PoseTrackFrame, VideoItem } from '../../types';
import { PoseVideoPlayer } from './PoseVideoPlayer';

const videoA: VideoItem = {
  video_id: 'video-a',
  project_id: 'factory floor',
  filename: 'shift-a.mp4',
  original_fps: 24,
  canonical_fps: 24,
  original_frame_count: 240,
  canonical_frame_count: 240,
  duration_seconds: 10,
  width: 640,
  height: 480,
  processing_status: 'annotation_ready',
  annotation_status: 'unlabeled',
  quality_status: 'good',
  annotation_revision: 0,
  is_approved: 0,
  include_in_export: 1,
  updated_at: '2026-07-13',
};

const videoB: VideoItem = {
  ...videoA,
  video_id: 'video-b',
  filename: 'shift-b.mp4',
};

const overlay: PoseTrackFrame = {
  frame_index: 1,
  tracks: [{
    track_id: 7,
    bbox: [10, 20, 110, 220],
    keypoints: Array.from({ length: 17 }, (_, index) => [index * 3, index * 4]),
    keypoint_scores: Array.from({ length: 17 }, () => 0.9),
    person_confidence: 0.95,
  }],
};

const dummyFeatures: FeatureWindow[] = [{
  window_id: 'win-1',
  track_id: 7,
  start_frame: 0,
  end_frame: 60,
  raw: {},
  transformed: {
    running_score: 0.854,
    fall_inhibition_score: 0.152,
  },
  provenance: {},
  quality: { status: 'good', valid_frame_ratio: 1.0 },
}];

type FrameCallback = (now: DOMHighResTimeStamp, metadata: VideoFrameCallbackMetadata) => void;

describe('PoseVideoPlayer', () => {
  let loadSpy: ReturnType<typeof vi.spyOn>;
  let pauseSpy: ReturnType<typeof vi.spyOn>;
  let frameCallbacks: Map<number, FrameCallback>;
  let nextFrameRequestId: number;

  beforeEach(() => {
    loadSpy = vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => undefined);
    pauseSpy = vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);

    frameCallbacks = new Map();
    nextFrameRequestId = 1;
    Object.defineProperty(HTMLVideoElement.prototype, 'requestVideoFrameCallback', {
      configurable: true,
      value: vi.fn((callback: FrameCallback) => {
        const requestId = nextFrameRequestId;
        nextFrameRequestId += 1;
        frameCallbacks.set(requestId, callback);
        return requestId;
      }),
    });
    Object.defineProperty(HTMLVideoElement.prototype, 'cancelVideoFrameCallback', {
      configurable: true,
      value: vi.fn((requestId: number) => {
        frameCallbacks.delete(requestId);
      }),
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    delete (HTMLVideoElement.prototype as Partial<HTMLVideoElement>).requestVideoFrameCallback;
    delete (HTMLVideoElement.prototype as Partial<HTMLVideoElement>).cancelVideoFrameCallback;
  });

  // showBoxes now controls both bbox and skeleton (#13).
  // showSkeleton prop is removed.
  function renderPlayer(video = videoA, frameOverlay: PoseTrackFrame | undefined = overlay) {
    const onTimeUpdate = vi.fn();
    const result = render(
      <PoseVideoPlayer
        projectId="factory floor"
        video={video}
        overlay={frameOverlay}
        selectedTrack={7}
        selectedOnly={false}
        showBoxes
        onSelectTrack={vi.fn()}
        onTimeUpdate={onTimeUpdate}
      />,
    );
    return { ...result, onTimeUpdate };
  }

  it('restores the selected playback rate after switching video sources', () => {
    const { rerender } = renderPlayer();
    const player = document.querySelector('video') as HTMLVideoElement;

    rerender(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoB}
        overlay={overlay}
        selectedTrack={7}
        selectedOnly={false}
        showBoxes
        playbackRate={0.5}
        onSelectTrack={vi.fn()}
        onTimeUpdate={vi.fn()}
      />,
    );
    fireEvent.loadedMetadata(player);

    expect(player.playbackRate).toBe(0.5);
  });

  it('keeps playing and reporting media frames after pose data ends', () => {
    const { onTimeUpdate, rerender } = renderPlayer();
    const player = document.querySelector('video') as HTMLVideoElement;
    expect(player).toHaveClass('w-full', 'h-full', 'object-contain');
    expect(screen.getByText('W7')).toBeInTheDocument();
    expect(screen.getByTestId('worker-label-7')).toHaveAttribute('width', '100');

    pauseSpy.mockClear();
    Object.defineProperty(player, 'paused', { configurable: true, value: false });
    Object.defineProperty(player, 'ended', { configurable: true, value: false });
    player.currentTime = 8.75;
    fireEvent.play(player);

    const firstFrameCallback = frameCallbacks.values().next().value as FrameCallback;
    firstFrameCallback(0, {} as VideoFrameCallbackMetadata);
    expect(onTimeUpdate).toHaveBeenCalled();

    rerender(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoA}
        overlay={undefined}
        selectedTrack={7}
        selectedOnly={false}
        showBoxes
        onSelectTrack={vi.fn()}
        onTimeUpdate={onTimeUpdate}
      />,
    );
    expect(screen.getByText('No pose at this frame')).toBeInTheDocument();

    player.currentTime = 9.75;
    fireEvent.timeUpdate(player);
    fireEvent.seeked(player);

    expect(player.currentTime).toBe(9.75);
    expect(pauseSpy).not.toHaveBeenCalled();
    expect(loadSpy).toHaveBeenCalledOnce();
  });

  it('synchronizes the actual media ended event without an earlier pose boundary', () => {
    const { onTimeUpdate } = renderPlayer(videoA, undefined);
    const player = document.querySelector('video') as HTMLVideoElement;
    Object.defineProperty(player, 'paused', { configurable: true, value: false });
    Object.defineProperty(player, 'ended', { configurable: true, value: false });
    player.currentTime = 9.9;
    fireEvent.play(player);
    fireEvent.timeUpdate(player);
    const callsBeforeEnd = onTimeUpdate.mock.calls.length;
    Object.defineProperty(player, 'paused', { configurable: true, value: true });
    Object.defineProperty(player, 'ended', { configurable: true, value: true });
    player.currentTime = 10;
    fireEvent.ended(player);
    expect(player.currentTime).toBe(10);
    expect(onTimeUpdate.mock.calls.length).toBeGreaterThan(callsBeforeEnd);
  });

  it('resets and reloads the media source for repeated A to B to A switching', async () => {
    const { rerender } = renderPlayer(videoA, undefined);
    const player = document.querySelector('video') as HTMLVideoElement;

    expect(player.getAttribute('src')).toBe('/api/v1/video-projects/factory%20floor/videos/video-a/media');
    player.currentTime = 4;

    rerender(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoB}
        selectedOnly={false}
        showBoxes
        onSelectTrack={vi.fn()}
        onTimeUpdate={vi.fn()}
      />,
    );
    await waitFor(() => expect(player.getAttribute('src')).toBe(
      '/api/v1/video-projects/factory%20floor/videos/video-b/media',
    ));
    expect(player.currentTime).toBe(0);

    player.currentTime = 3;
    rerender(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoA}
        selectedOnly={false}
        showBoxes
        onSelectTrack={vi.fn()}
        onTimeUpdate={vi.fn()}
      />,
    );
    await waitFor(() => expect(player.getAttribute('src')).toBe(
      '/api/v1/video-projects/factory%20floor/videos/video-a/media',
    ));
    expect(player.currentTime).toBe(0);
    expect(loadSpy).toHaveBeenCalledTimes(5);
    expect(pauseSpy).toHaveBeenCalledTimes(5);
  });

  it('supports repeated play and scrub cycles across A to B to A navigation', async () => {
    const { rerender, onTimeUpdate } = renderPlayer(videoA, undefined);
    const player = document.querySelector('video') as HTMLVideoElement;
    Object.defineProperty(player, 'paused', { configurable: true, value: false });
    Object.defineProperty(player, 'ended', { configurable: true, value: false });

    for (const [index, currentVideo] of [videoA, videoB, videoA, videoB, videoA].entries()) {
      rerender(
        <PoseVideoPlayer
          projectId="factory floor"
          video={currentVideo}
          selectedOnly={false}
          showBoxes
          onSelectTrack={vi.fn()}
          onTimeUpdate={onTimeUpdate}
        />,
      );
      await waitFor(() => expect(player.getAttribute('src')).toContain(currentVideo.video_id));
      player.currentTime = index + 0.5;
      fireEvent.play(player);
      fireEvent.seeked(player);
      fireEvent.timeUpdate(player);
      expect(player.currentTime).toBe(index + 0.5);
    }
    expect(onTimeUpdate.mock.calls.length).toBeGreaterThanOrEqual(15);
  });

  it('cancels stale frame callbacks when the selected media changes', () => {
    const { onTimeUpdate, rerender } = renderPlayer(videoA, undefined);
    const player = document.querySelector('video') as HTMLVideoElement;
    Object.defineProperty(player, 'paused', { configurable: true, value: false });
    Object.defineProperty(player, 'ended', { configurable: true, value: false });
    player.dispatchEvent(new Event('play'));
    expect(HTMLVideoElement.prototype.requestVideoFrameCallback).toHaveBeenCalledOnce();
    const staleCallback = vi.mocked(
      HTMLVideoElement.prototype.requestVideoFrameCallback,
    ).mock.calls[0][0] as FrameCallback;
    const callsBeforeSwitch = onTimeUpdate.mock.calls.length;
    rerender(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoB}
        selectedOnly={false}
        showBoxes
        onSelectTrack={vi.fn()}
        onTimeUpdate={onTimeUpdate}
      />,
    );

    staleCallback(0, {} as VideoFrameCallbackMetadata);
    expect(onTimeUpdate).toHaveBeenCalledTimes(callsBeforeSwitch);
    expect(HTMLVideoElement.prototype.cancelVideoFrameCallback).toHaveBeenCalled();
  });

  it('cancels and guards the animation-frame fallback on a source change', () => {
    delete (HTMLVideoElement.prototype as Partial<HTMLVideoElement>).requestVideoFrameCallback;
    delete (HTMLVideoElement.prototype as Partial<HTMLVideoElement>).cancelVideoFrameCallback;
    let staleAnimationFrame: FrameRequestCallback | undefined;
    const requestAnimationFrameSpy = vi.spyOn(window, 'requestAnimationFrame')
      .mockImplementation((callback) => {
        staleAnimationFrame = callback;
        return 42;
      });
    const cancelAnimationFrameSpy = vi.spyOn(window, 'cancelAnimationFrame')
      .mockImplementation(() => undefined);

    const { onTimeUpdate, rerender } = renderPlayer(videoA, undefined);
    const player = document.querySelector('video') as HTMLVideoElement;
    Object.defineProperty(player, 'paused', { configurable: true, value: false });
    Object.defineProperty(player, 'ended', { configurable: true, value: false });
    player.dispatchEvent(new Event('play'));
    expect(requestAnimationFrameSpy).toHaveBeenCalledOnce();
    expect(staleAnimationFrame).toBeTypeOf('function');

    const callsBeforeSwitch = onTimeUpdate.mock.calls.length;
    rerender(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoB}
        selectedOnly={false}
        showBoxes
        onSelectTrack={vi.fn()}
        onTimeUpdate={onTimeUpdate}
      />,
    );
    staleAnimationFrame?.(0);

    expect(cancelAnimationFrameSpy).toHaveBeenCalledWith(42);
    expect(onTimeUpdate).toHaveBeenCalledTimes(callsBeforeSwitch);
  });

  it('reports a current media decoding error without removing pose data', () => {
    const onMediaError = vi.fn();
    render(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoA}
        overlay={overlay}
        selectedTrack={7}
        selectedOnly={false}
        showBoxes
        onSelectTrack={vi.fn()}
        onTimeUpdate={vi.fn()}
        onMediaError={onMediaError}
      />,
    );
    const player = document.querySelector('video') as HTMLVideoElement;
    fireEvent.error(player);
    expect(onMediaError).toHaveBeenCalledOnce();
    expect(screen.getByText('W7')).toBeInTheDocument();
  });

  it('renders the running score and fall inhibition score if features are provided', () => {
    render(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoA}
        overlay={overlay}
        selectedTrack={7}
        selectedOnly={false}
        showBoxes
        features={dummyFeatures}
        currentFrame={10}
        onSelectTrack={vi.fn()}
        onTimeUpdate={vi.fn()}
      />,
    );
    expect(screen.getByText('W7 · R:0.85 · FI:0.15')).toBeInTheDocument();
  });

  it('renders the consecutive running frame count if in a running segment', () => {
    const segments = [{
      segment_id: 'seg-1',
      track_id: 7,
      start_frame: 5,
      end_frame: 20,
      label: 'running' as const,
      quality_status: 'good',
      include_in_export: 1,
      source_type: 'manual',
    }];
    render(
      <PoseVideoPlayer
        projectId="factory floor"
        video={videoA}
        overlay={overlay}
        selectedTrack={7}
        selectedOnly={false}
        showBoxes
        features={dummyFeatures}
        currentSegments={segments}
        currentFrame={10}
        onSelectTrack={vi.fn()}
        onTimeUpdate={vi.fn()}
      />,
    );
    expect(screen.getByText('W7 · running · R:0.85 · FI:0.15 · RC:6')).toBeInTheDocument();
  });
});
