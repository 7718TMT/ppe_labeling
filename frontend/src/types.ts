export interface BBox {
  class_id: number;
  x_center: number;
  y_center: number;
  w: number;
  h: number;
}

export interface ImageData {
  name: string;
  has_label: boolean;
  image_url: string;
  visualization_url?: string | null;
}

export type InteractionMode = 'pan' | 'select';

export interface SelectionRect {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}
