import type { BBox } from '../../../types';

export interface CanvasSize {
  width: number;
  height: number;
}

export interface CanvasPosition {
  x: number;
  y: number;
}

interface CanvasBoxAttributes {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Keeps the image within the canvas while preserving the initial fit position
 * when it is smaller than the available viewport.
 */
export function clampCanvasPosition(
  position: CanvasPosition,
  scale: number,
  initialScale: number,
  containerSize: CanvasSize,
  imageSize: CanvasSize,
): CanvasPosition {
  const imageWidth = imageSize.width * scale;
  const imageHeight = imageSize.height * scale;

  let x = position.x;
  let y = position.y;

  if (imageWidth <= containerSize.width) {
    x = Math.abs(scale - initialScale) < 0.001
      ? (containerSize.width - imageWidth) / 2
      : Math.max(0, Math.min(containerSize.width - imageWidth, position.x));
  } else {
    x = Math.max(containerSize.width - imageWidth, Math.min(0, position.x));
  }

  if (imageHeight <= containerSize.height) {
    y = Math.abs(scale - initialScale) < 0.001
      ? (containerSize.height - imageHeight) / 2
      : Math.max(0, Math.min(containerSize.height - imageHeight, position.y));
  } else {
    y = Math.max(containerSize.height - imageHeight, Math.min(0, position.y));
  }

  return { x, y };
}

/** Converts a canvas rectangle back to the normalized YOLO-style box format. */
export function boxFromCanvasAttributes(
  current: BBox,
  attributes: CanvasBoxAttributes,
  imageSize: CanvasSize,
): BBox {
  const xCenter = (attributes.x + attributes.width / 2) / imageSize.width;
  const yCenter = (attributes.y + attributes.height / 2) / imageSize.height;
  const width = attributes.width / imageSize.width;
  const height = attributes.height / imageSize.height;

  return {
    ...current,
    x_center: Math.max(0, Math.min(1, xCenter)),
    y_center: Math.max(0, Math.min(1, yCenter)),
    w: Math.max(0.001, Math.min(1, width)),
    h: Math.max(0.001, Math.min(1, height)),
  };
}
