import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api/client';
import { Dashboard } from './Dashboard';

vi.mock('../api/client', () => ({
  getImages: vi.fn(),
  getTasks: vi.fn(),
}));

const TASKS = [
  { id: 'ppe', name: 'PPE', class_names: { 0: 'Person' } },
  { id: 'safety_signs', name: 'Safety Signs', class_names: { 0: 'Sign' } },
];

describe('Dashboard module navigation', () => {
  beforeEach(() => {
    vi.mocked(api.getTasks).mockResolvedValue(TASKS);
    vi.mocked(api.getImages).mockImplementation(async (taskId) => {
      if (taskId === 'ppe') {
        return [
          { name: 'one.jpg', has_label: true, is_approved: true, image_url: '/one.jpg' },
          { name: 'two.jpg', has_label: true, is_approved: false, image_url: '/two.jpg' },
        ];
      }
      return [
        { name: 'sign.jpg', has_label: true, is_approved: true, image_url: '/sign.jpg' },
      ];
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('offers PPE, Sign, and Pose from one product entry point', () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Open PPE labeling' })).toHaveAttribute('href', '/task/ppe');
    expect(screen.getByRole('link', { name: 'Open Sign labeling' })).toHaveAttribute('href', '/task/safety_signs');
    expect(screen.getByRole('link', { name: 'Open Pose labeling' })).toHaveAttribute('href', '/video');
  });

  it('shows image progress without changing module navigation', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    const ppeModule = screen.getByRole('link', { name: 'Open PPE labeling' });
    const signModule = screen.getByRole('link', { name: 'Open Sign labeling' });

    await waitFor(() => {
      expect(within(ppeModule).getByText('1 / 2 approved')).toBeInTheDocument();
      expect(within(signModule).getByText('1 / 1 approved')).toBeInTheDocument();
    });
    expect(within(ppeModule).getByText('50%')).toBeInTheDocument();
    expect(within(signModule).getByText('Completed')).toBeInTheDocument();
  });

  it('keeps all module routes available when progress cannot be loaded', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.mocked(api.getTasks).mockRejectedValue(new Error('offline'));

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('status')).toHaveTextContent('You can still open any labeling module.');
    expect(screen.getByRole('link', { name: 'Open PPE labeling' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Sign labeling' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Pose labeling' })).toBeInTheDocument();
    expect(consoleError).toHaveBeenCalledWith('Failed to load dashboard progress', expect.any(Error));
  });
});
