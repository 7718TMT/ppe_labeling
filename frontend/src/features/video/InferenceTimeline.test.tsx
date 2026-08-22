import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { BehaviorEvent, VideoTrack } from '../../types';
import {
  buildInferenceTimelineSegments, InferenceTimeline,
} from './InferenceTimeline';


const EVENT: BehaviorEvent = {
  suggestion_id: 'event-1',
  track_id: 2,
  start_frame: 20,
  end_frame: 40,
  suggested_label: 'falling',
  confidence: 0.9,
};

const TRACKS: VideoTrack[] = [1, 2].map((trackId) => ({
  track_id: trackId,
  start_frame: 0,
  end_frame: 100,
  avg_keypoint_confidence: 0.9,
  valid_frame_ratio: 1,
  missing_ankle_ratio: 0,
  quality_status: 'good',
  include_in_export: 1,
}));

describe('InferenceTimeline', () => {
  it('shows frame previews and seeks by frame position or event', () => {
    const onFrame = vi.fn();
    const onSegment = vi.fn();
    render(
      <InferenceTimeline
        frameCount={101}
        currentFrame={25}
        mediaUrl="/media/video.mp4"
        tracks={TRACKS}
        events={[EVENT]}
        selectedTrack={2}
        onFrame={onFrame}
        onSegment={onSegment}
      />,
    );

    const timeline = screen.getByLabelText('Inference frame timeline');
    const previewStrip = timeline.querySelector('.h-20') as HTMLDivElement;
    vi.spyOn(previewStrip, 'getBoundingClientRect').mockReturnValue({
      bottom: 80,
      height: 80,
      left: 0,
      right: 100,
      top: 0,
      width: 100,
      x: 0,
      y: 0,
      toJSON: () => undefined,
    });

    expect(screen.getByText('FRAME PREVIEW')).toBeInTheDocument();
    expect(screen.getByText('W1')).toBeInTheDocument();
    expect(screen.getByText('W2')).toHaveClass('text-primary');
    fireEvent.click(previewStrip, { clientX: 50 });
    expect(onFrame).toHaveBeenCalledWith(50);

    fireEvent.click(screen.getByRole('button', {
      name: 'Worker 2 falling, frames 20 to 40',
    }));
    expect(onSegment).toHaveBeenCalledWith(expect.objectContaining({
      trackId: 2,
      label: 'falling',
      startFrame: 20,
    }));
    expect(screen.getByRole('button', {
      name: 'Worker 1 others, frames 0 to 100',
    })).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'Worker 2 others, frames 41 to 100',
    })).toBeInTheDocument();
  });

  it('builds a complete non-overlapping label timeline', () => {
    expect(buildInferenceTimelineSegments(TRACKS, [EVENT], 101)
      .filter((segment) => segment.trackId === 2)
      .map((segment) => [segment.label, segment.startFrame, segment.endFrame]))
      .toEqual([
        ['others', 0, 19],
        ['falling', 20, 40],
        ['others', 41, 100],
      ]);
  });
});
