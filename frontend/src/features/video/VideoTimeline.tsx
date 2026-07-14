/**
 * VideoTimeline — multi-layer temporal timeline for pose video labeling.
 *
 * Design decisions:
 * - The "LABEL" bar renders saved annotation segments only. Generated
 *   suggestions are materialized as editable segments instead of an overlay.
 * - Windows and the legacy Suggestions overlay are removed.
 * - When multiple tracks exist each track gets its own LABEL bar, stacked vertically.
 * - Segment blocks support drag-resize handles on their left/right edges (#11).
 * - Each block shows the class label when wide enough (#2).
 */

import { useRef, useState } from 'react';
import type { HumanVideoLabel, VideoSegment } from '../../types';

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
  mode: 'move' | 'start' | 'end';
  originX: number;
  originFrame: number;
  originalStart: number;
  originalEnd: number;
  start: number;
  end: number;
  /** Inclusive bounds that keep this segment clear of adjacent segments. */
  minimumStart: number;
  maximumEnd: number;
  frameCount: number;
  containerWidth: number;
}

interface Props {
  frameCount: number;
  currentFrame: number;
  /** All human segments (may span multiple tracks). */
  segments: VideoSegment[];
  /** segment_id of the currently selected segment (for highlight ring). */
  selectedSegment?: string;
  /** Called when the user clicks a position in the timeline. */
  onFrame: (frame: number) => void;
  /** Called when the user clicks a segment block. */
  onSegment: (segment: VideoSegment) => void;
  /** Called once when the user releases a resized segment boundary. */
  onSegmentResize?: (segmentId: string, start: number, end: number) => void;
}

