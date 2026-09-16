import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api/client';
import { DetectionInference } from './DetectionInference';

vi.mock('../api/client', () => ({
  deleteDetectionInferenceItem: vi.fn(),
  getDetectionInferenceItems: vi.fn(),
  getTasks: vi.fn(),
  uploadDetectionInferenceMedia: vi.fn(),
}));

const items = [
  { id: 'image-1', task_id: 'ppe', filename: 'worker.jpg', media_type: 'image' as const, source_url: '/source/image', result_url: '/result/image', detections: 3, created_at: '2026-08-22' },
  { id: 'video-1', task_id: 'ppe', filename: 'factory.mp4', media_type: 'video' as const, source_url: '/source/video', result_url: '/result/video', detections: 21, created_at: '2026-08-21' },
];

describe('PPE and Sign inference workspace', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  beforeEach(() => {
    vi.mocked(api.getTasks).mockResolvedValue([
      { id: 'ppe', name: 'PPE', class_names: { 0: 'Person', 1: 'Helmet', 2: 'Vest' } },
    ]);
  });

  it('loads mixed media and filters images or videos from the sidebar', async () => {
    vi.mocked(api.getDetectionInferenceItems).mockResolvedValue(items);
    render(<MemoryRouter initialEntries={['/ppe/inference']}><Routes><Route path="/:taskKey/inference" element={<DetectionInference />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole('button', { name: 'Open worker.jpg' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open factory.mp4' })).toBeInTheDocument();
    expect(await screen.findByText('Helmet')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Videos' }));
    expect(screen.queryByRole('button', { name: 'Open worker.jpg' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open factory.mp4' })).toBeInTheDocument();
  });

  it('uploads images and videos to the PPE model endpoint', async () => {
    vi.mocked(api.getDetectionInferenceItems).mockResolvedValue([]);
    vi.mocked(api.uploadDetectionInferenceMedia).mockResolvedValue([items[0]]);
    const { container } = render(<MemoryRouter initialEntries={['/ppe/inference']}><Routes><Route path="/:taskKey/inference" element={<DetectionInference />} /></Routes></MemoryRouter>);
    await screen.findByText(/upload an image or video/i);
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['image'], 'worker.jpg', { type: 'image/jpeg' });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => expect(api.uploadDetectionInferenceMedia).toHaveBeenCalledWith('ppe', [file]));
    expect(await screen.findByAltText('Inference result for worker.jpg')).toBeInTheDocument();
  });
});
