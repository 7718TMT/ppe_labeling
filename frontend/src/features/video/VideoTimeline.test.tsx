import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { VideoTimeline } from './VideoTimeline';

describe('VideoTimeline', () => {
  it('renders the LABEL bar with saved annotation segments only', () => {
    const onSegment = vi.fn();
    render(
      <VideoTimeline
        frameCount={120}
        currentFrame={20}
        selectedSegment="s1"
        onFrame={vi.fn()}
        onSegment={onSegment}
        segments={[{
          segment_id: 's1',
          track_id: 1,
          start_frame: 0,
          end_frame: 20,
          label: 'others',
          quality_status: 'good',
          include_in_export: 1,
          source_type: 'manual',
        }]}
      />,
    );
    // Segment should render and be clickable
    const segmentBtn = screen.getByTitle('others frames 0–20');
    fireEvent.click(segmentBtn);
    expect(onSegment).toHaveBeenCalled();

    // Selected segment should have ring class
    expect(segmentBtn).toHaveClass('ring-1');
    expect(screen.getByText('W1')).toBeInTheDocument();
    expect(screen.queryByText('QUALITY')).not.toBeInTheDocument();
  });

  it('previews a resize locally and commits only once on pointer release', () => {
    const onSegmentResize = vi.fn();
    render(
      <VideoTimeline
        frameCount={120}
        currentFrame={20}
        onFrame={vi.fn()}
        onSegment={vi.fn()}
        onSegmentResize={onSegmentResize}
        segments={[{
          segment_id: 's1', track_id: 1, start_frame: 0, end_frame: 20,
          label: 'others', quality_status: 'good', include_in_export: 1,
          source_type: 'manual',
        }]}
      />,
    );

    const handle = screen.getByLabelText('Drag segment end');
    fireEvent.pointerDown(handle, { clientX: 0, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: 1, pointerId: 1 });
    expect(onSegmentResize).not.toHaveBeenCalled();
    fireEvent.pointerUp(handle, { clientX: 1, pointerId: 1 });
    expect(onSegmentResize).toHaveBeenCalledTimes(1);
  });

  it('stops a dragged boundary immediately before the next segment', () => {
    const onSegmentResize = vi.fn();
    render(
      <VideoTimeline
        frameCount={120}
        currentFrame={20}
        onFrame={vi.fn()}
        onSegment={vi.fn()}
        onSegmentResize={onSegmentResize}
        segments={[
          { segment_id: 's1', track_id: 1, start_frame: 0, end_frame: 20, label: 'others', quality_status: 'good', include_in_export: 1, source_type: 'manual' },
          { segment_id: 's2', track_id: 1, start_frame: 40, end_frame: 80, label: 'running', quality_status: 'good', include_in_export: 1, source_type: 'manual' },
        ]}
      />,
    );

    const handles = screen.getAllByLabelText('Drag segment end');
    const handle = handles[handles.length - 2];
    fireEvent.pointerDown(handle, { clientX: 0, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: 100, pointerId: 1 });
    fireEvent.pointerUp(handle, { clientX: 100, pointerId: 1 });

    expect(onSegmentResize).toHaveBeenCalledWith('s1', 0, 39);
  });
});
