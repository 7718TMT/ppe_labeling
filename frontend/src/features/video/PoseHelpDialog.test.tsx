import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PoseHelpDialog } from './PoseHelpDialog';

describe('PoseHelpDialog', () => {
  afterEach(cleanup);

  it('explains the workspace zones, controls, workflow, statuses, and deletion', () => {
    render(<PoseHelpDialog open onClose={vi.fn()} />);
    expect(screen.getByText('Workspace zones')).toBeInTheDocument();
    expect(screen.getByText('Video browser and dataset actions')).toBeInTheDocument();
    expect(screen.getByText('Playback, timeline, and video toolbar')).toBeInTheDocument();
    expect(screen.getByText('Workers and segments')).toBeInTheDocument();
    expect(screen.getByText(/loss of balance begins/)).toBeInTheDocument();
    expect(screen.getByText(/Space plays or pauses/)).toBeInTheDocument();
    expect(screen.getByText('Video status filters')).toBeInTheDocument();
    expect(screen.getByText(/The two filters work together/)).toBeInTheDocument();
    expect(screen.getByText('Approval, export, and recovery')).toBeInTheDocument();
  });

  it('filters topics and closes with Escape', () => {
    const close = vi.fn();
    render(<PoseHelpDialog open onClose={close} />);
    fireEvent.change(screen.getByPlaceholderText(/Search workflow/), { target: { value: 'export' } });
    expect(screen.getByText('Video browser and dataset actions')).toBeInTheDocument();
    expect(screen.queryByText('Running')).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(close).toHaveBeenCalledOnce();
  });
});
