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

export interface TaskInfo {
  id: string;
  name: string;
  class_names: Record<string, string>;
  temporary_class_id?: number | null;
}

export interface RenamePreviewItem {
  original_name: string;
  suggested_name: string;
  reason: string;
  class_ids: number[];
  label_count: number;
  will_rename: boolean;
}

export interface RenamePreviewResponse {
  items: RenamePreviewItem[];
  rename_count: number;
}

export type InteractionMode = 'pan' | 'select';

export interface SelectionRect {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}
