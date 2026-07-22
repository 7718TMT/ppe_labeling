import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { BehaviorHome } from './BehaviorHome';


describe('Behavior workflow chooser', () => {
  afterEach(cleanup);

  it('keeps labeling separate from read-only inference', () => {
    render(
      <MemoryRouter>
        <BehaviorHome />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Open Behavior Labeling' }))
      .toHaveAttribute('href', '/video');
    expect(screen.getByRole('link', { name: 'Open Behavior Inference' }))
      .toHaveAttribute('href', '/behavior/inference');
    expect(screen.queryByText(/threshold/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/training controls/i)).not.toBeInTheDocument();
  });
});
