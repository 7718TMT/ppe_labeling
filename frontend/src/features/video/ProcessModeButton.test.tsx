import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SuggestionModeButton } from './ProcessModeButton';

describe('SuggestionModeButton', () => {
  afterEach(cleanup);

  it('runs the displayed mode immediately from the main button', () => {
    const generate = vi.fn();
    render(<SuggestionModeButton source="Threshold" modelAvailable onSourceChange={vi.fn()} onGenerate={generate} />);
    fireEvent.click(screen.getByRole('button', { name: 'Suggestions: Threshold' }));
    expect(generate).toHaveBeenCalledOnce();
  });

  it('keeps the selected mode visible while processing', () => {
    render(<SuggestionModeButton source="AI" modelAvailable generating onSourceChange={vi.fn()} onGenerate={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Generating: AI' })).toBeDisabled();
  });

  it('changes mode only through the arrow menu and disables an unavailable model', () => {
    const change = vi.fn();
    render(<SuggestionModeButton source="Threshold" modelAvailable={false} onSourceChange={change} onGenerate={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Choose suggestion source' }));
    expect(screen.getByRole('menuitemradio', { name: /AI/ })).toBeDisabled();
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Threshold' }));
    expect(change).toHaveBeenCalledWith('Threshold');
  });

  it('keeps Off as a display-only selection', () => {
    render(<SuggestionModeButton source="Off" modelAvailable onSourceChange={vi.fn()} onGenerate={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Suggestions: Off' })).toBeDisabled();
  });

  it('allows choosing a source before a video is selected for import defaults', () => {
    const change = vi.fn();
    render(<SuggestionModeButton source="Threshold" disabled modelAvailable onSourceChange={change} onGenerate={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Suggestions: Threshold' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Choose suggestion source' }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'AI' }));
    expect(change).toHaveBeenCalledWith('AI');
  });
});
