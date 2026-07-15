import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ShortcutGuideOverlay } from './ShortcutGuideOverlay';

describe('ShortcutGuideOverlay', () => {
  it('uses individual key blocks and separates its two shortcut groups', () => {
    render(<ShortcutGuideOverlay visible />);

    expect(screen.getByText('Playback and navigation')).toBeInTheDocument();
    const editing = screen.getByText('Labels and editing').closest('section');
    expect(editing).toHaveClass('sm:border-l');
    expect(screen.getAllByText('Shift')).toHaveLength(2);
    expect(screen.getAllByText('Ctrl').every((key) => key.closest('kbd') !== null)).toBe(true);
    expect(screen.getByText('Z').closest('kbd')).toBeInTheDocument();
  });
});
