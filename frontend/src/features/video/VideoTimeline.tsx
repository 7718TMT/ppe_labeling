/**
 * VideoTimeline — multi-layer temporal timeline for pose video labeling.
 *
 * Design decisions:
 * - The "LABEL" bar replaces the old "HUMAN" bar. Pending suggestions are rendered
 *   as translucent overlay blocks on the same row (visually distinct via opacity /
 *   dashed border) so the annotator sees suggestions in context.
 * - Windows and a separate Suggestions row are removed per UX spec (#10, #5).
 * - When multiple tracks exist each track gets its own LABEL bar, stacked vertically.
 * - Segment blocks support drag-resize handles on their left/right edges (#11).
 * - Each block shows the class label when wide enough (#2).
 */

import { useRef, useState } from 'react';
import type {
  GeneratedWindow,
  HumanVideoLabel,
  SuggestionSource,
  VideoSegment,
  VideoSuggestion,
} from '../../types';

/** Hex color per label class matching the design palette. */
const LABEL_COLORS: Record<HumanVideoLabel, string> = {
  others: '#64748b',
  running: '#3b82f6',
  falling: '#ef4444',
};

/** Minimum pixel width for showing the label text inside a segment block. */
const MIN_LABEL_WIDTH_PX = 36;

interface DragState {
  segmentId: string;
  edge: 'start' | 'end';
  originX: number;
  originFrame: number;
  frameCount: number;
  containerLeft: number;
  containerWidth: number;
}

interface Props {
  frameCount: number;
  currentFrame: number;
  /** All human segments (may span multiple tracks). */
  segments: VideoSegment[];
  /** Pending suggestions from the active source. */
  suggestions: VideoSuggestion[];
  /** Currently active suggestion source. */
  source: SuggestionSource;
  /** segment_id of the currently selected segment (for highlight ring). */
  selectedSegment?: string;
  /** Called when the user clicks a position in the timeline. */
  onFrame: (frame: number) => void;
  /** Called when the user clicks a segment block. */
  onSegment: (segment: VideoSegment) => void;
  /** Called when a suggestion block is clicked. */
  onSuggestion: (suggestion: VideoSuggestion) => void;
  /** Called when the user drags a segment boundary (segment_id, newStart, newEnd). */
  onSegmentResize?: (segmentId: string, start: number, end: number) => void;
}

