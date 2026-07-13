import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ProcessModeButton } from './ProcessModeButton';

describe('ProcessModeButton', () => {
  afterEach(cleanup);

  it('runs the displayed mode immediately from the main button', () => {
    const process = vi.fn();
    render(<ProcessModeButton mode="Threshold" modelAvailable onModeChange={vi.fn()} onProcess={process} />);
    fireEvent.click(screen.getByRole('button', { name: 'Process: Threshold' }));
    expect(process).toHaveBeenCalledOnce();
  });

  it('keeps the selected mode visible while processing', () => {
    render(<ProcessModeButton mode="Model" modelAvailable processing onModeChange={vi.fn()} onProcess={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Processing: Model' })).toBeDisabled();
  });

  it('changes mode only through the arrow menu and disables an unavailable model', () => {
    const change = vi.fn();
    render(<ProcessModeButton mode="Threshold" modelAvailable={false} onModeChange={change} onProcess={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Choose processing mode' }));
    expect(screen.getByRole('menuitemradio', { name: /Model/ })).toBeDisabled();
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Threshold' }));
    expect(change).toHaveBeenCalledWith('Threshold');
  });
});
