import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ProcessingJob, VideoItem } from '../../types';
import { VideoBrowser } from './VideoBrowser';

const video = (id: string, status = 'annotation_ready'): VideoItem => ({
  video_id: id, project_id: 'p1', filename: `${id}.mp4`, original_fps: 24,
  canonical_fps: 24, original_frame_count: 120, canonical_frame_count: 120,
  duration_seconds: 5, width: 640, height: 480, processing_status: status,
  annotation_status: 'unlabeled', quality_status: 'good', annotation_revision: 0,
  is_approved: 0, include_in_export: 1, updated_at: '2026-01-01',
});

describe('VideoBrowser', () => {
  afterEach(cleanup);

  it('shows bordered thumbnails and simple statuses, filters, selects, and imports', () => {
    const select = vi.fn();
    const upload = vi.fn();
    const jobs: ProcessingJob[] = [{
      job_id: 'j1', video_id: 'one', stage: 'pose_track', status: 'running',
      priority: 100, progress: 0.4,
    }];
    const { container } = render(
      <VideoBrowser videos={[video('one'), video('two', 'failed')]} jobs={jobs} onSelect={select} onImport={upload} />,
    );
    expect(container.querySelector('img')).toHaveAttribute('src', expect.stringContaining('/thumbnail'));
    expect(screen.getByLabelText('Open one.mp4')).toHaveClass('border-outline-variant');
    expect(within(screen.getByLabelText('Open one.mp4')).getByText('Processing')).toBeInTheDocument();
    fireEvent.click(screen.getByText('one.mp4'));
    expect(select).toHaveBeenCalledWith(expect.objectContaining({ video_id: 'one' }));
    fireEvent.change(screen.getByLabelText('Filter system processing status'), { target: { value: 'Failed' } });
    expect(screen.queryByText('one.mp4')).not.toBeInTheDocument();
    expect(screen.getByText('two.mp4')).toBeInTheDocument();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['video'], 'new.mp4', { type: 'video/mp4' });
    fireEvent.change(input, { target: { files: [file] } });
    expect(upload).toHaveBeenCalledWith([file]);
  });

  it('keeps delete separate from selection and exposes thumbnail fallback', () => {
    const select = vi.fn();
    const remove = vi.fn();
    const { container } = render(<VideoBrowser videos={[video('one')]} onSelect={select} onImport={vi.fn()} onDelete={remove} />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete one.mp4' }));
    expect(remove).toHaveBeenCalledWith(expect.objectContaining({ video_id: 'one' }));
    expect(select).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole('button', { name: 'Delete one.mp4' }), { key: 'Enter' });
    expect(select).not.toHaveBeenCalled();
    fireEvent.error(container.querySelector('img') as HTMLImageElement);
    expect(screen.getByLabelText('Thumbnail unavailable')).toBeInTheDocument();
  });

  it('resets virtualization scroll when a filter shortens the result', () => {
    const videos = Array.from({ length: 30 }, (_, index) => video(
      `video-${index}`,
      index === 0 ? 'failed' : 'annotation_ready',
    ));
    const { container } = render(
      <VideoBrowser videos={videos} onSelect={vi.fn()} onImport={vi.fn()} />,
    );
    const viewport = container.querySelector('.overflow-y-auto') as HTMLDivElement;
    Object.defineProperty(viewport, 'scrollTop', { configurable: true, writable: true, value: 2200 });
    fireEvent.scroll(viewport);
    fireEvent.change(screen.getByLabelText('Filter system processing status'), { target: { value: 'Failed' } });
    expect(viewport.scrollTop).toBe(0);
    expect(screen.getByText('video-0.mp4')).toBeInTheDocument();
  });

  it('combines system processing and user-labeling filters', () => {
    const labeled = { ...video('review', 'annotation_ready'), annotation_status: 'labeled' };
    render(
      <VideoBrowser videos={[video('unlabeled'), labeled, video('failed', 'failed')]} onSelect={vi.fn()} onImport={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText('Filter user labelling status'), { target: { value: 'Labeled' } });
    expect(screen.getByText('review.mp4')).toBeInTheDocument();
    expect(screen.queryByText('unlabeled.mp4')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Filter system processing status'), { target: { value: 'Ready' } });
    expect(screen.getByText('review.mp4')).toBeInTheDocument();
    expect(screen.queryByText('failed.mp4')).not.toBeInTheDocument();
  });

  it('filters video cards by a case-insensitive name search', () => {
    render(<VideoBrowser videos={[video('Fall-Worker'), video('running-shift')]} onSelect={vi.fn()} onImport={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Search videos by name'), { target: { value: 'FALL' } });
    expect(screen.getByText('Fall-Worker.mp4')).toBeInTheDocument();
    expect(screen.queryByText('running-shift.mp4')).not.toBeInTheDocument();
  });

  it('sorts filtered videos locally by the selected field and direction', () => {
    const alpha = { ...video('alpha'), duration_seconds: 20, updated_at: '2026-01-02T00:00:00Z' };
    const zeta = { ...video('zeta'), duration_seconds: 5, updated_at: '2026-01-03T00:00:00Z' };
    render(<VideoBrowser videos={[zeta, alpha]} onSelect={vi.fn()} onImport={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('Order videos by'), { target: { value: 'filename' } });
    expect(screen.getAllByRole('button', { name: /^Open / }).map((item) => item.getAttribute('aria-label')))
      .toEqual(['Open zeta.mp4', 'Open alpha.mp4']);
    fireEvent.click(screen.getByRole('button', { name: 'Sort descending' }));
    expect(screen.getAllByRole('button', { name: /^Open / }).map((item) => item.getAttribute('aria-label')))
      .toEqual(['Open alpha.mp4', 'Open zeta.mp4']);

    fireEvent.change(screen.getByLabelText('Order videos by'), { target: { value: 'duration' } });
    expect(screen.getAllByRole('button', { name: /^Open / }).map((item) => item.getAttribute('aria-label')))
      .toEqual(['Open zeta.mp4', 'Open alpha.mp4']);
  });
});
