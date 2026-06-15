import axios from 'axios';

import type { BBox, ImageData, TaskInfo } from '../types';

const api = axios.create({
  baseURL: '/api/v1',
});

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

export async function exportImage(taskId: string, filename: string): Promise<void> {
  const response = await api.get<Blob>(`/tasks/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}/export`, {
    responseType: 'blob',
  });
  downloadBlob(response.data, filename.replace(/\.[^.]+$/, '_dataset.zip'));
}

export async function exportAll(taskId: string): Promise<void> {
  const response = await api.get<Blob>(`/tasks/${encodeURIComponent(taskId)}/export`, {
    responseType: 'blob',
  });
  downloadBlob(response.data, `${taskId}_dataset.zip`);
}

export function imageUrl(taskId: string, filename: string): string {
  return `/media/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}`;
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
