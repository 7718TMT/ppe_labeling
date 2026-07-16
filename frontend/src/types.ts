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
  is_approved: boolean;
  image_url: string;
  visualization_url?: string | null;
}

export interface TaskInfo {
  id: string;
  name: string;
  class_names: Record<string, string>;
  temporary_class_id?: number | null;
}

export type InteractionMode = 'pan' | 'select';

export interface SelectionRect {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export type HumanVideoLabel = 'others' | 'running' | 'falling';
export type SuggestionSource = 'Off' | 'Threshold' | 'AI';

export interface VideoProject {
  project_id: string;
  name: string;
  config: Record<string, any>;
  active_threshold_profile_id?: string | null;
  workspace_state?: VideoWorkspaceState | null;
  created_at: string;
  updated_at: string;
}

export interface VideoItem {
  video_id: string;
  project_id: string;
  filename: string;
  original_fps: number;
  canonical_fps: number;
  original_frame_count: number;
  canonical_frame_count: number;
  duration_seconds: number;
  width: number;
  height: number;
  processing_status: string;
  annotation_status: string;
  quality_status: string;
  annotation_revision: number;
  is_approved: number;
  include_in_export: number;
  exclude_reason?: string | null;
  last_error?: string | null;
  updated_at: string;
}

export interface ProcessingJob {
  job_id: string;
  project_id?: string;
  video_id?: string | null;
  stage: string;
  status: string;
  priority: number;
  progress: number;
  target_mode?: 'threshold' | 'model';
  external_model_id?: string | null;
  error_message?: string | null;
}

export interface ProcessingOptions {
  threshold_available: boolean;
  model_available: boolean;
  model_message?: string | null;
}

/** Result of refreshing windows/features after a manual annotation edit. */
export interface AnnotationDerivativeRefresh {
  requested_revision: number;
  status: 'queued' | 'deferred' | 'already_queued';
  job?: ProcessingJob | null;
}

/** Compact export state shared by the workspace event stream and export panel. */
export interface VideoExportRecord {
  export_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  created_at: string;
  finished_at?: string | null;
  job_id?: string | null;
}

/**
 * Compact initial state used by the event-driven video workspace synchronizer.
 *
 * The payload deliberately contains card-level data only. Tracks, segments,
 * pose overlays, and feature rows remain lazy-loaded for the active video.
 */
export interface VideoWorkspaceSnapshot {
  project: VideoProject;
  videos: VideoItem[];
  jobs: ProcessingJob[];
  processing_options: ProcessingOptions;
  exports?: VideoExportRecord[];
  last_event_id: number;
}

/**
 * A durable, project-scoped workspace change emitted by the backend outbox.
 *
 * Event payloads are intentionally opaque here: consumers choose the small
 * subset they need, rather than coupling every screen to every event type.
 */
export interface VideoWorkspaceEvent {
  event_id: number;
  project_id: string;
  video_id?: string | null;
  event_type: string;
  payload: unknown;
  created_at?: string;
}

/** A catch-up response used after a reconnect or restored browser tab. */
export interface VideoWorkspaceChanges {
  events: VideoWorkspaceEvent[];
  last_event_id: number;
  resync_required?: boolean;
  has_more?: boolean;
}

export interface VideoTrack {
  track_id: number;
  start_frame: number;
  end_frame: number;
  avg_keypoint_confidence: number;
  valid_frame_ratio: number;
  missing_ankle_ratio: number;
  quality_status: string;
  include_in_export: number;
  exclude_reason?: string | null;
}

export interface VideoSegment {
  segment_id: string;
  track_id: number;
  start_frame: number;
  end_frame: number;
  label: HumanVideoLabel;
  quality_status: string;
  include_in_export: number;
  source_type: string;
  source_id?: string | null;
}

export interface GeneratedWindow {
  window_id: string;
  track_id: number;
  start_frame: number;
  end_frame: number;
  label?: HumanVideoLabel | null;
  quality_status: string;
  quality_score: number;
  include_in_export: number;
  exclude_reason?: string | null;
}

export interface PoseTrackFrame {
  frame_index: number;
  tracks: Array<{
    track_id: number;
    bbox: [number, number, number, number];
    keypoints: Array<[number, number]>;
    keypoint_scores: number[];
    person_confidence: number;
  }>;
}

export interface FeatureWindow {
  window_id: string;
  track_id: number;
  start_frame: number;
  end_frame: number;
  raw: Record<string, number>;
  transformed: Record<string, number>;
  provenance: Record<string, 'observed' | 'interpolated' | 'missing'>;
  quality: { status: string; valid_frame_ratio: number };
}

export interface ExternalModel {
  external_model_id: string;
  name: string;
  version: string;
  adapter_type: string;
  compatibility_status: string;
  compatibility_errors: string[];
  is_active: number;
}

export interface ThresholdProfile {
  threshold_profile_id: string;
  name: string;
  version: string;
  config: Record<string, any>;
  is_default: number;
}

export interface VideoWorkspaceState {
  video_id?: string | null;
  track_id?: number | null;
  frame_index: number;
  suggestion_source: SuggestionSource;
}
