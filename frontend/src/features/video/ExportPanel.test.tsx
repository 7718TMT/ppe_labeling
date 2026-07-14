import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  createVideoExport,
  downloadVideoExport,
  getVideoExports,
  validateVideoExport,
} from '../../api/client';
import { ExportPanel } from './ExportPanel';

vi.mock('../../api/client', () => ({
  createVideoExport: vi.fn(),
  downloadVideoExport: vi.fn(),
  getVideoExports: vi.fn(),
  validateVideoExport: vi.fn(),
}));

describe('ExportPanel', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('downloads the completed ZIP after its queued export finishes', async () => {
    vi.mocked(createVideoExport).mockResolvedValue({
      queued: true,
      export: { export_id: 'export-1', status: 'queued', created_at: '2026-07-14' },
      validation: { errors: [], warnings: [] },
    });
    vi.mocked(getVideoExports).mockResolvedValue([{
      export_id: 'export-1', status: 'completed', created_at: '2026-07-14', finished_at: '2026-07-14',
    }]);
    render(<ExportPanel projectId="project-1" />);

    fireEvent.click(screen.getByRole('button', { name: 'Create export' }));
    await waitFor(() => expect(downloadVideoExport).toHaveBeenCalledWith('project-1', 'export-1'));
    expect(screen.getByRole('button', { name: 'Download ZIP' })).toBeInTheDocument();
  });

  it('shows validation errors without queuing a download', async () => {
    vi.mocked(createVideoExport).mockResolvedValue({
      queued: false,
      validation: { errors: ['No included videos are approved'], warnings: [] },
    });
    render(<ExportPanel projectId="project-1" />);

    fireEvent.click(screen.getByRole('button', { name: 'Create export' }));
    expect(await screen.findByText('Resolve validation errors first.')).toBeInTheDocument();
    expect(downloadVideoExport).not.toHaveBeenCalled();
  });
});
