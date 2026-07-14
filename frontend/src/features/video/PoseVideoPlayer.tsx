/**
 * PoseVideoPlayer — video element with SVG pose/track overlay and fullscreen controls.
 *
 * Changes vs previous version:
 * - `showBoxes` controls both bbox rect AND skeleton (toggle means hide/show everything).
 * - Bbox label includes the current segment class for the displayed track (#14).
 * - Fullscreen mode renders a minimal play/pause button + scrubber overlay (#16).
 * - `currentSegments` prop provides the segments needed for class lookup.
 */

import {
  forwardRef,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { Pause, Play } from 'lucide-react';

import type { HumanVideoLabel, PoseTrackFrame, VideoItem, VideoSegment } from '../../types';
import { videoMediaUrl } from '../../api/client';

/** COCO-17 skeleton edges. */
const EDGES = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12],
  [11, 13], [13, 15], [12, 14], [14, 16],
  [0, 5], [0, 6],
];

/** Human-readable label colors (must match VideoTimeline). */
const LABEL_COLORS: Record<HumanVideoLabel, string> = {
  others: '#64748b',
  running: '#3b82f6',
  falling: '#ef4444',
};

interface Props {
  projectId: string;
  video: VideoItem;
  overlay?: PoseTrackFrame;
  selectedTrack?: number;
  selectedOnly: boolean;
  /** When true, hides both bounding boxes AND keypoint skeleton. */
  showBoxes: boolean;
  /** currentSegments is used to look up the class label shown on the bbox. */
  currentSegments?: VideoSegment[];
  /** Current canonical frame index, used to look up active segment class. */
  currentFrame?: number;
  onSelectTrack: (id: number) => void;
  onTimeUpdate: () => void;
  onMediaError?: () => void;
  /** Called when the scrubber in fullscreen mode changes position. */
  onSeek?: (frame: number) => void;
  playing?: boolean;
  onPlayPause?: () => void;
}

type PendingFrame = {
  kind: 'animation' | 'video';
  requestId: number;
};

/**
 * Look up which segment covers the given frame for a specific track.
 * Returns the label string, or undefined if uncovered.
 */
function segmentLabelAt(
  segments: VideoSegment[],
  trackId: number,
  frame: number,
): HumanVideoLabel | undefined {
  const seg = segments.find(
    (s) => s.track_id === trackId && frame >= s.start_frame && frame <= s.end_frame,
  );
  return seg?.label;
}

