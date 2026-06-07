import axios from 'axios';

import type { BBox, ImageData } from '../types';

const api = axios.create({
  baseURL: '/api/v1',
});

export async function getImages(): Promise<ImageData[]> {
  const response = await api.get<ImageData[]>('/images');
  return response.data;
}

export async function getLabels(filename: string): Promise<BBox[]> {
  const response = await api.get<{ filename: string; boxes: BBox[] }>(`/images/${encodeURIComponent(filename)}/labels`);
  return response.data.boxes;
}

export async function saveLabels(filename: string, boxes: BBox[]): Promise<void> {
  await api.put(`/images/${encodeURIComponent(filename)}/labels`, { boxes });
}

export async function autoLabelAll(): Promise<void> {
  await api.post('/auto-label');
}

export async function autoLabelImage(filename: string): Promise<void> {
  await api.post(`/images/${encodeURIComponent(filename)}/auto-label`);
}

export async function generateVisualizations(): Promise<void> {
  await api.post('/visualizations');
}

export async function deleteImage(filename: string): Promise<void> {
  await api.delete(`/images/${encodeURIComponent(filename)}`);
}

export function imageUrl(filename: string): string {
  return `/media/images/${encodeURIComponent(filename)}`;
}
