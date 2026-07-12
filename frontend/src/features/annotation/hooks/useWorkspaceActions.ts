import { useCallback, useState } from 'react';
import type { MouseEvent } from 'react';

import {
  autoLabelAll,
  autoLabelImage,
  deleteImage,
  exportAll,
  renameSequential,
  setApproval,
  uploadImages,
} from '../../../api/client';
import type { ImageData } from '../../../types';

interface UseWorkspaceActionsOptions {
  selectedTaskId: string;
  selectedImage: string | null;
  images: ImageData[];
  setSelectedImage: (filename: string | null) => void;
  refreshImages: (taskId?: string) => Promise<void>;
  flushPendingLabels: () => Promise<void>;
  loadLabels: (filename: string) => Promise<void>;
  clearAfterRename: () => void;
  clearAfterDelete: () => void;
}

/** Coordinates dataset-management actions around the current image editor. */
export function useWorkspaceActions({
  selectedTaskId,
  selectedImage,
  images,
  setSelectedImage,
  refreshImages,
  flushPendingLabels,
  loadLabels,
  clearAfterRename,
  clearAfterDelete,
}: UseWorkspaceActionsOptions) {
  const [processingAction, setProcessingAction] = useState<string | null>(null);

  const handleSelectImage = useCallback(async (filename: string) => {
    await flushPendingLabels();
    setSelectedImage(filename);
  }, [flushPendingLabels, setSelectedImage]);

  const goToNext = useCallback(async () => {
    if (!selectedImage || images.length === 0) return;
    const currentIndex = images.findIndex((image) => image.name === selectedImage);
    if (currentIndex < images.length - 1) {
      await flushPendingLabels();
      setSelectedImage(images[currentIndex + 1].name);
    }
  }, [flushPendingLabels, images, selectedImage, setSelectedImage]);

  const goToPrev = useCallback(async () => {
    if (!selectedImage || images.length === 0) return;
    const currentIndex = images.findIndex((image) => image.name === selectedImage);
    if (currentIndex > 0) {
      await flushPendingLabels();
      setSelectedImage(images[currentIndex - 1].name);
    }
  }, [flushPendingLabels, images, selectedImage, setSelectedImage]);

  const handleProcess = useCallback(async () => {
    setProcessingAction('autoLabelAll');
    try {
      await flushPendingLabels();
      await autoLabelAll(selectedTaskId);
      await refreshImages(selectedTaskId);
      if (selectedImage) await loadLabels(selectedImage);
      alert('Processing completed!');
    } catch (error) {
      console.error('Processing failed:', error);
      alert('Processing failed. Check console for details.');
    } finally {
      setProcessingAction(null);
    }
  }, [flushPendingLabels, loadLabels, refreshImages, selectedImage, selectedTaskId]);

  const handleUploadImages = useCallback(async (files: File[]) => {
    setProcessingAction('upload');
    try {
      await flushPendingLabels();
      await uploadImages(selectedTaskId, files);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Check console for details.');
    } finally {
      setProcessingAction(null);
    }
  }, [flushPendingLabels, refreshImages, selectedTaskId]);

  const handleAutoLabelCurrent = useCallback(async () => {
    setProcessingAction('autoLabelCurrent');
    if (!selectedImage) return;
    try {
      await autoLabelImage(selectedTaskId, selectedImage);
      await loadLabels(selectedImage);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Auto-label failed:', error);
      alert('Auto-label failed. Check console for details.');
    } finally {
      setProcessingAction(null);
    }
  }, [loadLabels, refreshImages, selectedImage, selectedTaskId]);

  const handleExportAll = useCallback(async () => {
    setProcessingAction('exportAll');
    try {
      await flushPendingLabels();
      exportAll(selectedTaskId);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Check console for details.');
    } finally {
      setProcessingAction(null);
    }
  }, [flushPendingLabels, selectedTaskId]);

  const handleRenameSequential = useCallback(async () => {
    if (!confirm('Rename all images and matching labels in this task to image_00000, image_00001, and so on?')) return;
    setProcessingAction('renameSequential');
    try {
      await flushPendingLabels();
      await renameSequential(selectedTaskId);
      clearAfterRename();
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Rename failed:', error);
      alert('Rename failed. Check console for details.');
    } finally {
      setProcessingAction(null);
    }
  }, [clearAfterRename, flushPendingLabels, refreshImages, selectedTaskId]);

  const handleApprovalChange = useCallback(async (isApproved: boolean) => {
    if (!selectedImage) return;
    setProcessingAction('approve');
    try {
      await setApproval(selectedTaskId, selectedImage, isApproved);
      await refreshImages(selectedTaskId);
      if (isApproved) await goToNext();
    } catch (error) {
      console.error('Approval update failed:', error);
      alert('Approval update failed. Check console.');
    } finally {
      setProcessingAction(null);
    }
  }, [goToNext, refreshImages, selectedImage, selectedTaskId]);

  const handleReset = useCallback(async () => {
    if (!selectedImage) return;
    if (!confirm('Are you sure? This will remove manual changes for this image and re-run AI detection.')) return;
    try {
      await autoLabelImage(selectedTaskId, selectedImage);
      await loadLabels(selectedImage);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Reset failed:', error);
      alert('Reset failed. Check console.');
    }
  }, [loadLabels, refreshImages, selectedImage, selectedTaskId]);

  const handleDeleteImage = useCallback(async (event: MouseEvent, filename: string) => {
    event.stopPropagation();
    if (!confirm(`Are you sure you want to delete ${filename}? This cannot be undone.`)) return;
    try {
      await deleteImage(selectedTaskId, filename);
      if (selectedImage === filename) clearAfterDelete();
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Error deleting image:', error);
      alert('Failed to delete image.');
    }
  }, [clearAfterDelete, refreshImages, selectedImage, selectedTaskId]);

  return {
    processingAction,
    handleSelectImage,
    goToNext,
    goToPrev,
    handleProcess,
    handleUploadImages,
    handleAutoLabelCurrent,
    handleExportAll,
    handleRenameSequential,
    handleApprovalChange,
    handleReset,
    handleDeleteImage,
  };
}
