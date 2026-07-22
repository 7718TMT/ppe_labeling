import axios from 'axios';

import type { BBox, ImageData, TaskInfo } from '../types';
import type {
  AnnotationDerivativeRefresh, BehaviorInferenceResults, BehaviorInferenceWorkspace, ExternalModel, FeatureWindow, GeneratedWindow, PoseTrackFrame, ProcessingJob,
  ProcessingOptions,
  SuggestionSource, ThresholdProfile, VideoItem, VideoProject, VideoSegment,
  VideoExportRecord, VideoTrack, VideoWorkspaceChanges, VideoWorkspaceSnapshot, VideoWorkspaceState,
  HumanVideoLabel,
} from '../types';

export type { VideoExportRecord } from '../types';

const api = axios.create({
  baseURL: '/api/v1',
});

// Surface human-readable backend error messages instead of generic HTTP status text.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail;
    if (detail && typeof detail === 'string') {
      return Promise.reject(new Error(detail));
    }
    return Promise.reject(error);
  },
);

export async function getTasks(): Promise<TaskInfo[]> {
  const response = await api.get<TaskInfo[]>('/tasks');
  return response.data;
}

export async function getImages(taskId: string): Promise<ImageData[]> {
  const response = await api.get<ImageData[]>(`/tasks/${encodeURIComponent(taskId)}/images`);
  return response.data;
}

export async function getLabels(taskId: string, filename: string): Promise<BBox[]> {
  const response = await api.get<{ filename: string; boxes: BBox[] }>(`/tasks/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}/labels`);
  return response.data.boxes;
}

