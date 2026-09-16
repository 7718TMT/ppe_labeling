import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { ImageTaskHome } from './ImageTaskHome';

describe('image detection workflow chooser', () => {
  afterEach(cleanup);

  it('separates PPE labeling and inference', () => {
    render(<MemoryRouter initialEntries={['/ppe']}><Routes><Route path="/:taskKey" element={<ImageTaskHome />} /></Routes></MemoryRouter>);

    expect(screen.getByRole('link', { name: 'Open PPE Labeling' })).toHaveAttribute('href', '/task/ppe');
    expect(screen.getByRole('link', { name: 'Open PPE Inference' })).toHaveAttribute('href', '/ppe/inference');
  });

  it('separates Sign labeling and inference', () => {
    render(<MemoryRouter initialEntries={['/sign']}><Routes><Route path="/:taskKey" element={<ImageTaskHome />} /></Routes></MemoryRouter>);

    expect(screen.getByRole('link', { name: 'Open Sign Labeling' })).toHaveAttribute('href', '/task/safety_signs');
    expect(screen.getByRole('link', { name: 'Open Sign Inference' })).toHaveAttribute('href', '/sign/inference');
  });
});
