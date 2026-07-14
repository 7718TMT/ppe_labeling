import { useMemo, useRef, useState } from 'react';
import { Film, Loader2, Trash2, Upload } from 'lucide-react';

import { videoThumbnailUrl } from '../../api/client';
import type { ProcessingJob, VideoItem } from '../../types';
import { userAnnotationStatus, userVideoStatus } from './videoPresentation';

interface Props {
  videos: VideoItem[];
  jobs?: ProcessingJob[];
  selectedId?: string;
  deletingId?: string;
  onSelect: (video: VideoItem) => void;
  onImport: (files: File[]) => void;
  onDelete?: (video: VideoItem) => void;
}

const ROW_HEIGHT = 106;
const FILTERS = ['All', 'Unprocessed', 'Processing', 'Ready', 'Failed', 'Unlabeled', 'In progress', 'Completed'];

function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  return `${minutes}:${String(safe % 60).padStart(2, '0')}`;
}

/** Virtualized, thumbnail-backed video browser following the image filmstrip. */
export function VideoBrowser({
  videos,
  jobs = [],
  selectedId,
  deletingId,
  onSelect,
  onImport,
  onDelete,
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  const scrollViewport = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState('All');
  const [scrollTop, setScrollTop] = useState(0);
  const [failedThumbnails, setFailedThumbnails] = useState<Set<string>>(new Set());
  const filtered = useMemo(() => {
    if (filter === 'All') return videos;
    return videos.filter((video) =>
      userVideoStatus(video, jobs) === filter || userAnnotationStatus(video) === filter,
    );
  }, [filter, jobs, videos]);
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 2);
  const visible = filtered.slice(start, start + 12);

  return (
    <section
      className="flex flex-col min-h-0 flex-1"
      aria-label="Video browser"
      onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; }}
      onDrop={(event) => {
        event.preventDefault();
        onImport(Array.from(event.dataTransfer.files).filter((file) => file.type.startsWith('video/')));
      }}
    >
      <div className="p-3 border-b border-outline-variant space-y-2">
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="w-full h-8 bg-primary-container text-on-primary-container rounded font-label text-label-sm font-bold flex items-center justify-center gap-2"
        >
          <Upload size={15} />Import videos
        </button>
        <input
          ref={input}
          className="hidden"
          type="file"
          multiple
          accept="video/*"
          onChange={(event) => {
            onImport(Array.from(event.target.files ?? []));
            event.target.value = '';
          }}
        />
        <select
          aria-label="Filter videos"
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value);
            setScrollTop(0);
            if (scrollViewport.current) scrollViewport.current.scrollTop = 0;
          }}
          className="w-full h-8 bg-surface-container-lowest border border-outline-variant rounded px-2 text-label-sm"
        >
          {FILTERS.map((value) => <option key={value}>{value}</option>)}
        </select>
      </div>
      <div
        ref={scrollViewport}
        className="overflow-y-auto relative flex-1"
        onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
        style={{ minHeight: 240 }}
      >
        <div style={{ height: filtered.length * ROW_HEIGHT, position: 'relative' }}>
          {visible.map((video, offset) => {
            const selected = selectedId === video.video_id;
            const processing = userVideoStatus(video, jobs);
            const annotation = userAnnotationStatus(video);
            const deleting = deletingId === video.video_id;
            return (
              <div
                key={video.video_id}
                role="button"
                tabIndex={0}
                aria-label={`Open ${video.filename}`}
                aria-current={selected ? 'true' : undefined}
                onClick={() => !deleting && onSelect(video)}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) return;
                  if (!deleting && ['Enter', ' '].includes(event.key)) {
                    event.preventDefault();
                    onSelect(video);
                  }
                }}
                className={`group absolute left-2 right-2 h-[98px] rounded border p-2 cursor-pointer transition-colors ${
                  selected
                    ? 'border-primary bg-primary/10 ring-1 ring-primary/50'
                    : 'border-outline-variant bg-surface-container-lowest hover:border-on-surface-variant hover:bg-surface-container-high'
                } ${video.is_approved ? 'border-l-4 border-l-emerald-500' : ''} ${deleting ? 'opacity-50 pointer-events-none' : ''}`}
                style={{ top: (start + offset) * ROW_HEIGHT + 4 }}
              >
                <div className="flex gap-2 h-full">
                  <div className="w-[92px] h-full bg-black rounded-sm overflow-hidden shrink-0 flex items-center justify-center">
                    {failedThumbnails.has(video.video_id) ? (
                      <Film size={24} className="text-on-surface-variant" aria-label="Thumbnail unavailable" />
                    ) : (
                      <img
                        src={videoThumbnailUrl(video.project_id, video.video_id)}
                        alt=""
                        loading="lazy"
                        className="w-full h-full object-cover"
                        onError={() => setFailedThumbnails((current) => new Set(current).add(video.video_id))}
                      />
                    )}
                  </div>
                  <div className="min-w-0 flex-1 flex flex-col">
                    <div className="flex items-start gap-1">
                      <span className="truncate text-body-md font-medium flex-1" title={video.filename}>{video.filename}</span>
                      {onDelete && (
                        <button
                          type="button"
                          title={`Delete ${video.filename}`}
                          aria-label={`Delete ${video.filename}`}
                          disabled={deleting}
                          onClick={(event) => {
                            event.stopPropagation();
                            onDelete(video);
                          }}
                          onKeyDown={(event) => event.stopPropagation()}
                          className="w-7 h-7 -mt-1 -mr-1 rounded flex items-center justify-center text-error hover:bg-error/10 disabled:opacity-40"
                        >
                          {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                        </button>
                      )}
                    </div>
                    <p className="font-label text-[10px] text-on-surface-variant mt-0.5">
                      {formatDuration(video.duration_seconds)} · {video.canonical_frame_count} frames
                    </p>
                    <div className="mt-auto flex flex-wrap gap-1">
                      <span className={`status-pill ${processing === 'Failed' ? 'text-error border-error/40' : processing === 'Ready' ? 'text-primary border-primary/40' : ''}`}>{processing}</span>
                      <span className="status-pill">{annotation}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        {filtered.length === 0 && <div className="p-6 text-center text-on-surface-variant text-body-md">No videos match this filter.</div>}
      </div>
    </section>
  );
}