export async function uploadImages(taskId: string, files: File[]): Promise<void> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  await api.post(`/tasks/${encodeURIComponent(taskId)}/images/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

export async function saveLabels(taskId: string, filename: string, boxes: BBox[]): Promise<void> {
  await api.put(`/tasks/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}/labels`, { boxes });
}

export async function setApproval(taskId: string, filename: string, isApproved: boolean): Promise<void> {
  await api.put(`/tasks/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}/approve`, { is_approved: isApproved });
}

export async function autoLabelAll(taskId: string): Promise<void> {
  await api.post(`/tasks/${encodeURIComponent(taskId)}/auto-label`);
}

export async function autoLabelImage(taskId: string, filename: string): Promise<void> {
  await api.post(`/tasks/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}/auto-label`);
}

export async function generateVisualizations(taskId: string): Promise<void> {
  await api.post(`/tasks/${encodeURIComponent(taskId)}/visualizations`);
}

export async function deleteImage(taskId: string, filename: string): Promise<void> {
  await api.delete(`/tasks/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}`);
}

export async function renameSequential(taskId: string): Promise<void> {
  await api.post(`/tasks/${encodeURIComponent(taskId)}/rename-sequential`);
}

export function exportImage(taskId: string, filename: string): void {
  const url = `/api/v1/tasks/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}/export`;
  triggerBrowserDownload(url, filename.replace(/\.[^.]+$/, '_dataset.zip'));
}

export function exportAll(taskId: string): void {
  const url = `/api/v1/tasks/${encodeURIComponent(taskId)}/export`;
  triggerBrowserDownload(url, `${taskId}_dataset.zip`);
}

export function imageUrl(taskId: string, filename: string): string {
  return `/media/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}`;
}

function triggerBrowserDownload(url: string, filename: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export async function getVideoProjects(): Promise<VideoProject[]> {
  return (await api.get<VideoProject[]>('/video-projects')).data;
}

export async function getBehaviorInferenceWorkspace(): Promise<BehaviorInferenceWorkspace> {
  return (await api.get<BehaviorInferenceWorkspace>('/behavior-inference')).data;
}

export async function importBehaviorInferenceVideos(files: File[]): Promise<VideoItem[]> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  return (await api.post<VideoItem[]>('/behavior-inference/videos', formData)).data;
}

export async function getBehaviorInferenceResults(videoId: string): Promise<BehaviorInferenceResults> {
  return (await api.get<BehaviorInferenceResults>(`/behavior-inference/videos/${encodeURIComponent(videoId)}/results`)).data;
}

export async function createVideoProject(name: string): Promise<VideoProject> {
  return (await api.post<VideoProject>('/video-projects', { name })).data;
}

export async function getVideoProject(projectId: string): Promise<VideoProject> {
  return (await api.get<VideoProject>(`/video-projects/${projectId}`)).data;
}

export async function getVideos(projectId: string, status?: string): Promise<VideoItem[]> {
  return (await api.get<VideoItem[]>(`/video-projects/${projectId}/videos`, { params: { status } })).data;
}

export async function importVideos(projectId: string, files: File[], mode: 'Threshold' | 'Model' = 'Threshold'): Promise<VideoItem[]> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  // mode param triggers auto-pipeline queue on the backend
  return (await api.post<VideoItem[]>(
    `/video-projects/${projectId}/videos/import`,
    formData,
    { params: { mode: mode.toLowerCase() } },
  )).data;
}

export function videoMediaUrl(projectId: string, videoId: string): string {
  return `/api/v1/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/media`;
}

export function videoThumbnailUrl(projectId: string, videoId: string): string {
  return `/api/v1/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/thumbnail`;
}

export async function deleteVideo(projectId: string, videoId: string): Promise<void> {
  await api.delete(`/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}`);
}

export async function renameVideos(projectId: string, prefix: string): Promise<VideoItem[]> {
  return (await api.post(`/video-projects/${encodeURIComponent(projectId)}/videos/rename`, { prefix })).data;
}

export async function trimVideo(
  projectId: string,
  videoId: string,
  startFrame: number,
  endFrame: number,
  saveMode: 'replace' | 'copy',
  filename?: string,
  suggestionMode: 'threshold' | 'model' = 'threshold',
): Promise<{
  video: VideoItem;
  save_mode: 'replace' | 'copy';
  processing_action?: 'keypoints_copied' | 'suggestions_queued';
  jobs?: ProcessingJob[];
}> {
  return (await api.post(
    `/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/trim`,
    {
      start_frame: startFrame, end_frame: endFrame, save_mode: saveMode,
      suggestion_mode: suggestionMode, ...(filename ? { filename } : {}),
    },
  )).data;
}

export async function processVideo(
  projectId: string,
  videoId: string,
  mode: 'Threshold' | 'Model',
  overwriteLabels = false,
): Promise<ProcessingJob[]> {
  return (await api.post<ProcessingJob[]>(
    `/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/process`,
    { mode: mode.toLowerCase(), priority: 1000, ...(overwriteLabels ? { overwrite_labels: true } : {}) },
  )).data;
}

/** Rebuild label-derived windows/features without generating new suggestions. */
export async function refreshAnnotationDerivatives(
  projectId: string,
  videoId: string,
): Promise<AnnotationDerivativeRefresh> {
  return (await api.post<AnnotationDerivativeRefresh>(
    `/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/annotation-derivatives/refresh`,
  )).data;
}

export async function getProcessingOptions(projectId: string): Promise<ProcessingOptions> {
  return (await api.get<ProcessingOptions>(
    `/video-projects/${encodeURIComponent(projectId)}/processing-options`,
  )).data;
}

export async function getVideoJobs(projectId: string): Promise<ProcessingJob[]> {
  return (await api.get<ProcessingJob[]>(`/video-projects/${projectId}/jobs`)).data;
}

/**
 * Load the compact, internally consistent state required to initialize an
 * event-driven video workspace. Detailed active-video resources remain lazy.
 */
export async function getVideoWorkspaceSnapshot(
  projectId: string,
  signal?: AbortSignal,
): Promise<VideoWorkspaceSnapshot> {
  return (await api.get<VideoWorkspaceSnapshot>(
    `/video-projects/${encodeURIComponent(projectId)}/workspace-snapshot`,
    { signal },
  )).data;
}

/**
 * Fetch only durable changes after a known workspace event cursor.
 *
 * This is the recovery path for a reconnect or a browser tab that becomes
 * visible again; it intentionally does not re-fetch the full video list.
 */
export async function getVideoWorkspaceChanges(
  projectId: string,
  after: number,
  signal?: AbortSignal,
): Promise<VideoWorkspaceChanges> {
  return (await api.get<VideoWorkspaceChanges>(
    `/video-projects/${encodeURIComponent(projectId)}/workspace-changes`,
    { params: { after }, signal },
  )).data;
}

/** Return the same-origin SSE URL used to receive project-scoped updates. */
export function videoWorkspaceEventsUrl(projectId: string, after?: number): string {
  const query = after === undefined ? '' : `?after=${encodeURIComponent(after)}`;
  return `/api/v1/video-projects/${encodeURIComponent(projectId)}/events${query}`;
}

export async function controlVideoJob(projectId: string, jobId: string, action: string): Promise<ProcessingJob> {
  return (await api.post<ProcessingJob>(`/video-projects/${projectId}/jobs/${jobId}/control`, { action })).data;
}

export async function getVideoTracks(
  projectId: string,
  videoId: string,
  signal?: AbortSignal,
): Promise<VideoTrack[]> {
  return (await api.get<VideoTrack[]>(
    `/video-projects/${projectId}/videos/${videoId}/tracks`,
    { signal },
  )).data;
}

export async function getVideoSegments(
  projectId: string,
  videoId: string,
  signal?: AbortSignal,
): Promise<{ revision: number; segments: VideoSegment[] }> {
  return (await api.get(
    `/video-projects/${projectId}/videos/${videoId}/segments`,
    { signal },
  )).data;
}

export async function saveVideoSegment(
  projectId: string, videoId: string, payload: { track_id: number; start_frame: number; end_frame: number; label: HumanVideoLabel; expected_revision: number }, segmentId?: string,
): Promise<{ segment: VideoSegment; revision: number }> {
  const url = `/video-projects/${projectId}/videos/${videoId}/segments${segmentId ? `/${segmentId}` : ''}`;
  return (await (segmentId ? api.put(url, payload) : api.post(url, payload))).data;
}

export async function deleteVideoSegment(projectId: string, videoId: string, segmentId: string, revision: number): Promise<{ revision: number }> {
  return (await api.delete(`/video-projects/${projectId}/videos/${videoId}/segments/${segmentId}`, { data: { expected_revision: revision } })).data;
}

export async function videoHistoryAction(projectId: string, videoId: string, action: 'undo' | 'redo', revision: number): Promise<{ revision: number }> {
  return (await api.post(`/video-projects/${projectId}/videos/${videoId}/history/${action}`, { expected_revision: revision })).data;
}

export async function getPoseOverlay(projectId: string, videoId: string, start: number, end: number): Promise<PoseTrackFrame[]> {
  return (await api.get<PoseTrackFrame[]>(`/video-projects/${projectId}/videos/${videoId}/overlay`, { params: { start, end } })).data;
}

export async function getWindows(projectId: string, videoId: string): Promise<GeneratedWindow[]> {
  return (await api.get<GeneratedWindow[]>(`/video-projects/${projectId}/videos/${videoId}/windows`)).data;
}

export async function getFeatures(projectId: string, videoId: string, trackId?: number): Promise<FeatureWindow[]> {
  return (await api.get<FeatureWindow[]>(`/video-projects/${projectId}/videos/${videoId}/features`, { params: { track_id: trackId } })).data;
}

export async function approveVideo(projectId: string, videoId: string): Promise<VideoItem> {
  return (await api.post<VideoItem>(`/video-projects/${projectId}/videos/${videoId}/approve`)).data;
}

export async function getThresholdProfiles(projectId: string): Promise<ThresholdProfile[]> {
  return (await api.get<ThresholdProfile[]>(`/video-projects/${projectId}/threshold-profiles`)).data;
}

export async function saveThresholdProfile(projectId: string, profile: ThresholdProfile): Promise<ThresholdProfile> {
  return (await api.post<ThresholdProfile>(`/video-projects/${projectId}/threshold-profiles`, { profile_id: profile.threshold_profile_id, name: profile.name, config: profile.config })).data;
}

export async function cloneThresholdProfile(projectId: string, profile: ThresholdProfile): Promise<ThresholdProfile> {
  return (await api.post<ThresholdProfile>(`/video-projects/${projectId}/threshold-profiles`, { name: `${profile.name} Copy`, config: profile.config })).data;
}

export async function restoreDefaultThresholdProfile(projectId: string): Promise<ThresholdProfile> {
  return (await api.post<ThresholdProfile>(`/video-projects/${projectId}/threshold-profiles/restore-default`)).data;
}

export async function getExternalModels(projectId: string): Promise<ExternalModel[]> {
  return (await api.get<ExternalModel[]>(`/video-projects/${projectId}/models`)).data;
}

export async function saveVideoWorkspaceState(projectId: string, state: VideoWorkspaceState): Promise<VideoWorkspaceState> {
  return (await api.put<VideoWorkspaceState>(`/video-projects/${projectId}/workspace-state`, state)).data;
}

/**
 * Best-effort final recovery checkpoint for page shutdown.
 *
 * ``sendBeacon`` cannot be used because the API deliberately requires PUT.
 * A small same-origin keepalive fetch preserves that contract while giving a
 * closing browser page a chance to persist its latest resume position.
 */
export function flushVideoWorkspaceStateOnExit(
  projectId: string,
  state: VideoWorkspaceState,
): void {
  void fetch(`/api/v1/video-projects/${encodeURIComponent(projectId)}/workspace-state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
    keepalive: true,
  }).catch(() => undefined);
}

