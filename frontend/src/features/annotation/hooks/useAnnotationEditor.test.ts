import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { getLabels, saveLabels } from '../../../api/client';
import type { BBox } from '../../../types';
import { useAnnotationEditor } from './useAnnotationEditor';

vi.mock('../../../api/client', () => ({
  getLabels: vi.fn(),
  saveLabels: vi.fn(),
}));

const box: BBox = {
  class_id: 1,
  x_center: 0.5,
  y_center: 0.5,
  w: 0.2,
  h: 0.2,
};

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('useAnnotationEditor', () => {
  it('autosaves a dirty label change after one second', async () => {
    vi.useFakeTimers();
    vi.mocked(saveLabels).mockResolvedValue();
    const refreshImages = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useAnnotationEditor({
      selectedTaskId: 'ppe',
      selectedImage: 'image.jpg',
      refreshImages,
    }));

    act(() => {
      result.current.pushToHistory([box]);
    });

    expect(saveLabels).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(saveLabels).toHaveBeenCalledWith('ppe', 'image.jpg', [box]);
    expect(refreshImages).toHaveBeenCalledWith('ppe');
  });

  it('discards a late label response after switching task and image', async () => {
    let resolveLabels: ((value: BBox[]) => void) | undefined;
    vi.mocked(getLabels).mockImplementation(() => new Promise((resolve) => {
      resolveLabels = resolve;
    }));
    const refreshImages = vi.fn().mockResolvedValue(undefined);
    const { result, rerender } = renderHook(
      ({ taskId, image }) => useAnnotationEditor({
        selectedTaskId: taskId,
        selectedImage: image,
        refreshImages,
      }),
      { initialProps: { taskId: 'ppe', image: 'ppe.jpg' } },
    );

    act(() => {
      void result.current.loadLabels('ppe.jpg');
    });
    rerender({ taskId: 'safety_signs', image: 'sign.jpg' });
    await act(async () => {
      resolveLabels?.([box]);
    });

    expect(result.current.labels).toEqual([]);
    expect(result.current.isDirty).toBe(false);
  });
});
