import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Loader2, Upload } from 'lucide-react';

import { AnnotationCanvas } from '../components/AnnotationCanvas';
import { FilmstripPanel } from '../components/FilmstripPanel';
import { PropertiesPanel } from '../components/PropertiesPanel';
import { TopNavBar } from '../components/TopNavBar';
import { imageUrl } from '../api/client';
import { DEFAULT_TASK_ID } from '../constants';
import { useAnnotationEditor } from '../features/annotation/hooks/useAnnotationEditor';
import { useWorkspaceActions } from '../features/annotation/hooks/useWorkspaceActions';
import { useWorkspaceData } from '../features/annotation/hooks/useWorkspaceData';
import { boxFromCanvasAttributes, clampCanvasPosition } from '../features/annotation/utils/canvasGeometry';
import type { InteractionMode, SelectionRect } from '../types';

/** Composes task data, label editing, dataset actions, and the Konva canvas. */
export const Workspace = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const selectedTaskId = taskId || DEFAULT_TASK_ID;
  const {
    tasks,
    images,
    selectedImage,
    setSelectedImage,
    refreshImages,
    selectedImageApproved,
    classNames,
    assignClassIds,
    addClassIds,
  } = useWorkspaceData({ selectedTaskId });
  const {
    labels,
    setLabels,
    loading,
    isSaving,
    setIsDirty,
    selectedIndices,
    setSelectedIndices,
    drawingClass,
    setDrawingClass,
    loadLabels,
    flushPendingLabels,
    clearForNoImage,
    clearAfterRename,
    prepareForLoadedImage,
    pushToHistory,
    undo,
    toggleAddMode,
    deleteSelected,
    changeSelectedClass,
  } = useAnnotationEditor({ selectedTaskId, selectedImage, refreshImages });

  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });
  const [imageObj, setImageObj] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);
  const [initialScale, setInitialScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [isSpacePressed, setIsSpacePressed] = useState(false);
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('select');
  const [selectionRect, setSelectionRect] = useState<SelectionRect | null>(null);
  const [overlayVisible, setOverlayVisible] = useState(true);

  const isSpacePressedRef = useRef(false);
  const stageRef = useRef<any>(null);
  const transformerRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const clearWorkspaceAfterRename = useCallback(() => {
    setSelectedImage(null);
    clearAfterRename();
    setImageObj(null);
  }, [clearAfterRename, setSelectedImage]);

  const clearWorkspaceAfterDelete = useCallback(() => {
    setSelectedImage(null);
    clearForNoImage();
    setImageObj(null);
  }, [clearForNoImage, setSelectedImage]);

  const {
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
  } = useWorkspaceActions({
    selectedTaskId,
    selectedImage,
    images,
    setSelectedImage,
    refreshImages,
    flushPendingLabels,
    loadLabels,
    clearAfterRename: clearWorkspaceAfterRename,
    clearAfterDelete: clearWorkspaceAfterDelete,
  });

  const updateContainerSize = useCallback(() => {
    if (!containerRef.current) return;
    setContainerSize({
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });
  }, []);

  useEffect(() => {
    updateContainerSize();
    window.addEventListener('resize', updateContainerSize);
    return () => window.removeEventListener('resize', updateContainerSize);
  }, [updateContainerSize]);

  useEffect(() => {
    if (selectedIndices.length > 0 && transformerRef.current) {
      const nodes = selectedIndices
        .map((index) => stageRef.current?.findOne(`.box-${index}`))
        .filter(Boolean);
      const transformer = transformerRef.current;
      transformer.nodes(nodes);

      const hitSize = 20 / scale;
      [
        'top-left',
        'top-center',
        'top-right',
        'middle-right',
        'bottom-right',
        'bottom-center',
        'bottom-left',
        'middle-left',
      ].forEach((name) => {
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
  }, [labels, scale, selectedIndices]);

  useEffect(() => {
    if (!selectedImage) {
      clearForNoImage();
      setImageObj(null);
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
      prepareForLoadedImage();
    };
  }, [
    clearForNoImage,
    containerSize.height,
    containerSize.width,
    loadLabels,
    prepareForLoadedImage,
    selectedImage,
    selectedTaskId,
  ]);

  const clampPosition = useCallback((x: number, y: number, currentScale: number) => (
    clampCanvasPosition({ x, y }, currentScale, initialScale, containerSize, imageSize)
  ), [containerSize, imageSize, initialScale]);

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
        deleteSelected();
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
        void goToNext();
      } else if (event.key.toLowerCase() === 'a') {
        if (document.activeElement?.tagName === 'INPUT') return;
        void goToPrev();
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
  }, [clampPosition, deleteSelected, goToNext, goToPrev, scale, undo]);

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
    const newScale = Math.max(
      initialScale,
      Math.min(15, event.evt.deltaY > 0 ? oldScale / speed : oldScale * speed),
    );
    const newPosition = clampPosition(
      pointer.x - mousePointTo.x * newScale,
      pointer.y - mousePointTo.y * newScale,
      newScale,
    );

    setScale(newScale);
    setPosition(newPosition);
  };

  const handleMouseDown = (event: any) => {
    if (
      event.evt.button === 2
      || event.evt.button === 1
      || (event.evt.button === 0 && (isSpacePressedRef.current || interactionMode === 'pan'))
    ) {
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
      setPosition((current) => (
        clampPosition(current.x + event.evt.movementX, current.y + event.evt.movementY, scale)
      ));
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
    nextLabels[index] = boxFromCanvasAttributes(nextLabels[index], newAttrs, imageSize);
    pushToHistory(nextLabels);
  };

  const handleMultiBoxChange = (changes: { index: number; newAttrs: any }[]) => {
    const nextLabels = [...labels];
    changes.forEach(({ index, newAttrs }) => {
      nextLabels[index] = boxFromCanvasAttributes(nextLabels[index], newAttrs, imageSize);
    });
    pushToHistory(nextLabels);
  };

  const handleSelectBox = (index: number, additive: boolean) => {
    if (additive) {
      setSelectedIndices((current) => (
        current.includes(index)
          ? current.filter((selectedIndex) => selectedIndex !== index)
          : [...current, index]
      ));
    } else {
      setSelectedIndices([index]);
    }
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
    <div className={`flex flex-col h-screen bg-background text-on-background select-none ${drawingClass !== null ? 'cursor-crosshair' : ''}`}>
      <TopNavBar
        tasks={tasks}
        selectedTaskId={selectedTaskId}
        interactionMode={interactionMode}
        overlayVisible={overlayVisible}
        isSaving={isSaving}
        processingAction={processingAction}
        selectedImage={selectedImage}
        images={images}
        leftSidebarOpen={leftSidebarOpen}
        rightSidebarOpen={rightSidebarOpen}
        onOverlayVisibleChange={setOverlayVisible}
        onInteractionModeChange={setInteractionMode}
        onUndo={undo}
        onPrevious={goToPrev}
        onNext={goToNext}
        onProcess={handleProcess}
        onExportAll={handleExportAll}
        onToggleLeftSidebar={() => setLeftSidebarOpen(!leftSidebarOpen)}
        onToggleRightSidebar={() => setRightSidebarOpen(!rightSidebarOpen)}
      />

      <main className="flex-1 flex overflow-hidden">
        {leftSidebarOpen && (
          <FilmstripPanel
            images={images}
            selectedImage={selectedImage}
            processingAction={processingAction}
            onUploadImages={handleUploadImages}
            onRenameSequential={handleRenameSequential}
            onSelectImage={handleSelectImage}
            onDeleteImage={handleDeleteImage}
          />
        )}

        {images.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center bg-surface-container-lowest">
            <div className="max-w-md w-full p-8 border-2 border-dashed border-outline-variant rounded-2xl bg-surface flex flex-col items-center text-center">
              <Upload className="w-16 h-16 text-on-surface-variant/50 mb-4" />
              <h2 className="text-headline-sm font-headline-sm text-on-surface mb-2">No Images Found</h2>
              <p className="text-body-md text-on-surface-variant mb-6">
                Get started by uploading images for this task. You can upload multiple files at once.
              </p>

              <label className={`bg-primary-container text-on-primary-container font-label-lg font-bold px-6 py-3 rounded-xl hover:bg-primary-fixed transition-colors cursor-pointer active:scale-95 duration-100 flex items-center gap-2 ${processingAction === 'upload' ? 'opacity-50 pointer-events-none' : ''}`}>
                {processingAction === 'upload' ? <Loader2 className="animate-spin" size={20} /> : <Upload size={20} />}
                {processingAction === 'upload' ? 'Uploading...' : 'Select Images'}
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                  multiple
                  className="hidden"
                  onChange={(event) => {
                    const files = Array.from(event.target.files ?? []);
                    if (files.length > 0) void handleUploadImages(files);
                    event.target.value = '';
                  }}
                  disabled={processingAction !== null}
                />
              </label>
            </div>
          </div>
        ) : (
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
        )}

        {rightSidebarOpen && (
          <PropertiesPanel
            classNames={classNames}
            addClassIds={addClassIds}
            assignClassIds={assignClassIds}
            labels={labels}
            selectedIndices={selectedIndices}
            drawingClass={drawingClass}
            selectedImage={selectedImage}
            isApproved={selectedImageApproved}
            processingAction={processingAction}
            onToggleAddMode={toggleAddMode}
            onDelete={deleteSelected}
            onSelectedClassChange={changeSelectedClass}
            onReset={handleReset}
            onAutoLabelCurrent={handleAutoLabelCurrent}
            onApprovalChange={handleApprovalChange}
          />
        )}
      </main>
    </div>
  );
};
