import { useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, Download, Film, ListFilter, Loader2, MoreHorizontal, Pencil, Search, Trash2, Upload, X } from 'lucide-react';

import { videoThumbnailUrl } from '../../api/client';
import type { ProcessingJob, VideoItem } from '../../types';
import { userAnnotationStatus, userVideoStatus } from './videoPresentation';

interface Props {
  videos: VideoItem[];
  jobs?: ProcessingJob[];
  selectedId?: string;
  selectedIds?: Set<string>;
  deletingIds?: Set<string>;
  onSelect: (video: VideoItem) => void;
  onToggleSelection?: (video: VideoItem) => void;
  onImport: (files: File[]) => void;
  onExport?: () => void;
  onRename?: (prefix: string) => Promise<void>;
  onDelete?: (video: VideoItem) => void;
  onDeleteSelected?: () => void;
}

const ROW_HEIGHT = 106;
const PROCESSING_FILTERS = ['All', 'Unprocessed', 'Processing', 'Ready', 'Failed'];
const ANNOTATION_FILTERS = ['All', 'Unlabeled', 'Labeled', 'Approved'];
const ORDER_OPTIONS = [
  ['updated', 'Recently updated'],
  ['filename', 'Video name'],
  ['duration', 'Duration'],
  ['frames', 'Frame count'],
  ['processing', 'System processing'],
  ['annotation', 'User labelling'],
] as const;

type OrderField = typeof ORDER_OPTIONS[number][0];
type OrderDirection = 'asc' | 'desc';

