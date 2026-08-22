import {
  cleanup, fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api/client';
import type { BehaviorInferenceWorkspace, VideoItem } from '../types';
import { BehaviorInference } from './BehaviorInference';


vi.mock('../api/client', () => ({
  deleteVideo: vi.fn(),
  getBehaviorInferenceResults: vi.fn(),
  getBehaviorInferenceWorkspace: vi.fn(),
  getPoseOverlay: vi.fn(),
  importBehaviorInferenceVideos: vi.fn(),
  videoThumbnailUrl: vi.fn(
    (_projectId: string, videoId: string) => `/thumbnail/${videoId}`,
  ),
  videoMediaUrl: vi.fn(() => '/media/inference.mp4'),
}));

const PROJECT = {
  project_id: 'inference',
  name: 'Behavior inference',
  config: {},
  created_at: '',
  updated_at: '',
};

function video(
  videoId: string,
  filename: string,
  processingStatus: string,
  updatedAt: string,
): VideoItem {
  return {
    video_id: videoId,
    project_id: PROJECT.project_id,
    filename,
    original_fps: 24,
    canonical_fps: 24,
    original_frame_count: 60,
    canonical_frame_count: 60,
    duration_seconds: 2.5,
    width: 320,
    height: 240,
    processing_status: processingStatus,
    annotation_status: 'unlabeled',
    quality_status: 'good',
    annotation_revision: 0,
    is_approved: 0,
    include_in_export: 1,
    updated_at: updatedAt,
  };
}

describe('Behavior inference workspace', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it('presents a read-only upload workspace without annotation controls', async () => {
    vi.mocked(api.getBehaviorInferenceWorkspace).mockResolvedValue({
      project: PROJECT,
      videos: [],
      jobs: [],
      model: { name: 'Behavior XGBoost', version: 'test' },
    });

    render(
      <MemoryRouter>
        <BehaviorInference />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Behavior XGBoost')).toBeInTheDocument();
    expect(screen.getByText('Upload videos')).toBeInTheDocument();
    expect(screen.getByText(/upload a video to run behavior inference/i))
      .toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /split|merge|delete/i }))
      .not.toBeInTheDocument();
    expect(screen.queryByText(/threshold settings|training/i))
      .not.toBeInTheDocument();
  });

  it('orders ready videos first and deletes through the existing video API', async () => {
    const ready = video('ready', 'ready.mp4', 'feature_ready', '2026-07-21');
    const processing = video('processing', 'processing.mp4', 'imported', '2026-07-22');
    const initial: BehaviorInferenceWorkspace = {
      project: PROJECT,
      videos: [processing, ready],
      jobs: [{
        job_id: 'job-1',
        project_id: PROJECT.project_id,
        video_id: processing.video_id,
        stage: 'pose_track',
        status: 'running',
        priority: 1,
        progress: 0.5,
      }],
      model: { name: 'Behavior XGBoost', version: 'test' },
    };
    vi.mocked(api.getBehaviorInferenceWorkspace)
      .mockResolvedValueOnce(initial)
      .mockResolvedValue({ ...initial, videos: [processing] });
    vi.mocked(api.deleteVideo).mockResolvedValue();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);

    const { container } = render(
      <MemoryRouter>
        <BehaviorInference />
      </MemoryRouter>,
    );

    const cards = await screen.findAllByRole('button', { name: /^Open / });
    expect(cards.map((card) => card.getAttribute('aria-label'))).toEqual([
      'Open ready.mp4',
      'Open processing.mp4',
    ]);
    expect(container.querySelectorAll('img')[0]).toHaveAttribute(
      'src',
      '/thumbnail/ready',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Delete ready.mp4' }));
    await waitFor(() => {
      expect(api.deleteVideo).toHaveBeenCalledWith('inference', 'ready');
    });
    expect(confirm).toHaveBeenCalledWith(
      'Delete "ready.mp4"? This cannot be undone.',
    );
  });

  it('keeps the player controls and timeline in the fullscreen surface', async () => {
    const item = video('processing', 'processing.mp4', 'imported', '2026-07-22');
    vi.mocked(api.getBehaviorInferenceWorkspace).mockResolvedValue({
      project: PROJECT,
      videos: [item],
      jobs: [],
      model: { name: 'Behavior XGBoost', version: 'test' },
    });

    const fullscreenElementDescriptor = Object.getOwnPropertyDescriptor(
      document,
      'fullscreenElement',
    );
    const exitFullscreenDescriptor = Object.getOwnPropertyDescriptor(
      document,
      'exitFullscreen',
    );
    let currentFullscreenElement: Element | null = null;
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => currentFullscreenElement,
    });
    const exitFullscreen = vi.fn(async () => {
      currentFullscreenElement = null;
      document.dispatchEvent(new Event('fullscreenchange'));
    });
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });

    render(
      <MemoryRouter>
        <BehaviorInference />
      </MemoryRouter>,
    );

    const stage = await screen.findByTestId('inference-fullscreen-stage');
    const requestFullscreen = vi.fn(async () => {
      currentFullscreenElement = stage;
      document.dispatchEvent(new Event('fullscreenchange'));
    });
    Object.defineProperty(stage, 'requestFullscreen', {
      configurable: true,
      value: requestFullscreen,
    });

    expect(within(stage).getByLabelText('Inference frame timeline'))
      .toBeInTheDocument();
    fireEvent.click(within(stage).getByRole('button', {
      name: 'Enter fullscreen',
    }));
    await waitFor(() => expect(requestFullscreen).toHaveBeenCalledOnce());
    expect(within(stage).getByRole('button', { name: 'Exit fullscreen' }))
      .toBeInTheDocument();
    expect(within(stage).getByLabelText('Inference frame timeline'))
      .toBeInTheDocument();

    fireEvent.click(within(stage).getByRole('button', {
      name: 'Exit fullscreen',
    }));
    await waitFor(() => expect(exitFullscreen).toHaveBeenCalledOnce());

    if (fullscreenElementDescriptor) {
      Object.defineProperty(
        document,
        'fullscreenElement',
        fullscreenElementDescriptor,
      );
    } else {
      Reflect.deleteProperty(document, 'fullscreenElement');
    }
    if (exitFullscreenDescriptor) {
      Object.defineProperty(
        document,
        'exitFullscreen',
        exitFullscreenDescriptor,
      );
    } else {
      Reflect.deleteProperty(document, 'exitFullscreen');
    }
  });
});