export function VideoTimeline({
  frameCount,
  currentFrame,
  segments,
  selectedSegment,
  onFrame,
  onSegment,
  onSegmentResize,
}: Props) {
  const [zoom, setZoom] = useState(1);
  const [dragBounds, setDragBounds] = useState<{
    segmentId: string; start: number; end: number;
  }>();
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const ignoreNextClickRef = useRef(false);

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
    event: React.PointerEvent<HTMLElement>,
    segment: VideoSegment,
    mode: DragState['mode'],
  ) {
    event.stopPropagation();
    const container = containerRef.current;
    if (!container || !onSegmentResize) return;
    const rect = container.getBoundingClientRect();
    const adjacent = segments
      .filter((item) => item.track_id === segment.track_id && item.segment_id !== segment.segment_id)
      .sort((left, right) => left.start_frame - right.start_frame);
    const preceding = adjacent.filter((item) => item.end_frame < segment.start_frame);
    const previous = preceding[preceding.length - 1];
    const next = adjacent.find((item) => item.start_frame > segment.end_frame);
    dragRef.current = {
      segmentId: segment.segment_id,
      mode,
      originX: event.clientX,
      originFrame: mode === 'end' ? segment.end_frame : segment.start_frame,
      frameCount,
      containerWidth: rect.width,
      originalStart: segment.start_frame,
      originalEnd: segment.end_frame,
      start: segment.start_frame,
      end: segment.end_frame,
      minimumStart: Math.max(0, (previous?.end_frame ?? -1) + 1),
      maximumEnd: Math.min(frameCount - 1, (next?.start_frame ?? frameCount) - 1),
    };
    const target = event.target as Element;
    if (typeof target.setPointerCapture === 'function') {
      target.setPointerCapture(event.pointerId);
    }
  }

  function updateDragBounds(event: React.PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    if (!drag || !onSegmentResize) return;
    const deltaX = event.clientX - drag.originX;
    const framesPerPx = (drag.frameCount - 1) / Math.max(1, drag.containerWidth);
    const deltaFrames = Math.round(deltaX * framesPerPx);
    const newFrame = Math.max(0, Math.min(drag.frameCount - 1, drag.originFrame + deltaFrames));
    if (drag.mode === 'move') {
      const length = drag.originalEnd - drag.originalStart;
      const maximumStart = drag.maximumEnd - length;
      drag.start = Math.max(drag.minimumStart, Math.min(drag.originalStart + deltaFrames, maximumStart));
      drag.end = drag.start + length;
    } else if (drag.mode === 'start') {
      drag.start = Math.max(drag.minimumStart, Math.min(newFrame, drag.originalEnd - 1));
    } else {
      drag.end = Math.min(drag.maximumEnd, Math.max(newFrame, drag.originalStart + 1));
    }
    setDragBounds({ segmentId: drag.segmentId, start: drag.start, end: drag.end });
  }

  function handlePointerMove(event: React.PointerEvent<HTMLElement>) {
    updateDragBounds(event);
  }

  function handlePointerUp(event: React.PointerEvent<HTMLElement>) {
    event.stopPropagation();
    updateDragBounds(event);
    const drag = dragRef.current;
    if (drag && (drag.start !== drag.originalStart || drag.end !== drag.originalEnd)) {
      ignoreNextClickRef.current = true;
      onSegmentResize?.(drag.segmentId, drag.start, drag.end);
    }
    dragRef.current = null;
    setDragBounds(undefined);
  }

  function cancelSegmentDrag() {
    dragRef.current = null;
    setDragBounds(undefined);
  }

  // ── Derive per-track grouping ────────────────────────────────────────────────

  /** Unique track IDs in the order they first appear in segments; fallback to [0] */
  const trackIds = [...new Set(segments.map((s) => s.track_id))].sort((a, b) => a - b);
  const effectiveTracks = trackIds.length > 0 ? trackIds : [];

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
              return (
                <div key={trackId} className="flex items-center gap-2 mb-1">
                  <span className="w-16 shrink-0 font-label text-[10px] text-on-surface-variant text-right pr-2">
                    W{trackId}
                  </span>
                  <div
                    className="relative flex-1 h-8 bg-surface-container-lowest border border-outline-variant cursor-crosshair"
                    onClick={handleTimelineClick}
                  >
                    {/* Human segments */}
                    {trackSegments.map((seg) => {
                      const isSelected = selectedSegment === seg.segment_id;
                      const color = LABEL_COLORS[seg.label] ?? '#64748b';
                      const displayedBounds = dragBounds?.segmentId === seg.segment_id
                        ? dragBounds
                        : { start: seg.start_frame, end: seg.end_frame };
                      return (
                        <button
                          key={seg.segment_id}
                          type="button"
                          title={`${seg.label} frames ${seg.start_frame}–${seg.end_frame}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (ignoreNextClickRef.current) {
                              ignoreNextClickRef.current = false;
                              return;
                            }
                            onSegment(seg);
                          }}
                          onPointerDown={(e) => startSegmentDrag(e, seg, 'move')}
                          onPointerMove={handlePointerMove}
                          onPointerUp={handlePointerUp}
                          onPointerCancel={cancelSegmentDrag}
                          className={`absolute top-1 bottom-1 rounded-sm group cursor-grab active:cursor-grabbing ${isSelected ? 'ring-1 ring-white z-10' : ''}`}
                          style={{ ...blockStyle(displayedBounds.start, displayedBounds.end), background: color }}
                        >
                          {/* Left drag handle */}
                          {onSegmentResize && (
                            <span
                              role="separator"
                              aria-label="Drag segment start"
                              className="absolute left-0 top-0 bottom-0 w-1.5 cursor-ew-resize bg-white/30 hover:bg-white/60 rounded-l-sm z-20"
                              onPointerDown={(e) => startSegmentDrag(e, seg, 'start')}
                              onPointerMove={handlePointerMove}
                              onPointerUp={handlePointerUp}
                              onPointerCancel={cancelSegmentDrag}
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
                              onPointerDown={(e) => startSegmentDrag(e, seg, 'end')}
                              onPointerMove={handlePointerMove}
                              onPointerUp={handlePointerUp}
                              onPointerCancel={cancelSegmentDrag}
                            />
                          )}
                        </button>
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
        </div>
      </div>


    </section>
  );
}
