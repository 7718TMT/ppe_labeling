import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ProcessingQueue } from './ProcessingQueue';

describe('ProcessingQueue', () => {
  it('uses plain stage names and omits completed duplicate stages', () => {
    render(<ProcessingQueue remainingVideos={2} totalVideos={3} onControl={vi.fn()} jobs={[
      { job_id: 'done', video_id: 'v1', stage: 'canonicalize', status: 'completed', priority: 1, progress: 1 },
      { job_id: 'active', video_id: 'v1', stage: 'pose_track', status: 'failed', priority: 1, progress: 0.5, error_message: 'Pose model is unavailable' },
    ]} />);
    expect(screen.getByText('Detecting and tracking workers')).toBeInTheDocument();
    expect(screen.queryByText('Preparing video')).not.toBeInTheDocument();
    expect(screen.queryByText(/Canonicalize/i)).not.toBeInTheDocument();
    expect(screen.getByText('2 remaining / 3 videos')).toBeInTheDocument();
    expect(screen.getByLabelText('2 remaining of 3 videos')).toBeInTheDocument();
    expect(screen.getByText(/Detecting and tracking workers failed: Pose model is unavailable/)).toBeInTheDocument();
  });
});