/** Render the active media and keep its pose overlay synchronized. */
export const PoseVideoPlayer = forwardRef<HTMLVideoElement, Props>(
  function PoseVideoPlayer(
    {
      projectId,
      video,
      overlay,
      selectedTrack,
      selectedOnly,
      showBoxes,
      currentSegments = [],
      currentFrame = 0,
      onSelectTrack,
      onTimeUpdate,
      onMediaError,
      onSeek,
      playing,
      onPlayPause,
    },
    forwardedRef,
  ) {
    const videoElementRef = useRef<HTMLVideoElement | null>(null);
    const mediaGenerationRef = useRef(0);
    const pendingFrameRef = useRef<PendingFrame>();
    const onTimeUpdateRef = useRef(onTimeUpdate);
    const onMediaErrorRef = useRef(onMediaError);
    const [isFullscreen, setIsFullscreen] = useState(false);

    onTimeUpdateRef.current = onTimeUpdate;
    onMediaErrorRef.current = onMediaError;

    const setVideoElement = useCallback((element: HTMLVideoElement | null) => {
      videoElementRef.current = element;
      if (typeof forwardedRef === 'function') {
        forwardedRef(element);
      } else if (forwardedRef) {
        forwardedRef.current = element;
      }
    }, [forwardedRef]);

    const source = videoMediaUrl(projectId, video.video_id);

    useEffect(() => {
      const element = videoElementRef.current;
      if (!element) return undefined;

      const generation = mediaGenerationRef.current + 1;
      mediaGenerationRef.current = generation;

      const cancelFrameSync = () => {
        const pending = pendingFrameRef.current;
        if (!pending) return;
        if (pending.kind === 'video' && typeof element.cancelVideoFrameCallback === 'function') {
          element.cancelVideoFrameCallback(pending.requestId);
        } else if (pending.kind === 'animation') {
          window.cancelAnimationFrame(pending.requestId);
        }
        pendingFrameRef.current = undefined;
      };

      const isCurrentMedia = () => mediaGenerationRef.current === generation;
      const notifyFrame = () => { if (isCurrentMedia()) onTimeUpdateRef.current(); };

      const scheduleFrameSync = () => {
        if (!isCurrentMedia() || element.paused || element.ended || pendingFrameRef.current) return;
        const tick = () => {
          pendingFrameRef.current = undefined;
          if (!isCurrentMedia() || element.paused || element.ended) return;
          notifyFrame();
          scheduleFrameSync();
        };
        if (typeof element.requestVideoFrameCallback === 'function') {
          pendingFrameRef.current = { kind: 'video', requestId: element.requestVideoFrameCallback(tick) };
        } else {
          pendingFrameRef.current = { kind: 'animation', requestId: window.requestAnimationFrame(tick) };
        }
      };

      const startFrameSync = () => { notifyFrame(); scheduleFrameSync(); };
      const stopFrameSync = () => { notifyFrame(); cancelFrameSync(); };
      const reportMediaError = () => { cancelFrameSync(); if (isCurrentMedia()) onMediaErrorRef.current?.(); };

      element.addEventListener('loadedmetadata', notifyFrame);
      element.addEventListener('seeked', notifyFrame);
      element.addEventListener('timeupdate', notifyFrame);
      element.addEventListener('play', startFrameSync);
      element.addEventListener('pause', stopFrameSync);
      element.addEventListener('ended', stopFrameSync);
      element.addEventListener('error', reportMediaError);

      cancelFrameSync();
      element.pause();
      element.removeAttribute('src');
      element.src = source;
      element.currentTime = 0;
      element.load();

      return () => {
        if (isCurrentMedia()) mediaGenerationRef.current += 1;
        cancelFrameSync();
        element.removeEventListener('loadedmetadata', notifyFrame);
        element.removeEventListener('seeked', notifyFrame);
        element.removeEventListener('timeupdate', notifyFrame);
        element.removeEventListener('play', startFrameSync);
        element.removeEventListener('pause', stopFrameSync);
        element.removeEventListener('ended', stopFrameSync);
        element.removeEventListener('error', reportMediaError);
        element.pause();
        element.removeAttribute('src');
        element.load();
      };
    }, [source]);

    // Track fullscreen state changes
    useEffect(() => {
      const onFsChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
      document.addEventListener('fullscreenchange', onFsChange);
      return () => document.removeEventListener('fullscreenchange', onFsChange);
    }, []);

    const visibleTracks = overlay?.tracks.filter(
      (track) => !selectedOnly || track.track_id === selectedTrack,
    ) ?? [];

    const totalFrames = video.canonical_frame_count;
    const scrubPercent = totalFrames > 1 ? (currentFrame / (totalFrames - 1)) * 100 : 0;

    return (
      <div className="relative bg-surface-container-lowest w-full h-full flex items-center justify-center overflow-hidden">
        <video
          ref={setVideoElement}
          className="w-full h-full object-contain"
          preload="auto"
          playsInline
        />

        {/* Pose + bbox SVG overlay */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox={`0 0 ${video.width} ${video.height}`}
          preserveAspectRatio="xMidYMid meet"
          aria-label="Pose and track overlay"
        >
          {visibleTracks.map((track) => {
            const isActive = track.track_id === selectedTrack;
            // Look up the class label at the current frame for bbox annotation (#14)
            const classLabel = segmentLabelAt(currentSegments, track.track_id, currentFrame);
            const baseColor = classLabel ? LABEL_COLORS[classLabel] : '#64748b';
            const bboxStroke = isActive ? baseColor : `${baseColor}cc`;
            const bboxFill = baseColor;

            return (
              <g
                key={track.track_id}
                className="pointer-events-auto cursor-pointer"
                onClick={() => onSelectTrack(track.track_id)}
              >
                {/* Bounding box — controlled by showBoxes (#13) */}
                {showBoxes && (
                  <>
                    <rect
                      data-testid={`worker-label-${track.track_id}`}
                      x={track.bbox[0]}
                      y={track.bbox[1]}
                      width={track.bbox[2] - track.bbox[0]}
                      height={track.bbox[3] - track.bbox[1]}
                      fill="transparent"
                      stroke={bboxStroke}
                      strokeWidth={isActive ? 3 : 2}
                      vectorEffect="non-scaling-stroke"
                    />
                    {/* Label background */}
                    <rect
                      x={track.bbox[0]}
                      y={Math.max(0, track.bbox[1] - 22)}
                      width={track.bbox[2] - track.bbox[0]}
                      height={20}
                      fill={bboxFill}
                    />
                    {/* Label text: TRACK N · class (#14) */}
                    <text
                      x={track.bbox[0] + 4}
                      y={Math.max(14, track.bbox[1] - 6)}
                      fontSize="11"
                      fill="#fff"
                      fontWeight="bold"
                    >
                      {`W${track.track_id}${classLabel ? ` · ${classLabel}` : ''}`}
                    </text>
                  </>
                )}

                {/* Skeleton — also controlled by showBoxes (#13: toggle hides both) */}
                {showBoxes && EDGES.map(([start, end]) =>
                  track.keypoint_scores[start] >= 0.1 && track.keypoint_scores[end] >= 0.1 ? (
                    <line
                      key={`${start}-${end}`}
                      x1={track.keypoints[start][0]}
                      y1={track.keypoints[start][1]}
                      x2={track.keypoints[end][0]}
                      y2={track.keypoints[end][1]}
                      stroke={isActive ? baseColor : `${baseColor}bb`}
                      strokeWidth="2"
                      vectorEffect="non-scaling-stroke"
                    />
                  ) : null,
                )}
              </g>
            );
          })}
        </svg>

        {/* No-pose notice */}
        {visibleTracks.length === 0 && video.processing_status === 'annotation_ready' && (
          <div className="absolute top-3 left-3 bg-surface-container/90 border border-outline-variant rounded px-2 py-1 text-label-sm">
            No pose at this frame
          </div>
        )}

        {/* Fullscreen overlay: play/pause + scrubber (#16) */}
        {isFullscreen && (
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-3 flex flex-col gap-2 pointer-events-auto">
            {/* Scrubber */}
            <input
              aria-label="Video scrubber"
              type="range"
              min={0}
              max={totalFrames - 1}
              value={currentFrame}
              onChange={(e) => onSeek?.(Number(e.target.value))}
              className="w-full accent-primary h-1.5 cursor-pointer"
            />
            <div className="flex items-center gap-3">
              {onPlayPause && (
                <button
                  type="button"
                  aria-label={playing ? 'Pause' : 'Play'}
                  onClick={onPlayPause}
                  className="w-9 h-9 bg-primary-container text-on-primary-container rounded-full flex items-center justify-center"
                >
                  {playing ? <Pause size={18} /> : <Play size={18} />}
                </button>
              )}
              <span className="text-white text-xs font-mono">
                {currentFrame} / {totalFrames - 1}
              </span>
            </div>
          </div>
        )}
      </div>
    );
  },
);
