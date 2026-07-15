import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ProcessingQueue } from './ProcessingQueue';

describe('ProcessingQueue', () => {
  it('uses one batch bar instead of a bar for every processing job', () => {
    render(<ProcessingQueue remainingVideos={2} totalVideos={3} jobs={[
      { job_id: 'done', video_id: 'v1', stage: 'canonicalize', status: 'completed', priority: 1, progress: 1 },
      { job_id: 'active', video_id: 'v2', stage: 'pose_track', status: 'running', priority: 1, progress: 0.5 },
      { job_id: 'queued', video_id: 'v3', stage: 'canonicalize', status: 'queued', priority: 1, progress: 0 },
    ]} />);
    expect(screen.getByText('Detecting and tracking workers')).toBeInTheDocument();
    expect(screen.queryByText('Preparing video')).not.toBeInTheDocument();
    expect(screen.queryByText(/Canonicalize/i)).not.toBeInTheDocument();
    expect(screen.getByText('2 remaining / 3 videos')).toBeInTheDocument();
    expect(screen.getByLabelText('2 remaining of 3 videos')).toBeInTheDocument();
    expect(screen.queryByTitle('Pause')).not.toBeInTheDocument();
  });
});
