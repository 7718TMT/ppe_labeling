import { useRef, useState } from 'react';

import type {
  BehaviorEvent, HumanVideoLabel, VideoTrack,
} from '../../types';
import { useFramePreviews } from './hooks/useFramePreviews';


const PREVIEW_COUNT = 12;
const LABEL_COLORS: Record<HumanVideoLabel, string> = {
  others: '#64748b',
  running: '#3b82f6',
  falling: '#ef4444',
};

export interface InferenceTimelineSegment {
  segmentId: string;
  trackId: number;
  startFrame: number;
  endFrame: number;
  label: HumanVideoLabel;
}

/** Fill every non-action range in each worker lifespan with `others`. */
export function buildInferenceTimelineSegments(
  tracks: VideoTrack[],
  events: BehaviorEvent[],
  frameCount: number,
): InferenceTimelineSegment[] {
  const maximumFrame = Math.max(0, frameCount - 1);
  const trackById = new Map(tracks.map((track) => [track.track_id, track]));
  const trackIds = [...new Set([
    ...tracks.map((track) => track.track_id),
    ...events.map((event) => event.track_id),
  ])].sort((left, right) => left - right);

  return trackIds.flatMap((trackId) => {
    const track = trackById.get(trackId);
    const trackStart = Math.max(0, track?.start_frame ?? 0);
    const trackEnd = Math.min(maximumFrame, track?.end_frame ?? maximumFrame);
    const actions = events
      .filter((event) => (
        event.track_id === trackId
        && event.end_frame >= trackStart
        && event.start_frame <= trackEnd
      ))
      .sort((left, right) => left.start_frame - right.start_frame);
    const segments: InferenceTimelineSegment[] = [];
    let cursor = trackStart;

    for (const action of actions) {
      const actionStart = Math.max(cursor, trackStart, action.start_frame);
      const actionEnd = Math.min(trackEnd, action.end_frame);
      if (actionStart > cursor) {
        segments.push({
          segmentId: `others-${trackId}-${cursor}-${actionStart - 1}`,
          trackId,
          startFrame: cursor,
          endFrame: actionStart - 1,
          label: 'others',
        });
      }
      if (actionEnd >= actionStart) {
        segments.push({
          segmentId: action.suggestion_id,
          trackId,
          startFrame: actionStart,
          endFrame: actionEnd,
          label: action.suggested_label,
        });
        cursor = actionEnd + 1;
      }
    }
    if (cursor <= trackEnd) {
      segments.push({
        segmentId: `others-${trackId}-${cursor}-${trackEnd}`,
        trackId,
        startFrame: cursor,
        endFrame: trackEnd,
        label: 'others',
      });
    }
    return segments;
  });
}

interface Props {
  frameCount: number;
  currentFrame: number;
  mediaUrl: string;
  tracks: VideoTrack[];
  events: BehaviorEvent[];
  selectedTrack?: number;
  onFrame: (frame: number) => void;
  onSegment: (segment: InferenceTimelineSegment) => void;
}

