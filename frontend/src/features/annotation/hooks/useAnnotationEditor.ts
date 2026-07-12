import { useCallback, useEffect, useRef, useState } from 'react';

import { getLabels, saveLabels } from '../../../api/client';
import type { BBox } from '../../../types';

interface UseAnnotationEditorOptions {
  selectedTaskId: string;
  selectedImage: string | null;
  refreshImages: (taskId?: string) => Promise<void>;
}

/**
 * Owns label editing state and persistence. Canvas input remains in the
 * workspace so Konva event handling stays separate from label persistence.
 */
export function useAnnotationEditor({
  selectedTaskId,
  selectedImage,
  refreshImages,
}: UseAnnotationEditorOptions) {
  const [labels, setLabels] = useState<BBox[]>([]);
  const [history, setHistory] = useState<BBox[][]>([]);
  const [loading, setLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [drawingClass, setDrawingClass] = useState<number | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const labelRequestVersionRef = useRef(0);
  const activeTaskIdRef = useRef(selectedTaskId);
  const selectedImageRef = useRef(selectedImage);
  activeTaskIdRef.current = selectedTaskId;
  selectedImageRef.current = selectedImage;

  const resetForTask = useCallback(() => {
    setLabels([]);
    setHistory([]);
    setSelectedIndices([]);
    setDrawingClass(null);
    setIsDirty(false);
    setIsSaving(false);
  }, []);

  useEffect(() => {
    labelRequestVersionRef.current += 1;
    resetForTask();
  }, [resetForTask, selectedTaskId]);

  const loadLabels = useCallback(async (filename: string) => {
    const requestVersion = ++labelRequestVersionRef.current;
    const requestTaskId = selectedTaskId;
    setLoading(true);
    try {
      const loadedLabels = await getLabels(requestTaskId, filename);
      if (
        requestVersion !== labelRequestVersionRef.current
        || requestTaskId !== activeTaskIdRef.current
        || filename !== selectedImageRef.current
      ) return;
      setLabels(loadedLabels);
      setHistory([]);
      setIsDirty(false);
    } catch (error) {
      console.error('Error fetching labels:', error);
    } finally {
      if (requestVersion === labelRequestVersionRef.current) setLoading(false);
    }
  }, [selectedTaskId]);

  const persistLabels = useCallback(async (
    nextLabels = labels,
    options: { refresh?: boolean } = {},
  ) => {
    if (!selectedImage) return;
    const requestTaskId = selectedTaskId;
    const requestImage = selectedImage;
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }
    setIsSaving(true);
    try {
      await saveLabels(requestTaskId, requestImage, nextLabels);
      if (requestTaskId !== activeTaskIdRef.current || requestImage !== selectedImageRef.current) return;
      setIsDirty(false);
      if (options.refresh ?? true) {
        await refreshImages(requestTaskId);
      }
    } catch (error) {
      console.error('Error saving labels:', error);
    } finally {
      if (requestTaskId === activeTaskIdRef.current && requestImage === selectedImageRef.current) {
        setIsSaving(false);
      }
    }
  }, [labels, refreshImages, selectedImage, selectedTaskId]);

  const flushPendingLabels = useCallback(async () => {
    if (!selectedImage || !isDirty) return;
    await persistLabels(labels, { refresh: false });
  }, [isDirty, labels, persistLabels, selectedImage]);

  const autoSaveLabels = useCallback(async () => {
    await persistLabels(labels);
  }, [labels, persistLabels]);

  useEffect(() => {
    if (!selectedImage || !isDirty) return;
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    saveTimeoutRef.current = setTimeout(() => {
      void autoSaveLabels();
    }, 1000);

    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [autoSaveLabels, isDirty, labels, selectedImage, selectedTaskId]);

  const clearForNoImage = useCallback(() => {
    setLabels([]);
    setIsDirty(false);
  }, []);

  const clearAfterRename = useCallback(() => {
    setLabels([]);
    setHistory([]);
    setSelectedIndices([]);
  }, []);

  const prepareForLoadedImage = useCallback(() => {
    setHistory([]);
    setSelectedIndices([]);
    setDrawingClass(null);
  }, []);

  const pushToHistory = useCallback((nextLabels: BBox[]) => {
    setHistory((current) => [...current, labels]);
    setLabels(nextLabels);
    setIsDirty(true);
  }, [labels]);

  const undo = useCallback(() => {
    if (history.length === 0) return;
    const previous = history[history.length - 1];
    setHistory((current) => current.slice(0, -1));
    setLabels(previous);
    setSelectedIndices([]);
    setIsDirty(true);
  }, [history]);

  const toggleAddMode = useCallback((classId: number) => {
    setDrawingClass((current) => (current === classId ? null : classId));
    setSelectedIndices([]);
  }, []);

  const deleteSelected = useCallback(() => {
    if (selectedIndices.length === 0) return;
    pushToHistory(labels.filter((_, index) => !selectedIndices.includes(index)));
    setSelectedIndices([]);
  }, [labels, pushToHistory, selectedIndices]);

  const changeSelectedClass = useCallback((classId: number) => {
    if (selectedIndices.length === 0) return;
    const nextLabels = labels.map((box, index) => (
      selectedIndices.includes(index) ? { ...box, class_id: classId } : box
    ));
    pushToHistory(nextLabels);
    void persistLabels(nextLabels);
  }, [labels, persistLabels, pushToHistory, selectedIndices]);

  return {
    labels,
    setLabels,
    history,
    loading,
    isSaving,
    isDirty,
    setIsDirty,
    selectedIndices,
    setSelectedIndices,
    drawingClass,
    setDrawingClass,
    loadLabels,
    persistLabels,
    flushPendingLabels,
    clearForNoImage,
    clearAfterRename,
    prepareForLoadedImage,
    pushToHistory,
    undo,
    toggleAddMode,
    deleteSelected,
    changeSelectedClass,
  };
}
