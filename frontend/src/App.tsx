import { useEffect, useRef, useState } from 'react';

import {
  autoLabelAll,
  autoLabelImage,
  deleteImage,
  exportAll,
  exportImage,
  generateVisualizations,
  getImages,
  getLabels,
  getTasks,
  imageUrl,
  renameSequential,
  saveLabels,
  uploadImages,
} from './api/client';
import { AnnotationCanvas } from './components/AnnotationCanvas';
import { ImageSidebar } from './components/ImageSidebar';
import { Toolbar } from './components/Toolbar';
import { DEFAULT_TASK_ID, FALLBACK_CLASS_NAMES } from './constants';
import type { BBox, ImageData, InteractionMode, SelectionRect, TaskInfo } from './types';

const App = () => {
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState(DEFAULT_TASK_ID);
  const [images, setImages] = useState<ImageData[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [labels, setLabels] = useState<BBox[]>([]);
  const [history, setHistory] = useState<BBox[][]>([]);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [imageObj, setImageObj] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);
  const [initialScale, setInitialScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [isSpacePressed, setIsSpacePressed] = useState(false);
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('select');
  const [selectionRect, setSelectionRect] = useState<SelectionRect | null>(null);
  const [drawingClass, setDrawingClass] = useState<number | null>(null);
  const [overlayVisible, setOverlayVisible] = useState(true);
  const [isDirty, setIsDirty] = useState(false);

  const isSpacePressedRef = useRef(false);
  const stageRef = useRef<any>(null);
  const transformerRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const selectedTask = tasks.find((task) => task.id === selectedTaskId);
  const classNames: Record<number, string> = Object.fromEntries(
    Object.entries(selectedTask?.class_names ?? FALLBACK_CLASS_NAMES[selectedTaskId] ?? {}).map(([id, name]) => [Number(id), name]),
  );
  const temporaryClassId = selectedTask?.temporary_class_id ?? null;
  const assignClassIds = Object.keys(classNames)
    .map(Number)
    .filter((classId) => classId !== temporaryClassId)
    .sort((a, b) => a - b);
  const addClassIds = selectedTaskId === 'safety_signs'
    ? assignClassIds.slice(0, 1)
    : temporaryClassId !== null && temporaryClassId !== undefined
      ? [temporaryClassId]
      : assignClassIds;
  const selectedClassIds = [...new Set(selectedIndices.map((index) => labels[index]?.class_id).filter((classId) => classId !== undefined))];
  const selectedClassId = selectedClassIds.length === 1 ? selectedClassIds[0] : null;
  const selectedAssignableClassId = selectedClassId !== null && assignClassIds.includes(selectedClassId) ? selectedClassId : null;

  useEffect(() => {
    void refreshTasks();
    updateContainerSize();
    window.addEventListener('resize', updateContainerSize);
    return () => window.removeEventListener('resize', updateContainerSize);
  }, []);

  useEffect(() => {
    void refreshImages(selectedTaskId);
    setSelectedImage(null);
    setLabels([]);
    setHistory([]);
    setSelectedIndices([]);
    setDrawingClass(null);
    setIsDirty(false);
  }, [selectedTaskId]);

  useEffect(() => {
    if (!selectedImage || !isDirty) return;
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    saveTimeoutRef.current = setTimeout(() => {
      void autoSaveLabels();
    }, 1000);

    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [labels, isDirty, selectedImage, selectedTaskId]);

  useEffect(() => {
    if (selectedIndices.length > 0 && transformerRef.current) {
      const nodes = selectedIndices.map((index) => stageRef.current?.findOne(`.box-${index}`)).filter(Boolean);
      const transformer = transformerRef.current;
      transformer.nodes(nodes);

      const hitSize = 20 / scale;
      ['top-left', 'top-center', 'top-right', 'middle-right', 'bottom-right', 'bottom-center', 'bottom-left', 'middle-left'].forEach((name) => {
        const anchor = transformer.findOne(`.${name}`);
        if (anchor) {
          anchor.hitFunc((context: any, shape: any) => {
            const transformerNode = shape.getParent();
            const width = transformerNode.width();
            const height = transformerNode.height();

            context.beginPath();
            if (name === 'top-center' || name === 'bottom-center') {
              context.rect(-width / 2, -hitSize / 2, width, hitSize);
            } else if (name === 'middle-left' || name === 'middle-right') {
              context.rect(-hitSize / 2, -height / 2, hitSize, height);
            } else {
              context.rect(-hitSize / 2, -hitSize / 2, hitSize, hitSize);
            }
            context.fillShape(shape);
          });
        }
      });

      transformer.getLayer().batchDraw();
    } else if (transformerRef.current) {
      transformerRef.current.nodes([]);
    }
  }, [selectedIndices, labels, scale]);

  useEffect(() => {
    if (!selectedImage) {
      setLabels([]);
      setImageObj(null);
      setIsDirty(false);
      return;
    }

    void loadLabels(selectedImage);
    const image = new Image();
    image.src = imageUrl(selectedTaskId, selectedImage);
    image.onload = () => {
      setImageObj(image);
      setImageSize({ width: image.width, height: image.height });

      const padding = 40;
      const availableWidth = containerSize.width - padding;
      const availableHeight = containerSize.height - padding;
      const fitScale = Math.min(availableWidth / image.width, availableHeight / image.height, 1);

      setScale(fitScale);
      setInitialScale(fitScale);
      setPosition({
        x: (containerSize.width - image.width * fitScale) / 2,
        y: (containerSize.height - image.height * fitScale) / 2,
      });
      setHistory([]);
      setSelectedIndices([]);
      setDrawingClass(null);
    };
  }, [selectedImage, selectedTaskId, containerSize.width, containerSize.height]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === ' ') {
        if (document.activeElement?.tagName === 'INPUT') return;
        event.preventDefault();
        if (!event.repeat) {
          isSpacePressedRef.current = true;
          setIsSpacePressed(true);
        }
        return;
      }

      if (event.ctrlKey && event.key === 'z') {
        event.preventDefault();
        undo();
      } else if (event.key === 'Delete' || event.key === 'Backspace') {
        if (document.activeElement?.tagName === 'INPUT') return;
        handleDelete();
      } else if (event.key === 'Escape') {
        setDrawingClass(null);
        setSelectionRect(null);
      } else if (event.key === 'ArrowRight') {
        setPosition((current) => clampPosition(current.x - 50, current.y, scale));
      } else if (event.key === 'ArrowLeft') {
        setPosition((current) => clampPosition(current.x + 50, current.y, scale));
      } else if (event.key === 'ArrowUp') {
        setPosition((current) => clampPosition(current.x, current.y + 50, scale));
      } else if (event.key === 'ArrowDown') {
        setPosition((current) => clampPosition(current.x, current.y - 50, scale));
      } else if (event.key.toLowerCase() === 'd') {
        if (document.activeElement?.tagName === 'INPUT') return;
        goToNext();
      } else if (event.key.toLowerCase() === 'a') {
        if (document.activeElement?.tagName === 'INPUT') return;
        goToPrev();
      } else if (event.key.toLowerCase() === 'h') {
        if (document.activeElement?.tagName === 'INPUT') return;
        setInteractionMode('pan');
      } else if (event.key.toLowerCase() === 'v') {
        if (document.activeElement?.tagName === 'INPUT') return;
        setInteractionMode('select');
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key === ' ') {
        isSpacePressedRef.current = false;
        setIsSpacePressed(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [selectedIndices, labels, history, isSpacePressed, scale]);

  const clampPosition = (x: number, y: number, currentScale: number) => {
    const stageWidth = containerSize.width;
    const stageHeight = containerSize.height;
    const imageWidth = imageSize.width * currentScale;
    const imageHeight = imageSize.height * currentScale;

    let nextX = x;
    let nextY = y;

    if (imageWidth <= stageWidth) {
      nextX = Math.abs(currentScale - initialScale) < 0.001 ? (stageWidth - imageWidth) / 2 : Math.max(0, Math.min(stageWidth - imageWidth, x));
    } else {
      nextX = Math.max(stageWidth - imageWidth, Math.min(0, x));
    }

    if (imageHeight <= stageHeight) {
      nextY = Math.abs(currentScale - initialScale) < 0.001 ? (stageHeight - imageHeight) / 2 : Math.max(0, Math.min(stageHeight - imageHeight, y));
    } else {
      nextY = Math.max(stageHeight - imageHeight, Math.min(0, y));
    }

    return { x: nextX, y: nextY };
  };

  const updateContainerSize = () => {
    if (!containerRef.current) return;
    setContainerSize({
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });
  };

  const refreshTasks = async () => {
    try {
      const taskList = await getTasks();
      setTasks(taskList);
      if (!taskList.some((task) => task.id === selectedTaskId)) {
        setSelectedTaskId(taskList.find((task) => task.id === DEFAULT_TASK_ID)?.id ?? taskList[0]?.id ?? DEFAULT_TASK_ID);
      }
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const refreshImages = async (taskId = selectedTaskId) => {
    try {
      const imageList = await getImages(taskId);
      setImages(imageList);
      setSelectedImage((current) => (current && imageList.some((image) => image.name === current) ? current : imageList[0]?.name ?? null));
    } catch (error) {
      console.error('Error fetching images:', error);
    }
  };

  const loadLabels = async (filename: string) => {
    setLoading(true);
    try {
      setLabels(await getLabels(selectedTaskId, filename));
      setHistory([]);
      setIsDirty(false);
    } catch (error) {
      console.error('Error fetching labels:', error);
    } finally {
      setLoading(false);
    }
  };

  const persistLabels = async (nextLabels = labels, options: { refresh?: boolean } = {}) => {
    if (!selectedImage) return;
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }
    setIsSaving(true);
    try {
      await saveLabels(selectedTaskId, selectedImage, nextLabels);
      setIsDirty(false);
      if (options.refresh ?? true) {
        await refreshImages(selectedTaskId);
      }
    } catch (error) {
      console.error('Error saving labels:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const flushPendingLabels = async () => {
    if (!selectedImage || !isDirty) return;
    await persistLabels(labels, { refresh: false });
  };

  const autoSaveLabels = async () => {
    await persistLabels(labels);
  };

  const handleProcess = async () => {
    setProcessing(true);
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
      setProcessing(false);
    }
  };

  const handleUploadImages = async (files: File[]) => {
    setProcessing(true);
    try {
      await flushPendingLabels();
      await uploadImages(selectedTaskId, files);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Check console for details.');
    } finally {
      setProcessing(false);
    }
  };

  const handleAutoLabelCurrent = async () => {
    if (!selectedImage) return;
    setProcessing(true);
    try {
      await autoLabelImage(selectedTaskId, selectedImage);
      await loadLabels(selectedImage);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Auto-label failed:', error);
      alert('Auto-label failed. Check console for details.');
    } finally {
      setProcessing(false);
    }
  };

  const handleExportCurrent = async () => {
    if (!selectedImage) return;
    setProcessing(true);
    try {
      await flushPendingLabels();
      await exportImage(selectedTaskId, selectedImage);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Check console for details.');
    } finally {
      setProcessing(false);
    }
  };

  const handleExportAll = async () => {
    setProcessing(true);
    try {
      await flushPendingLabels();
      await exportAll(selectedTaskId);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Check console for details.');
    } finally {
      setProcessing(false);
    }
  };

  const handleRenameSequential = async () => {
    if (!confirm('Rename all images and matching labels in this task to image_00000, image_00001, and so on?')) return;
    setProcessing(true);
    try {
      await flushPendingLabels();
      await renameSequential(selectedTaskId);
      setSelectedImage(null);
      setLabels([]);
      setImageObj(null);
      setHistory([]);
      setSelectedIndices([]);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Rename failed:', error);
      alert('Rename failed. Check console for details.');
    } finally {
      setProcessing(false);
    }
  };

  const handleVisualize = async () => {
    setProcessing(true);
    try {
      await flushPendingLabels();
      await generateVisualizations(selectedTaskId);
      await refreshImages(selectedTaskId);
      alert('Visualization completed! Check data/labeled_images.');
    } catch (error) {
      console.error('Visualization failed:', error);
      alert('Visualization failed.');
    } finally {
      setProcessing(false);
    }
  };

  const handleReset = async () => {
    if (!selectedImage) return;
    if (!confirm('Are you sure? This will remove manual changes for this image and re-run AI detection.')) return;

    setIsResetting(true);
    try {
      await autoLabelImage(selectedTaskId, selectedImage);
      await loadLabels(selectedImage);
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Reset failed:', error);
      alert('Reset failed. Check console.');
    } finally {
      setIsResetting(false);
    }
  };

  const handleDeleteImage = async (event: React.MouseEvent, filename: string) => {
    event.stopPropagation();
    if (!confirm(`Are you sure you want to delete ${filename}? This cannot be undone.`)) return;

    try {
      await deleteImage(selectedTaskId, filename);
      if (selectedImage === filename) {
        setSelectedImage(null);
        setLabels([]);
        setImageObj(null);
        setIsDirty(false);
      }
      await refreshImages(selectedTaskId);
    } catch (error) {
      console.error('Error deleting image:', error);
      alert('Failed to delete image.');
    }
  };

  const pushToHistory = (newLabels: BBox[]) => {
    setHistory((current) => [...current, labels]);
    setLabels(newLabels);
    setIsDirty(true);
  };

  const undo = () => {
    if (history.length === 0) return;
    const previous = history[history.length - 1];
    setHistory((current) => current.slice(0, -1));
    setLabels(previous);
    setSelectedIndices([]);
    setIsDirty(true);
  };

  const toggleAddMode = (classId: number) => {
    setDrawingClass((current) => (current === classId ? null : classId));
    setSelectedIndices([]);
  };

  const handleSelectImage = async (filename: string) => {
    await flushPendingLabels();
    setSelectedImage(filename);
  };

  const goToNext = async () => {
    if (!selectedImage || images.length === 0) return;
    const currentIndex = images.findIndex((image) => image.name === selectedImage);
    if (currentIndex < images.length - 1) {
      await flushPendingLabels();
      setSelectedImage(images[currentIndex + 1].name);
    }
  };

  const goToPrev = async () => {
    if (!selectedImage || images.length === 0) return;
    const currentIndex = images.findIndex((image) => image.name === selectedImage);
    if (currentIndex > 0) {
      await flushPendingLabels();
      setSelectedImage(images[currentIndex - 1].name);
    }
  };

  const handleWheel = (event: any) => {
    event.evt.preventDefault();
    const stage = stageRef.current;
    if (!stage) return;

    const oldScale = stage.scaleX();
    const pointer = stage.getPointerPosition();
    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    };

    const speed = 1.1;
    const newScale = Math.max(initialScale, Math.min(15, event.evt.deltaY > 0 ? oldScale / speed : oldScale * speed));
    const newPosition = clampPosition(pointer.x - mousePointTo.x * newScale, pointer.y - mousePointTo.y * newScale, newScale);

    setScale(newScale);
    setPosition(newPosition);
  };

  const handleMouseDown = (event: any) => {
    if (event.evt.button === 2 || event.evt.button === 1 || (event.evt.button === 0 && (isSpacePressedRef.current || interactionMode === 'pan'))) {
      event.evt.preventDefault();
      setIsPanning(true);
      return;
    }
    if (!overlayVisible) return;

    const isStage = event.target === event.target.getStage();
    const isImage = event.target.className === 'Image';
    if (!isStage && !isImage) return;

    const pointer = stageRef.current.getPointerPosition();
    const stageScale = stageRef.current.scaleX();
    const stageX = stageRef.current.x();
    const stageY = stageRef.current.y();

    const x = Math.max(0, Math.min(imageSize.width, (pointer.x - stageX) / stageScale));
    const y = Math.max(0, Math.min(imageSize.height, (pointer.y - stageY) / stageScale));

    setSelectionRect({ x1: x, y1: y, x2: x, y2: y });
    if (drawingClass === null) {
      setSelectedIndices([]);
    }
  };

  const handleMouseMove = (event: any) => {
    if (isPanning) {
      setPosition((current) => clampPosition(current.x + event.evt.movementX, current.y + event.evt.movementY, scale));
      return;
    }
    if (!selectionRect) return;

    const pointer = stageRef.current.getPointerPosition();
    const stageScale = stageRef.current.scaleX();
    const stageX = stageRef.current.x();
    const stageY = stageRef.current.y();

    const x = Math.max(0, Math.min(imageSize.width, (pointer.x - stageX) / stageScale));
    const y = Math.max(0, Math.min(imageSize.height, (pointer.y - stageY) / stageScale));

    setSelectionRect({ ...selectionRect, x2: x, y2: y });
  };

  const handleMouseUp = () => {
    if (isPanning) {
      setIsPanning(false);
      return;
    }
    if (!selectionRect) return;

    const x1 = Math.min(selectionRect.x1, selectionRect.x2);
    const y1 = Math.min(selectionRect.y1, selectionRect.y2);
    const x2 = Math.max(selectionRect.x1, selectionRect.x2);
    const y2 = Math.max(selectionRect.y1, selectionRect.y2);

    if (drawingClass !== null) {
      const width = x2 - x1;
      const height = y2 - y1;
      if (width > 2 && height > 2) {
        pushToHistory([
          ...labels,
          {
            class_id: drawingClass,
            x_center: (x1 + width / 2) / imageSize.width,
            y_center: (y1 + height / 2) / imageSize.height,
            w: width / imageSize.width,
            h: height / imageSize.height,
          },
        ]);
        setDrawingClass(null);
      }
      setSelectionRect(null);
      return;
    }

    const nextSelectedIndices: number[] = [];
    labels.forEach((box, index) => {
      const width = box.w * imageSize.width;
      const height = box.h * imageSize.height;
      const boxX = box.x_center * imageSize.width - width / 2;
      const boxY = box.y_center * imageSize.height - height / 2;

      if (boxX >= x1 && boxY >= y1 && boxX + width <= x2 && boxY + height <= y2) {
        nextSelectedIndices.push(index);
      }
    });

    setSelectedIndices(nextSelectedIndices);
    setSelectionRect(null);
  };

  const handleBoxChange = (index: number, newAttrs: any) => {
    const nextLabels = [...labels];
    nextLabels[index] = boxFromAttrs(nextLabels[index], newAttrs);
    pushToHistory(nextLabels);
  };

  const handleMultiBoxChange = (changes: { index: number; newAttrs: any }[]) => {
    const nextLabels = [...labels];
    changes.forEach(({ index, newAttrs }) => {
      nextLabels[index] = boxFromAttrs(nextLabels[index], newAttrs);
    });
    pushToHistory(nextLabels);
  };

  const boxFromAttrs = (current: BBox, newAttrs: any): BBox => {
    const xCenter = (newAttrs.x + newAttrs.width / 2) / imageSize.width;
    const yCenter = (newAttrs.y + newAttrs.height / 2) / imageSize.height;
    const width = newAttrs.width / imageSize.width;
    const height = newAttrs.height / imageSize.height;

    return {
      ...current,
      x_center: Math.max(0, Math.min(1, xCenter)),
      y_center: Math.max(0, Math.min(1, yCenter)),
      w: Math.max(0.001, Math.min(1, width)),
      h: Math.max(0.001, Math.min(1, height)),
    };
  };

  const handleDelete = () => {
    if (selectedIndices.length === 0) return;
    pushToHistory(labels.filter((_, index) => !selectedIndices.includes(index)));
    setSelectedIndices([]);
  };

  const handleSelectBox = (index: number, additive: boolean) => {
    if (additive) {
      setSelectedIndices((current) => (current.includes(index) ? current.filter((selectedIndex) => selectedIndex !== index) : [...current, index]));
    } else {
      setSelectedIndices([index]);
    }
  };

  const handleSelectedClassChange = (classId: number) => {
    if (selectedIndices.length === 0) return;
    const nextLabels = labels.map((box, index) => (selectedIndices.includes(index) ? { ...box, class_id: classId } : box));
    pushToHistory(nextLabels);
    void persistLabels(nextLabels);
  };

  const handleBoxDragEnd = (index: number, event: any) => {
    event.cancelBubble = true;
    if (selectedIndices.length > 1 && selectedIndices.includes(index)) {
      const changes = selectedIndices.map((selectedIndex) => {
        const node = stageRef.current.findOne(`.box-${selectedIndex}`);
        return {
          index: selectedIndex,
          newAttrs: {
            x: node.x(),
            y: node.y(),
            width: node.width() * node.scaleX(),
            height: node.height() * node.scaleY(),
          },
        };
      });
      handleMultiBoxChange(changes);
    } else {
      handleBoxChange(index, {
        x: event.target.x(),
        y: event.target.y(),
        width: event.target.width() * event.target.scaleX(),
        height: event.target.height() * event.target.scaleY(),
      });
    }
    event.target.scaleX(1);
    event.target.scaleY(1);
  };

  const handleBoxTransformEnd = (index: number, event: any) => {
    event.cancelBubble = true;
    if (selectedIndices.length > 1) {
      const changes = selectedIndices.map((selectedIndex) => {
        const node = stageRef.current.findOne(`.box-${selectedIndex}`);
        const change = {
          index: selectedIndex,
          newAttrs: {
            x: node.x(),
            y: node.y(),
            width: node.width() * node.scaleX(),
            height: node.height() * node.scaleY(),
          },
        };
        node.scaleX(1);
        node.scaleY(1);
        return change;
      });
      handleMultiBoxChange(changes);
    } else {
      const node = event.target;
      handleBoxChange(index, {
        x: node.x(),
        y: node.y(),
        width: node.width() * node.scaleX(),
        height: node.height() * node.scaleY(),
      });
      node.scaleX(1);
      node.scaleY(1);
    }
  };

  return (
    <div className={`flex h-screen bg-gray-900 text-white ${drawingClass !== null ? 'cursor-crosshair' : ''}`}>
      <ImageSidebar
        images={images}
        selectedImage={selectedImage}
        processing={processing}
        onUploadImages={handleUploadImages}
        onAutoLabelCurrent={handleAutoLabelCurrent}
        onProcess={handleProcess}
        onVisualize={handleVisualize}
        onExportCurrent={handleExportCurrent}
        onExportAll={handleExportAll}
        onRenameSequential={handleRenameSequential}
        onSelectImage={handleSelectImage}
        onDeleteImage={handleDeleteImage}
      />

      <div className="flex-1 flex flex-col">
        <Toolbar
          tasks={tasks}
          selectedTaskId={selectedTaskId}
          classNames={classNames}
          addClassIds={addClassIds}
          assignClassIds={assignClassIds}
          drawingClass={drawingClass}
          interactionMode={interactionMode}
          selectedCount={selectedIndices.length}
          selectedClassId={selectedAssignableClassId}
          overlayVisible={overlayVisible}
          isResetting={isResetting}
          isSaving={isSaving}
          selectedImage={selectedImage}
          onTaskChange={setSelectedTaskId}
          onToggleAddMode={toggleAddMode}
          onSelectedClassChange={handleSelectedClassChange}
          onOverlayVisibleChange={setOverlayVisible}
          onInteractionModeChange={setInteractionMode}
          onDeleteSelected={handleDelete}
          onReset={handleReset}
          onPrevious={goToPrev}
          onNext={goToNext}
        />

        <AnnotationCanvas
          containerRef={containerRef}
          stageRef={stageRef}
          transformerRef={transformerRef}
          containerSize={containerSize}
          imageSize={imageSize}
          loading={loading}
          imageObj={imageObj}
          labels={labels}
          selectedIndices={selectedIndices}
          selectionRect={selectionRect}
          drawingClass={drawingClass}
          interactionMode={interactionMode}
          overlayVisible={overlayVisible}
          isPanning={isPanning}
          isSpacePressed={isSpacePressed}
          scale={scale}
          position={position}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onSelectBox={handleSelectBox}
          onBoxDragEnd={handleBoxDragEnd}
          onBoxTransformEnd={handleBoxTransformEnd}
        />
      </div>
    </div>
  );
};

export default App;