/** Read-only frame-preview and prediction-event timeline for inference. */
export function InferenceTimeline({
  frameCount,
  currentFrame,
  mediaUrl,
  tracks,
  events,
  selectedTrack,
  onFrame,
  onSegment,
}: Props) {
  const { samples, previews } = useFramePreviews(
    frameCount,
    mediaUrl,
    PREVIEW_COUNT,
  );
  const [hoverFrame, setHoverFrame] = useState<number>();
  const stripRef = useRef<HTMLDivElement>(null);
  const maximumFrame = Math.max(0, frameCount - 1);
  const toPercent = (value: number) => (
    `${(value / Math.max(1, maximumFrame)) * 100}%`
  );
  const blockStyle = (start: number, end: number) => ({
    left: `${(start / Math.max(1, frameCount)) * 100}%`,
    width: `${Math.max(
      0.25,
      ((end - start + 1) / Math.max(1, frameCount)) * 100,
    )}%`,
  });

  function frameAt(clientX: number): number {
    const rect = stripRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return 0;
    return Math.max(0, Math.min(maximumFrame, Math.round(
      ((clientX - rect.left) / rect.width) * maximumFrame,
    )));
  }

  function seek(event: React.MouseEvent<HTMLDivElement>) {
    onFrame(frameAt(event.clientX));
  }

  const orderedTracks = [...new Set([
    ...tracks.map((track) => track.track_id),
    ...events.map((event) => event.track_id),
  ])].sort((left, right) => left - right);
  const segments = buildInferenceTimelineSegments(tracks, events, frameCount);

  return (
    <section
      className="bg-surface-container border-t border-outline-variant p-3 select-none"
      aria-label="Inference frame timeline"
    >
      <div className="flex items-center justify-between mb-2 font-label text-[10px] text-on-surface-variant">
        <span>FRAME PREVIEW</span>
        <span>
          Frame {currentFrame} / {maximumFrame}
          {hoverFrame !== undefined ? ` · Preview ${hoverFrame}` : ''}
        </span>
      </div>

      <div className="flex">
        <span className="w-12 shrink-0 pt-2 font-label text-[9px] text-on-surface-variant">
          VIDEO
        </span>
        <div
          ref={stripRef}
          className="relative h-20 flex-1 overflow-hidden border border-outline-variant bg-surface-container-lowest cursor-pointer"
          onClick={seek}
          onMouseMove={(event) => setHoverFrame(frameAt(event.clientX))}
          onMouseLeave={() => setHoverFrame(undefined)}
        >
          {samples.map((previewFrame, index) => (
            <div
              key={`${index}-${previewFrame}`}
              className="absolute inset-y-0 border-r border-black/30 bg-surface-container-high"
              style={{
                left: `${(index / samples.length) * 100}%`,
                width: `${100 / samples.length}%`,
              }}
            >
              {previews[previewFrame] && (
                <img
                  src={previews[previewFrame]}
                  alt={`Frame ${previewFrame}`}
                  className="w-full h-full object-cover"
                />
              )}
              <span className="absolute bottom-0 left-1 text-[9px] text-white drop-shadow">
                {previewFrame}
              </span>
            </div>
          ))}
          <span
            className="timeline-playhead absolute inset-y-0 z-20 w-px bg-primary pointer-events-none"
            style={{ left: toPercent(currentFrame) }}
          />
        </div>
      </div>

      <div className="max-h-24 overflow-y-auto">
        {orderedTracks.map((trackId) => (
          <div className="flex mt-1" key={trackId}>
            <span className={`w-12 shrink-0 font-label text-[9px] ${selectedTrack === trackId ? 'text-primary' : 'text-on-surface-variant'}`}>
              W{trackId}
            </span>
            <div
              className={`relative h-6 flex-1 border cursor-pointer ${selectedTrack === trackId ? 'border-primary/60 bg-primary/5' : 'border-outline-variant bg-surface-container-lowest'}`}
              onClick={seek}
            >
              {segments.filter((segment) => segment.trackId === trackId).map((segment) => (
                <button
                  key={segment.segmentId}
                  type="button"
                  title={`${segment.label} · frames ${segment.startFrame}-${segment.endFrame}`}
                  aria-label={`Worker ${trackId} ${segment.label}, frames ${segment.startFrame} to ${segment.endFrame}`}
                  className="absolute inset-y-0 overflow-hidden px-1 text-[9px] text-white capitalize hover:brightness-125 focus-visible:outline focus-visible:outline-1 focus-visible:outline-primary"
                  style={{
                    ...blockStyle(segment.startFrame, segment.endFrame),
                    backgroundColor: LABEL_COLORS[segment.label],
                  }}
                  onClick={(clickEvent) => {
                    clickEvent.stopPropagation();
                    onSegment(segment);
                  }}
                >
                  {segment.label}
                </button>
              ))}
              <span
                className="timeline-playhead absolute inset-y-0 z-20 w-px bg-primary pointer-events-none"
                style={{ left: toPercent(currentFrame) }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="ml-12 h-4 relative font-label text-[9px] text-on-surface-variant">
        <span className="absolute left-0">0</span>
        <span className="absolute left-1/2 -translate-x-1/2">
          {Math.round(maximumFrame / 2)}
        </span>
        <span className="absolute right-0">{maximumFrame}</span>
      </div>
    </section>
  );
}