const PROCESSING_ORDER = ['Unprocessed', 'Processing', 'Ready', 'Failed'];
const ANNOTATION_ORDER = ['Unlabeled', 'Labeled', 'Approved'];

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
  selectedIds = new Set(),
  deletingIds = new Set(),
  onSelect,
  onToggleSelection,
  onImport,
  onExport,
  onRename,
  onDelete,
  onDeleteSelected,
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  const scrollViewport = useRef<HTMLDivElement>(null);
  const [processingFilter, setProcessingFilter] = useState('All');
  const [annotationFilter, setAnnotationFilter] = useState('All');
  const [videoQuery, setVideoQuery] = useState('');
  const [orderField, setOrderField] = useState<OrderField>('updated');
  const [orderDirection, setOrderDirection] = useState<OrderDirection>('desc');
  const [scrollTop, setScrollTop] = useState(0);
  const [failedThumbnails, setFailedThumbnails] = useState<Set<string>>(new Set());
  const [renameOpen, setRenameOpen] = useState(false);
  const [renamePrefix, setRenamePrefix] = useState('video');
  const [renaming, setRenaming] = useState(false);
  const [renameError, setRenameError] = useState('');
  const [filterOpen, setFilterOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  function resetScroll() {
    setScrollTop(0);
    if (scrollViewport.current) scrollViewport.current.scrollTop = 0;
  }

  const filtered = useMemo(() => {
    const normalizedQuery = videoQuery.trim().toLocaleLowerCase();
    const matching = videos.filter((video) =>
      (!normalizedQuery || video.filename.toLocaleLowerCase().includes(normalizedQuery))
      && (processingFilter === 'All' || userVideoStatus(video, jobs) === processingFilter)
      && (annotationFilter === 'All' || userAnnotationStatus(video) === annotationFilter),
    );
    const multiplier = orderDirection === 'asc' ? 1 : -1;
    return [...matching].sort((left, right) => {
      let comparison: number;
      if (orderField === 'filename') {
        comparison = left.filename.localeCompare(right.filename, undefined, { numeric: true });
      } else if (orderField === 'duration') {
        comparison = left.duration_seconds - right.duration_seconds;
      } else if (orderField === 'frames') {
        comparison = left.canonical_frame_count - right.canonical_frame_count;
      } else if (orderField === 'processing') {
        comparison = PROCESSING_ORDER.indexOf(userVideoStatus(left, jobs))
          - PROCESSING_ORDER.indexOf(userVideoStatus(right, jobs));
      } else if (orderField === 'annotation') {
        comparison = ANNOTATION_ORDER.indexOf(userAnnotationStatus(left))
          - ANNOTATION_ORDER.indexOf(userAnnotationStatus(right));
      } else {
        comparison = Date.parse(left.updated_at) - Date.parse(right.updated_at);
      }
      if (comparison !== 0) return comparison * multiplier;
      return left.filename.localeCompare(right.filename, undefined, { numeric: true }) * multiplier;
    });
  }, [annotationFilter, jobs, orderDirection, orderField, processingFilter, videoQuery, videos]);
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 2);
  const visible = filtered.slice(start, start + 12);
  const activeFilterCount = Number(processingFilter !== 'All') + Number(annotationFilter !== 'All');

  function clearFilters() {
    setProcessingFilter('All');
    setAnnotationFilter('All');
    resetScroll();
  }

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
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={() => input.current?.click()}
              className="w-20 h-8 bg-primary-container text-on-primary-container rounded font-label text-label-sm font-bold flex items-center justify-center gap-1.5"
            >
              <Upload size={15} />Import
            </button>
            {onExport && (
              <button
                type="button"
                onClick={onExport}
                className="w-20 h-8 border border-outline-variant bg-surface-container-low text-on-surface rounded font-label text-label-sm flex items-center justify-center gap-1.5 hover:border-primary hover:text-primary"
              >
                <Download size={14} className="text-primary" />Export
              </button>
            )}
          </div>
          <div className="ml-auto flex items-center gap-2 min-w-0">
            <span aria-label="Video count" title={filtered.length === videos.length ? `${videos.length} videos` : `${filtered.length} of ${videos.length} videos`} className="min-w-8 h-8 px-2 rounded border border-outline-variant bg-surface-container-lowest font-label text-[10px] text-on-surface-variant flex items-center justify-center whitespace-nowrap">{filtered.length === videos.length ? videos.length : `${filtered.length}/${videos.length}`}</span>
            <div className="relative">
            {onRename && (
              <button
                type="button"
                aria-label="More video actions"
                aria-expanded={moreOpen}
                onClick={() => setMoreOpen((open) => !open)}
                className="toolbar-icon border border-outline-variant"
              >
                <MoreHorizontal size={17} />
              </button>
            )}
            {moreOpen && onRename && (
              <div role="menu" className="absolute right-0 top-9 z-20 min-w-36 rounded border border-outline-variant bg-surface-container-high p-1 shadow-lg">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => { setRenameOpen(true); setRenameError(''); setMoreOpen(false); }}
                  className="w-full h-8 px-2 text-left rounded text-label-sm hover:bg-surface-container-highest flex items-center gap-2"
                >
                  <Pencil size={14} />Rename all
                </button>
              </div>
            )}
            </div>
          </div>
        </div>
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
        <label className="relative block">
          <span className="sr-only">Search videos by name</span>
          <Search size={14} className="absolute left-2.5 top-2.5 text-on-surface-variant" />
          <input
            type="search"
            aria-label="Search videos by name"
            value={videoQuery}
            onChange={(event) => {
              setVideoQuery(event.target.value);
              resetScroll();
            }}
            placeholder="Search video names"
            className="w-full h-8 bg-surface-container-lowest border border-outline-variant rounded pl-8 pr-2 text-label-sm"
          />
        </label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-expanded={filterOpen}
            onClick={() => setFilterOpen((open) => !open)}
            className={`h-8 px-2 border rounded font-label text-label-sm flex items-center gap-1.5 ${filterOpen || activeFilterCount ? 'border-primary text-primary bg-primary/10' : 'border-outline-variant text-on-surface-variant hover:border-primary'}`}
          >
            <ListFilter size={14} />Filters{activeFilterCount ? ` (${activeFilterCount})` : ''}
          </button>
          <label className="min-w-0 flex-1 flex items-center gap-1 h-8 px-2 bg-surface-container-lowest border border-outline-variant rounded font-label text-label-sm text-on-surface-variant">
            <span>Sort</span>
            <select
              aria-label="Order videos by"
              value={orderField}
              onChange={(event) => {
                setOrderField(event.target.value as OrderField);
                resetScroll();
              }}
              className="min-w-0 flex-1 bg-transparent text-on-surface outline-none"
            >
              {ORDER_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <button
            type="button"
            aria-label={orderDirection === 'asc' ? 'Sort ascending' : 'Sort descending'}
            title={orderDirection === 'asc' ? 'Sort ascending' : 'Sort descending'}
            onClick={() => {
              setOrderDirection((current) => current === 'asc' ? 'desc' : 'asc');
              resetScroll();
            }}
            className="w-8 h-8 rounded border border-outline-variant bg-surface-container-lowest flex items-center justify-center"
          >
            {orderDirection === 'asc' ? <ArrowUp size={15} /> : <ArrowDown size={15} />}
          </button>
        </div>
        {activeFilterCount > 0 && (
          <div className="flex flex-wrap gap-1" aria-label="Active filters">
            {processingFilter !== 'All' && <button type="button" onClick={() => { setProcessingFilter('All'); resetScroll(); }} className="h-6 px-1.5 rounded border border-primary/40 text-primary text-[10px] flex items-center gap-1">{processingFilter}<X size={11} /></button>}
            {annotationFilter !== 'All' && <button type="button" onClick={() => { setAnnotationFilter('All'); resetScroll(); }} className="h-6 px-1.5 rounded border border-primary/40 text-primary text-[10px] flex items-center gap-1">{annotationFilter}<X size={11} /></button>}
          </div>
        )}
        {filterOpen && (
          <div className="rounded border border-outline-variant bg-surface-container-low p-2 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <label className="min-w-0 font-label text-[10px] text-on-surface-variant">
                System processing
                <select
                  aria-label="Filter system processing status"
                  value={processingFilter}
                  onChange={(event) => { setProcessingFilter(event.target.value); resetScroll(); }}
                  className="mt-1 w-full h-8 bg-surface-container-lowest border border-outline-variant rounded px-2 text-label-sm"
                >
                  {PROCESSING_FILTERS.map((value) => <option key={value}>{value}</option>)}
                </select>
              </label>
              <label className="min-w-0 font-label text-[10px] text-on-surface-variant">
                User labelling
                <select
                  aria-label="Filter user labelling status"
                  value={annotationFilter}
                  onChange={(event) => { setAnnotationFilter(event.target.value); resetScroll(); }}
                  className="mt-1 w-full h-8 bg-surface-container-lowest border border-outline-variant rounded px-2 text-label-sm"
                >
                  {ANNOTATION_FILTERS.map((value) => <option key={value}>{value}</option>)}
                </select>
              </label>
            </div>
            {activeFilterCount > 0 && <button type="button" onClick={clearFilters} className="h-7 px-2 text-label-sm text-on-surface-variant hover:text-primary">Clear filters</button>}
          </div>
        )}
        {renameOpen && onRename && (
          <form
            className="rounded border border-outline-variant bg-surface-container-low p-2 space-y-2"
            onSubmit={(event) => {
              event.preventDefault();
              const prefix = renamePrefix.trim();
              if (!prefix || renaming) return;
              setRenaming(true);
              setRenameError('');
              void onRename(prefix).then(() => setRenameOpen(false)).catch((reason: unknown) => {
                setRenameError(reason instanceof Error ? reason.message : 'Could not rename videos.');
              }).finally(() => setRenaming(false));
            }}
          >
            <label className="block font-label text-[10px] text-on-surface-variant">
              Video name prefix
              <input aria-label="Video name prefix" value={renamePrefix} onChange={(event) => setRenamePrefix(event.target.value)} className="editor-input mt-1" placeholder="e.g. fall-test" />
            </label>
            <p className="text-[10px] text-on-surface-variant">Names become {renamePrefix.trim() || 'prefix'}_00001, preserving extensions.</p>
            {renameError && <p className="text-[10px] text-error">{renameError}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setRenameOpen(false)} className="h-7 px-2 border border-outline-variant rounded text-label-sm">Cancel</button>
              <button type="submit" disabled={renaming || !renamePrefix.trim()} className="h-7 px-2 bg-primary-container text-on-primary-container rounded text-label-sm disabled:opacity-40">{renaming ? 'Renaming…' : 'Rename all'}</button>
            </div>
          </form>
        )}
        {selectedIds.size > 0 && onDeleteSelected && (
          <div className="flex items-center justify-between gap-2 rounded border border-error/40 bg-error/5 px-2 py-1.5">
            <span className="font-label text-label-sm text-on-surface">{selectedIds.size} selected</span>
            <button type="button" onClick={onDeleteSelected} className="h-7 px-2 border border-error/50 text-error rounded font-label text-label-sm hover:bg-error/10">Delete selected ({selectedIds.size})</button>
          </div>
        )}
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
            const multiSelected = selectedIds.has(video.video_id);
            const processing = userVideoStatus(video, jobs);
            const annotation = userAnnotationStatus(video);
            const deleting = deletingIds.has(video.video_id);
            return (
              <div
                key={video.video_id}
                role="button"
                tabIndex={0}
                aria-label={`Open ${video.filename}`}
                aria-current={selected ? 'true' : undefined}
                onClick={(event) => {
                  if (deleting) return;
                  if ((event.ctrlKey || event.metaKey) && onToggleSelection) {
                    onToggleSelection(video);
                    return;
                  }
                  onSelect(video);
                }}
                onKeyDown={(event) => {
                  if (event.target !== event.currentTarget) return;
                  if (!deleting && ['Enter', ' '].includes(event.key)) {
                    event.preventDefault();
                    onSelect(video);
                  }
                }}
                className={`group absolute left-2 right-2 h-[98px] rounded border p-2 cursor-pointer transition-colors ${
                  selected || multiSelected
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
                      {onToggleSelection && (
                        <input
                          type="checkbox"
                          aria-label={`Select ${video.filename}`}
                          checked={multiSelected}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => onToggleSelection(video)}
                          className="mt-1 shrink-0"
                        />
                      )}
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
