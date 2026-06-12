import { Loader2 } from 'lucide-react';
import { Image as KonvaImage, Layer, Rect, Stage, Transformer } from 'react-konva';

import { CLASS_COLORS } from '../constants';
import type { BBox, InteractionMode, SelectionRect } from '../types';

interface AnnotationCanvasProps {
  containerRef: React.RefObject<HTMLDivElement>;
  stageRef: React.RefObject<any>;
  transformerRef: React.RefObject<any>;
  containerSize: { width: number; height: number };
  imageSize: { width: number; height: number };
  loading: boolean;
  imageObj: HTMLImageElement | null;
  labels: BBox[];
  selectedIndices: number[];
  selectionRect: SelectionRect | null;
  drawingClass: number | null;
  interactionMode: InteractionMode;
  overlayVisible: boolean;
  isPanning: boolean;
  isSpacePressed: boolean;
  scale: number;
  position: { x: number; y: number };
  onWheel: (event: any) => void;
  onMouseDown: (event: any) => void;
  onMouseMove: (event: any) => void;
  onMouseUp: () => void;
  onSelectBox: (index: number, additive: boolean) => void;
  onBoxDragEnd: (index: number, event: any) => void;
  onSelectedTransformEnd: (event: any) => void;
}

export function AnnotationCanvas({
  containerRef,
  stageRef,
  transformerRef,
  containerSize,
  imageSize,
  loading,
  imageObj,
  labels,
  selectedIndices,
  selectionRect,
  drawingClass,
  interactionMode,
  overlayVisible,
  isPanning,
  isSpacePressed,
  scale,
  position,
  onWheel,
  onMouseDown,
  onMouseMove,
  onMouseUp,
  onSelectBox,
  onBoxDragEnd,
  onSelectedTransformEnd,
}: AnnotationCanvasProps) {
  return (
    <div ref={containerRef} className="flex-1 overflow-hidden bg-black flex items-center justify-center relative">
      {loading ? (
        <Loader2 className="animate-spin text-blue-500" size={48} />
      ) : imageObj ? (
        <Stage
          ref={stageRef}
          width={containerSize.width}
          height={containerSize.height}
          scaleX={scale}
          scaleY={scale}
          x={position.x}
          y={position.y}
          onWheel={onWheel}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onContextMenu={(event) => event.evt.preventDefault()}
          style={{
            cursor:
              isPanning || isSpacePressed || interactionMode === 'pan'
                ? isPanning
                  ? 'grabbing'
                  : 'grab'
                : drawingClass !== null
                  ? 'crosshair'
                  : 'default',
          }}
        >
          <Layer>
            <KonvaImage image={imageObj} />
            {overlayVisible && labels
              .map((box, index) => ({ box, index }))
              .sort((a, b) => {
                const order: Record<number, number> = { 0: 0, 2: 1, 1: 2 };
                return (order[a.box.class_id] ?? 0) - (order[b.box.class_id] ?? 0);
              })
              .map(({ box, index }) => {
                const width = box.w * imageSize.width;
                const height = box.h * imageSize.height;
                const x = box.x_center * imageSize.width - width / 2;
                const y = box.y_center * imageSize.height - height / 2;

                return (
                  <Rect
                    key={index}
                    name={`box-${index}`}
                    x={x}
                    y={y}
                    width={width}
                    height={height}
                    fill={CLASS_COLORS[box.class_id]}
                    stroke={selectedIndices.includes(index) ? 'white' : 'transparent'}
                    strokeWidth={2}
                    strokeScaleEnabled={false}
                    draggable={drawingClass === null && !isSpacePressed && interactionMode === 'select' && overlayVisible}
                    listening={drawingClass === null && !isSpacePressed && interactionMode === 'select' && overlayVisible}
                    onClick={(event) => {
                      if (drawingClass !== null) return;
                      event.cancelBubble = true;
                      onSelectBox(index, event.evt.shiftKey);
                    }}
                    onDragStart={(event) => {
                      event.cancelBubble = true;
                    }}
                    onDragMove={(event) => {
                      event.cancelBubble = true;
                    }}
                    onDragEnd={(event) => onBoxDragEnd(index, event)}
                    onTransformStart={(event) => {
                      event.cancelBubble = true;
                    }}
                    onTransform={(event) => {
                      event.cancelBubble = true;
                    }}
                    onTransformEnd={(event) => {
                      event.cancelBubble = true;
                    }}
                  />
                );
              })}
            {overlayVisible && selectionRect && (
              <Rect
                x={Math.min(selectionRect.x1, selectionRect.x2)}
                y={Math.min(selectionRect.y1, selectionRect.y2)}
                width={Math.abs(selectionRect.x2 - selectionRect.x1)}
                height={Math.abs(selectionRect.y2 - selectionRect.y1)}
                fill={drawingClass !== null ? CLASS_COLORS[drawingClass] : 'rgba(0, 161, 255, 0.3)'}
                stroke={drawingClass !== null ? 'white' : '#00a1ff'}
                strokeWidth={1}
                strokeScaleEnabled={false}
                listening={false}
              />
            )}
            {overlayVisible && selectedIndices.length > 0 && (
              <Transformer
                ref={transformerRef}
                rotateEnabled={false}
                flipEnabled={false}
                keepRatio={false}
                ignoreStroke
                borderStroke="#00a1ff"
                borderStrokeWidth={1 / scale}
                anchorSize={6 / scale}
                anchorFill="white"
                anchorStroke="#00a1ff"
                anchorStrokeWidth={1 / scale}
                anchorCornerRadius={3 / scale}
                listening={!isSpacePressed && interactionMode === 'select'}
                onDragStart={(event) => {
                  event.cancelBubble = true;
                }}
                onDragMove={(event) => {
                  event.cancelBubble = true;
                }}
                onDragEnd={(event) => {
                  event.cancelBubble = true;
                }}
                onTransformStart={(event) => {
                  event.cancelBubble = true;
                }}
                onTransform={(event) => {
                  event.cancelBubble = true;
                }}
                onTransformEnd={onSelectedTransformEnd}
                boundBoxFunc={(oldBox, newBox) => {
                  if (newBox.width < 2 || newBox.height < 2) return oldBox;
                  return newBox;
                }}
              />
            )}
          </Layer>
        </Stage>
      ) : (
        <div className="text-gray-500">Select an image to start</div>
      )}
    </div>
  );
}
