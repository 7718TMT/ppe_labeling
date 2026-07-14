import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PoseHelpDialog } from './PoseHelpDialog';

describe('PoseHelpDialog', () => {
  afterEach(cleanup);

  it('explains the workflow, class boundaries, statuses, controls, and deletion', () => {
    render(<PoseHelpDialog open onClose={vi.fn()} />);
    expect(screen.getByText('Basic workflow')).toBeInTheDocument();
    expect(screen.getByText(/loss of balance begins/)).toBeInTheDocument();
    expect(screen.getByText(/Space plays or pauses/)).toBeInTheDocument();
    expect(screen.getByText('Video status filters')).toBeInTheDocument();
    expect(screen.getByText(/The two filters work together/)).toBeInTheDocument();
    expect(screen.getByText('Select and delete items')).toBeInTheDocument();
  });

  it('filters topics and closes with Escape', () => {
    const close = vi.fn();
    render(<PoseHelpDialog open onClose={close} />);
    fireEvent.change(screen.getByPlaceholderText(/Search workflow/), { target: { value: 'trash' } });
    expect(screen.getByText('Select and delete items')).toBeInTheDocument();
    expect(screen.queryByText('Running')).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(close).toHaveBeenCalledOnce();
  });
});
