import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TrimTimeline } from './TrimTimeline';

describe('TrimTimeline', () => {
  it('shows a thumbnail strip without worker labels and commits a dragged trim head', () => {
    const onRangeCommit = vi.fn();
    render(<TrimTimeline frameCount={120} currentFrame={20} mediaUrl="/video.mp4" range={{ start: 0, end: 119 }} onFrame={vi.fn()} onRangeCommit={onRangeCommit} />);
    const timeline = screen.getByLabelText('Video trim timeline').querySelector('div.relative.h-24') as HTMLDivElement;
    vi.spyOn(timeline, 'getBoundingClientRect').mockReturnValue({ x: 0, y: 0, width: 120, height: 90, top: 0, left: 0, right: 120, bottom: 90, toJSON: () => ({}) });
    const start = screen.getByRole('button', { name: 'Drag trim start' });
    fireEvent.pointerDown(start, { clientX: 0, pointerId: 1 });
    fireEvent.pointerMove(start, { clientX: 20, pointerId: 1 });
    fireEvent.pointerUp(start, { clientX: 20, pointerId: 1 });
    expect(onRangeCommit).toHaveBeenCalledWith({ start: 20, end: 119 });
    expect(screen.queryByText('W1')).not.toBeInTheDocument();
  });
});