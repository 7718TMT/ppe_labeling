import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { getImages, getTasks } from '../../../api/client';
import { FALLBACK_CLASS_NAMES } from '../../../constants';
import type { ImageData, TaskInfo } from '../../../types';

interface UseWorkspaceDataOptions {
  selectedTaskId: string;
}

/** Owns task metadata and filesystem-backed image inventory for the workspace. */
export function useWorkspaceData({ selectedTaskId }: UseWorkspaceDataOptions) {
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [images, setImages] = useState<ImageData[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const activeTaskIdRef = useRef(selectedTaskId);
  activeTaskIdRef.current = selectedTaskId;

  const refreshTasks = useCallback(async () => {
    try {
      setTasks(await getTasks());
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  }, []);

  const refreshImages = useCallback(async (taskId?: string) => {
    const requestedTaskId = taskId ?? activeTaskIdRef.current;
    try {
      const imageList = await getImages(requestedTaskId);
      if (requestedTaskId !== activeTaskIdRef.current) return;
      setImages(imageList);
      setSelectedImage((current) => (
        current && imageList.some((image) => image.name === current)
          ? current
          : imageList[0]?.name ?? null
      ));
    } catch (error) {
      console.error('Error fetching images:', error);
    }
  }, []);

  useEffect(() => {
    void refreshTasks();
  }, [refreshTasks]);

  useEffect(() => {
    void refreshImages(selectedTaskId);
    setSelectedImage(null);
  }, [refreshImages, selectedTaskId]);

  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId),
    [selectedTaskId, tasks],
  );
  const selectedImageData = useMemo(
    () => images.find((image) => image.name === selectedImage),
    [images, selectedImage],
  );
  const classNames = useMemo<Record<number, string>>(
    () => Object.fromEntries(
      Object.entries(selectedTask?.class_names ?? FALLBACK_CLASS_NAMES[selectedTaskId] ?? {})
        .map(([id, name]) => [Number(id), name]),
    ),
    [selectedTask, selectedTaskId],
  );
  const temporaryClassId = selectedTask?.temporary_class_id ?? null;
  const assignClassIds = useMemo(
    () => Object.keys(classNames)
      .map(Number)
      .filter((classId) => classId !== temporaryClassId)
      .sort((left, right) => left - right),
    [classNames, temporaryClassId],
  );
  const addClassIds = temporaryClassId === null || temporaryClassId === undefined
    ? assignClassIds
    : [temporaryClassId];

  return {
    tasks,
    images,
    selectedImage,
    setSelectedImage,
    refreshImages,
    selectedImageApproved: selectedImageData?.is_approved ?? false,
    classNames,
    assignClassIds,
    addClassIds,
  };
}
