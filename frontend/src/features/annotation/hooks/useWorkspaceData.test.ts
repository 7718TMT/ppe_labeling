import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { getImages, getTasks } from '../../../api/client';
import { useWorkspaceData } from './useWorkspaceData';


vi.mock('../../../api/client', () => ({
  getImages: vi.fn(),
  getTasks: vi.fn(),
}));


afterEach(() => {
  vi.clearAllMocks();
});


describe('useWorkspaceData', () => {
  it('keeps only the latest task image and approval state when requests resolve out of order', async () => {
    let resolvePpe: ((value: Awaited<ReturnType<typeof getImages>>) => void) | undefined;
    let resolveSigns: ((value: Awaited<ReturnType<typeof getImages>>) => void) | undefined;
    vi.mocked(getTasks).mockResolvedValue([
      { id: 'ppe', name: 'PPE', class_names: { 0: 'Person' } },
      { id: 'safety_signs', name: 'Safety Signs', class_names: { 0: 'Sign' } },
    ]);
    vi.mocked(getImages).mockImplementation((taskId) => new Promise((resolve) => {
      if (taskId === 'ppe') resolvePpe = resolve;
      else resolveSigns = resolve;
    }));

    const { result, rerender } = renderHook(
      ({ taskId }) => useWorkspaceData({ selectedTaskId: taskId }),
      { initialProps: { taskId: 'ppe' } },
    );

    rerender({ taskId: 'safety_signs' });
    await act(async () => {
      resolveSigns?.([
        { name: 'sign.jpg', has_label: false, is_approved: false, image_url: '/media/safety_signs/images/sign.jpg' },
      ]);
    });
    await act(async () => {
      resolvePpe?.([
        { name: 'ppe.jpg', has_label: true, is_approved: true, image_url: '/media/ppe/images/ppe.jpg' },
      ]);
    });

    await waitFor(() => expect(result.current.selectedImage).toBe('sign.jpg'));
    expect(result.current.images.map((image) => image.name)).toEqual(['sign.jpg']);
    expect(result.current.selectedImageApproved).toBe(false);
  });
});
