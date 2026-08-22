import { act, renderHook } from '@testing-library/react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { deleteImage, renameSequential, setApproval } from '../../../api/client';
import { useWorkspaceActions } from './useWorkspaceActions';

vi.mock('../../../api/client', () => ({
  autoLabelAll: vi.fn(),
  autoLabelImage: vi.fn(),
  deleteImage: vi.fn(),
  exportAll: vi.fn(),
  renameSequential: vi.fn(),
  setApproval: vi.fn(),
  uploadImages: vi.fn(),
}));

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

function renderActions() {
  const flushPendingLabels = vi.fn().mockResolvedValue(undefined);
  const refreshImages = vi.fn().mockResolvedValue(undefined);
  const loadLabels = vi.fn().mockResolvedValue(undefined);
  const setSelectedImage = vi.fn();
  const clearAfterRename = vi.fn();
  const clearAfterDelete = vi.fn();

  const hook = renderHook(() => useWorkspaceActions({
    selectedTaskId: 'ppe',
    selectedImage: 'image.jpg',
    images: [
      { name: 'image.jpg', has_label: false, is_approved: false, image_url: '/media/ppe/images/image.jpg' },
      { name: 'next.jpg', has_label: false, is_approved: false, image_url: '/media/ppe/images/next.jpg' },
    ],
    setSelectedImage,
    refreshImages,
    flushPendingLabels,
    loadLabels,
    clearAfterRename,
    clearAfterDelete,
  }));

  return {
    ...hook,
    flushPendingLabels,
    refreshImages,
    setSelectedImage,
    clearAfterRename,
    clearAfterDelete,
  };
}

describe('useWorkspaceActions', () => {
  it('confirms a sequential rename once before running the workflow', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    vi.mocked(renameSequential).mockResolvedValue();
    const { result, flushPendingLabels, refreshImages, clearAfterRename } = renderActions();

    await act(async () => {
      await result.current.handleRenameSequential();
    });

    expect(confirm).toHaveBeenCalledTimes(1);
    expect(flushPendingLabels).toHaveBeenCalledTimes(1);
    expect(renameSequential).toHaveBeenCalledWith('ppe');
    expect(clearAfterRename).toHaveBeenCalledTimes(1);
    expect(refreshImages).toHaveBeenCalledWith('ppe');
  });

  it('refreshes approval state and advances after an approval', async () => {
    vi.mocked(setApproval).mockResolvedValue();
    const { result, refreshImages, setSelectedImage } = renderActions();

    await act(async () => {
      await result.current.handleApprovalChange(true);
    });

    expect(setApproval).toHaveBeenCalledWith('ppe', 'image.jpg', true);
    expect(refreshImages).toHaveBeenCalledWith('ppe');
    expect(setSelectedImage).toHaveBeenCalledWith('next.jpg');
  });

  it('flushes pending labels before changing the active image', async () => {
    const { result, flushPendingLabels, setSelectedImage } = renderActions();

    await act(async () => {
      await result.current.handleSelectImage('next.jpg');
    });

    expect(flushPendingLabels).toHaveBeenCalledTimes(1);
    expect(setSelectedImage).toHaveBeenCalledWith('next.jpg');
    expect(flushPendingLabels.mock.invocationCallOrder[0]).toBeLessThan(setSelectedImage.mock.invocationCallOrder[0]);
  });

  it('deletes the active image and clears stale workspace state before refreshing', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    vi.mocked(deleteImage).mockResolvedValue();
    const { result, refreshImages, clearAfterDelete } = renderActions();
    const event = { stopPropagation: vi.fn() } as unknown as ReactMouseEvent;

    await act(async () => {
      await result.current.handleDeleteImage(event, 'image.jpg');
    });

    expect(event.stopPropagation).toHaveBeenCalledTimes(1);
    expect(deleteImage).toHaveBeenCalledWith('ppe', 'image.jpg');
    expect(clearAfterDelete).toHaveBeenCalledTimes(1);
    expect(refreshImages).toHaveBeenCalledWith('ppe');
  });
});
