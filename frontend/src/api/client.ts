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

export function imageUrl(taskId: string, filename: string): string {
  return `/media/${encodeURIComponent(taskId)}/images/${encodeURIComponent(filename)}`;
}
