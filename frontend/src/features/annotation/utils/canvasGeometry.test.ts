import { describe, expect, it } from 'vitest';

import { boxFromCanvasAttributes, clampCanvasPosition } from './canvasGeometry';

describe('canvasGeometry', () => {
  it('keeps a fitted image centered when it is smaller than the canvas', () => {
    expect(clampCanvasPosition(
      { x: 20, y: 20 },
      1,
      1,
      { width: 800, height: 600 },
      { width: 400, height: 300 },
    )).toEqual({ x: 200, y: 150 });
  });

  it('normalizes and clamps a transformed box to the image bounds', () => {
    expect(boxFromCanvasAttributes(
      { class_id: 3, x_center: 0.5, y_center: 0.5, w: 0.2, h: 0.2 },
      { x: -20, y: 190, width: 10, height: 20 },
      { width: 100, height: 100 },
    )).toEqual({
      class_id: 3,
      x_center: 0,
      y_center: 1,
      w: 0.1,
      h: 0.2,
    });
  });
});