export async function validateVideoExport(projectId: string): Promise<{ errors: string[]; warnings: string[] }> {
  return (await api.get(`/video-projects/${projectId}/exports/validate`)).data;
}

export async function createVideoExport(projectId: string): Promise<any> {
  return (await api.post(`/video-projects/${projectId}/exports`)).data;
}

export async function getVideoExports(projectId: string): Promise<VideoExportRecord[]> {
  return (await api.get<VideoExportRecord[]>(`/video-projects/${projectId}/exports`)).data;
}

export function downloadVideoExport(projectId: string, exportId: string): void {
  triggerBrowserDownload(
    `/api/v1/video-projects/${encodeURIComponent(projectId)}/exports/${encodeURIComponent(exportId)}/download`,
    `pose-export-${exportId}.zip`,
  );
}

export async function mergeVideoTracks(projectId: string, videoId: string, target: number, source: number): Promise<VideoTrack> {
  return (await api.post(`/video-projects/${projectId}/videos/${videoId}/tracks/${target}/merge`, { source_track_id: source })).data;
}

export async function splitVideoTrack(projectId: string, videoId: string, trackId: number, frame: number): Promise<VideoTrack[]> {
  return (await api.post(`/video-projects/${projectId}/videos/${videoId}/tracks/${trackId}/split`, { frame })).data;
}

