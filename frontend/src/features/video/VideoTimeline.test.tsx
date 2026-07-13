import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { VideoTimeline } from './VideoTimeline';

describe('VideoTimeline', () => {
  it('renders the LABEL bar with human segments and suggestion overlays', () => {
    const onSegment = vi.fn();
    const onSuggestion = vi.fn();
    render(
      <VideoTimeline
        frameCount={120}
        currentFrame={20}
        source="Threshold"
        selectedSegment="s1"
        onFrame={vi.fn()}
        onSegment={onSegment}
        onSuggestion={onSuggestion}
        segments={[{
          segment_id: 's1',
          track_id: 1,
          start_frame: 0,
          end_frame: 20,
          label: 'others',
          quality_status: 'good',
          include_in_export: 1,
          needs_review: 0,
          source_type: 'manual',
        }]}
        suggestions={[{
          suggestion_id: 'g1',
          track_id: 1,
          start_frame: 30,
          end_frame: 50,
          suggested_label: 'falling',
          confidence: 0.9,
          review_status: 'pending',
        }]}
      />,
    );
    // Segment should render and be clickable
    const segmentBtn = screen.getByTitle('others frames 0–20');
    fireEvent.click(segmentBtn);
    expect(onSegment).toHaveBeenCalled();

    // Suggestion overlay should render and be clickable
    const sugBtn = screen.getByTitle(/Threshold suggestion: falling/);
    fireEvent.click(sugBtn);
    expect(onSuggestion).toHaveBeenCalled();

    // Selected segment should have ring class
    expect(segmentBtn).toHaveClass('ring-1');
  });
});