export function VideoTimeline({
  frameCount,
  currentFrame,
  segments,
  suggestions,
  source,
  selectedSegment,
  onFrame,
  onSegment,
  onSuggestion,
  onSegmentResize,
}: Props) {
  const [zoom, setZoom] = useState(1);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);

  /** Convert a frame number to a CSS left percentage string relative to the timeline area. */
  const toPercent = (frame: number) =>
    `${(frame / Math.max(1, frameCount - 1)) * 100}%`;

  /** Compute left + width CSS for a [start, end] inclusive frame range. */
  const blockStyle = (start: number, end: number) => ({
    left: toPercent(start),
    width: `${Math.max(0.25, ((end - start + 1) / Math.max(1, frameCount)) * 100)}%`,
  });

  /** Handle click on the timeline background to seek. */
  function handleTimelineClick(event: React.MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const relativeX = event.clientX - rect.left;
    const frame = Math.round((relativeX / rect.width) * (frameCount - 1));
    onFrame(Math.max(0, Math.min(frameCount - 1, frame)));
  }

  // ── Drag-resize logic ────────────────────────────────────────────────────────

  function startSegmentDrag(
    event: React.PointerEvent<HTMLButtonElement>,
    segment: VideoSegment,
    edge: 'start' | 'end',
  ) {
    event.stopPropagation();
    const container = containerRef.current;
    if (!container || !onSegmentResize) return;
    const rect = container.getBoundingClientRect();
    dragRef.current = {
      segmentId: segment.segment_id,
      edge,
      originX: event.clientX,
      originFrame: edge === 'start' ? segment.start_frame : segment.end_frame,
      frameCount,
      containerLeft: rect.left,
      containerWidth: rect.width,
    };
    (event.target as Element).setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || !onSegmentResize) return;
    const deltaX = event.clientX - drag.originX;
    const framesPerPx = (drag.frameCount - 1) / Math.max(1, drag.containerWidth);
    const deltaFrames = Math.round(deltaX * framesPerPx);
    const newFrame = Math.max(0, Math.min(drag.frameCount - 1, drag.originFrame + deltaFrames));
    const seg = segments.find((s) => s.segment_id === drag.segmentId);
    if (!seg) return;
    if (drag.edge === 'start') {
      onSegmentResize(drag.segmentId, Math.min(newFrame, seg.end_frame - 1), seg.end_frame);
    } else {
      onSegmentResize(drag.segmentId, seg.start_frame, Math.max(newFrame, seg.start_frame + 1));
    }
  }

  function handlePointerUp(event: React.PointerEvent<HTMLButtonElement>) {
    event.stopPropagation();
    dragRef.current = null;
  }

  // ── Derive per-track grouping ────────────────────────────────────────────────

  /** Unique track IDs in the order they first appear in segments; fallback to [0] */
  const trackIds = [...new Set(segments.map((s) => s.track_id))].sort((a, b) => a - b);
  const effectiveTracks = trackIds.length > 0 ? trackIds : [];

  /** Pending suggestions to overlay on the label bar. */
  const pendingSuggestions = suggestions.filter((s) => s.review_status === 'pending');

  return (
    <section
      className="bg-surface-container border-t border-outline-variant p-3 select-none"
      aria-label="Multi-layer timeline"
    >
      {/* Zoom control */}
      <div className="flex justify-end items-center gap-2 mb-2 font-label text-[10px] text-on-surface-variant">
        <span>Zoom</span>
        <input
          aria-label="Timeline zoom"
          type="range"
          min="1"
          max="8"
          step="0.5"
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
        />
        <span>{zoom.toFixed(1)}×</span>
      </div>

      <div className="overflow-x-auto">
        <div
          className="relative"
          style={{ width: `${zoom * 100}%` }}
          ref={containerRef}
        >
          {/* Per-track label rows */}
          {effectiveTracks.length === 0 ? (
            // No segments yet — show a single empty placeholder bar
            <div className="flex items-center gap-2 mb-1">
              <span className="w-16 shrink-0 font-label text-[10px] text-on-surface-variant text-right pr-2">
                LABEL
              </span>
              <div
                className="relative flex-1 h-7 bg-surface-container-lowest border border-outline-variant cursor-crosshair"
                onClick={handleTimelineClick}
              >
                {/* Current frame marker */}
                <span
                  className="absolute top-0 bottom-0 w-px bg-primary pointer-events-none z-20"
                  style={{ left: toPercent(currentFrame) }}
                />
              </div>
            </div>
          ) : (
            effectiveTracks.map((trackId) => {
              const trackSegments = segments.filter((s) => s.track_id === trackId);
              const trackSuggestions = pendingSuggestions.filter((s) => s.track_id === trackId);
              return (
                <div key={trackId} className="flex items-center gap-2 mb-1">
                  <span className="w-16 shrink-0 font-label text-[10px] text-on-surface-variant text-right pr-2">
                    T{trackId}
                  </span>
                  <div
                    className="relative flex-1 h-8 bg-surface-container-lowest border border-outline-variant cursor-crosshair"
                    onClick={handleTimelineClick}
                  >
                    {/* Human segments */}
                    {trackSegments.map((seg) => {
                      const isSelected = selectedSegment === seg.segment_id;
                      const color = LABEL_COLORS[seg.label] ?? '#64748b';
                      return (
                        <button
                          key={seg.segment_id}
                          type="button"
                          title={`${seg.label} frames ${seg.start_frame}–${seg.end_frame}`}
                          onClick={(e) => { e.stopPropagation(); onSegment(seg); }}
                          className={`absolute top-1 bottom-1 rounded-sm group ${isSelected ? 'ring-1 ring-white z-10' : ''}`}
                          style={{ ...blockStyle(seg.start_frame, seg.end_frame), background: color }}
                        >
                          {/* Left drag handle */}
                          {onSegmentResize && (
                            <span
                              role="separator"
                              aria-label="Drag segment start"
                              className="absolute left-0 top-0 bottom-0 w-1.5 cursor-ew-resize bg-white/30 hover:bg-white/60 rounded-l-sm z-20"
                              onPointerDown={(e) => startSegmentDrag(e as unknown as React.PointerEvent<HTMLButtonElement>, seg, 'start')}
                              onPointerMove={(e) => handlePointerMove(e as unknown as React.PointerEvent<HTMLButtonElement>)}
                              onPointerUp={(e) => handlePointerUp(e as unknown as React.PointerEvent<HTMLButtonElement>)}
                            />
                          )}
                          {/* Class label text — shown when block is wide enough */}
                          <span className="absolute inset-0 flex items-center justify-center text-white text-[9px] font-bold uppercase pointer-events-none overflow-hidden">
                            {seg.label}
                          </span>
                          {/* Right drag handle */}
                          {onSegmentResize && (
                            <span
                              role="separator"
                              aria-label="Drag segment end"
                              className="absolute right-0 top-0 bottom-0 w-1.5 cursor-ew-resize bg-white/30 hover:bg-white/60 rounded-r-sm z-20"
                              onPointerDown={(e) => startSegmentDrag(e as unknown as React.PointerEvent<HTMLButtonElement>, seg, 'end')}
                              onPointerMove={(e) => handlePointerMove(e as unknown as React.PointerEvent<HTMLButtonElement>)}
                              onPointerUp={(e) => handlePointerUp(e as unknown as React.PointerEvent<HTMLButtonElement>)}
                            />
                          )}
                        </button>
                      );
                    })}

                    {/* Suggestion overlays (translucent, on top of human segments) */}
                    {trackSuggestions.map((sug) => {
                      const color = LABEL_COLORS[sug.suggested_label] ?? '#64748b';
                      const borderStyle = source === 'AI' ? 'border-dashed' : 'border-solid';
                      return (
                        <button
                          key={sug.suggestion_id}
                          type="button"
                          title={`${source} suggestion: ${sug.suggested_label} ${Math.round(sug.confidence * 100)}% — frames ${sug.start_frame}–${sug.end_frame}`}
                          onClick={(e) => { e.stopPropagation(); onSuggestion(sug); }}
                          className={`absolute top-0.5 bottom-0.5 border-2 ${borderStyle} z-10 rounded-sm`}
                          style={{
                            ...blockStyle(sug.start_frame, sug.end_frame),
                            borderColor: color,
                            backgroundColor: `${color}30`,
                          }}
                        />
                      );
                    })}

                    {/* Current frame marker */}
                    <span
                      className="absolute top-0 bottom-0 w-px bg-primary pointer-events-none z-30"
                      style={{ left: toPercent(currentFrame) }}
                    />
                  </div>
                </div>
              );
            })
          )}

          {/* Quality bar */}
          <div className="flex items-center gap-2 mt-0.5">
            <span className="w-16 shrink-0 font-label text-[10px] text-on-surface-variant text-right pr-2">QUALITY</span>
            <div className="relative flex-1 h-2 bg-gradient-to-r from-error/60 via-amber-400/40 to-emerald-400/60" />
          </div>
        </div>
      </div>

      {/* Frame labels */}
      <div className="font-label text-label-sm text-on-surface-variant flex justify-between mt-2">
        <span>Frame 0</span>
        <span>Current {currentFrame}</span>
        <span>Frame {frameCount - 1}</span>
      </div>
    </section>
  );
}