export async function setVideoTrackInclusion(projectId: string, videoId: string, trackId: number, include: boolean, reason?: string): Promise<VideoTrack> {
  const response = await api.put<VideoTrack>(`/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/tracks/${trackId}/inclusion`, {
    include,
    reason: reason || null,
  });
  return response.data;
}

export async function deleteVideoTrack(projectId: string, videoId: string, trackId: number): Promise<void> {
  await api.delete(`/video-projects/${encodeURIComponent(projectId)}/videos/${encodeURIComponent(videoId)}/tracks/${trackId}`);
}

export async function reviewWindow(projectId: string, videoId: string, windowId: string, include: boolean, reason?: string): Promise<GeneratedWindow> {
  return (await api.put(`/video-projects/${projectId}/videos/${videoId}/windows/${windowId}`, { include, reason })).data;
}

export async function importExternalModel(projectId: string, artifact: File, manifest: File, trusted: boolean): Promise<ExternalModel> {
  const form = new FormData();
  form.append('artifact', artifact);
  form.append('manifest_json', await manifest.text());
  form.append('trusted_local', String(trusted));
  return (await api.post<ExternalModel>(`/video-projects/${projectId}/models/import`, form)).data;
}

export async function runExternalModel(projectId: string, videoId: string, modelId: string): Promise<ProcessingJob> {
  return (await api.post<ProcessingJob>(`/video-projects/${projectId}/videos/${videoId}/models/${modelId}/infer`)).data;
}

export async function unloadExternalModel(projectId: string, modelId: string): Promise<ExternalModel> {
  return (await api.post<ExternalModel>(`/video-projects/${projectId}/models/${modelId}/unload`)).data;
}

export async function splitVideoSegment(projectId: string, videoId: string, segmentId: string, frame: number, revision: number): Promise<VideoSegment[]> {
  return (await api.post<VideoSegment[]>(`/video-projects/${projectId}/videos/${videoId}/segments/${segmentId}/split`, { frame, expected_revision: revision })).data;
}

export async function mergeVideoSegments(projectId: string, videoId: string, segmentIds: string[], revision: number): Promise<{segment: VideoSegment; revision: number}> {
  return (await api.post(`/video-projects/${projectId}/videos/${videoId}/segments/merge`, { segment_ids: segmentIds, expected_revision: revision })).data;
}

export async function extendVideoSegment(projectId: string, videoId: string, segmentId: string, revision: number): Promise<{segment: VideoSegment; revision: number}> {
  return (await api.post(`/video-projects/${projectId}/videos/${videoId}/segments/${segmentId}/extend`, { expected_revision: revision })).data;
}

export async function labelFullVideoTrack(projectId: string, videoId: string, trackId: number, label: HumanVideoLabel, revision: number): Promise<{segment: VideoSegment; revision: number}> {
  return (await api.post(`/video-projects/${projectId}/videos/${videoId}/tracks/${trackId}/label/${label}`, { expected_revision: revision })).data;
}

export async function setVideoSegmentInclusion(projectId: string, videoId: string, segmentId: string, include: boolean, revision: number, reason?: string): Promise<{segment: VideoSegment; revision: number}> {
  return (await api.put(`/video-projects/${projectId}/videos/${videoId}/segments/${segmentId}/inclusion`, { include, reason, expected_revision: revision })).data;
}

/** Merge multiple tracks (by track_id list) into the first track in the list. */
export async function mergeMultipleVideoTracks(projectId: string, videoId: string, trackIds: number[]): Promise<VideoTrack> {
  return (await api.post(`/video-projects/${projectId}/videos/${videoId}/tracks/merge-multiple`, { track_ids: trackIds })).data;
}

/** Revoke approval on a video so it can be re-annotated. */
export async function unapproveVideo(projectId: string, videoId: string): Promise<VideoItem> {
  return (await api.post<VideoItem>(`/video-projects/${projectId}/videos/${videoId}/unapprove`)).data;
}
