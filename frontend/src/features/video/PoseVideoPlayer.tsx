import {
  forwardRef,
  useCallback,
  useEffect,
  useRef,
} from 'react';

import type { PoseTrackFrame, VideoItem } from '../../types';
import { videoMediaUrl } from '../../api/client';

const EDGES = [
  [5, 6],
  [5, 7],
  [7, 9],
  [6, 8],
  [8, 10],
  [5, 11],
  [6, 12],
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
  [0, 5],
  [0, 6],
];

interface Props {
  projectId: string;
  video: VideoItem;
  overlay?: PoseTrackFrame;
  selectedTrack?: number;
  selectedOnly: boolean;
  showSkeleton: boolean;
  showBoxes: boolean;
  onSelectTrack: (id: number) => void;
  onTimeUpdate: () => void;
  onMediaError?: () => void;
}

type PendingFrame = {
  kind: 'animation' | 'video';
  requestId: number;
};

/** Render the active media and keep its pose overlay synchronized. */
export const PoseVideoPlayer = forwardRef<HTMLVideoElement, Props>(
  function PoseVideoPlayer(
    {
      projectId,
      video,
      overlay,
      selectedTrack,
      selectedOnly,
      showSkeleton,
      showBoxes,
      onSelectTrack,
      onTimeUpdate,
      onMediaError,
    },
    forwardedRef,
  ) {
    const videoElementRef = useRef<HTMLVideoElement | null>(null);
    const mediaGenerationRef = useRef(0);
    const pendingFrameRef = useRef<PendingFrame>();
    const onTimeUpdateRef = useRef(onTimeUpdate);
    const onMediaErrorRef = useRef(onMediaError);
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
      if (!element) {
        return undefined;
      }

      const generation = mediaGenerationRef.current + 1;
      mediaGenerationRef.current = generation;

      const cancelFrameSync = () => {
        const pending = pendingFrameRef.current;
        if (!pending) {
          return;
        }
        if (pending.kind === 'video' && typeof element.cancelVideoFrameCallback === 'function') {
          element.cancelVideoFrameCallback(pending.requestId);
        } else if (pending.kind === 'animation') {
          window.cancelAnimationFrame(pending.requestId);
        }
        pendingFrameRef.current = undefined;
      };

      const isCurrentMedia = () => mediaGenerationRef.current === generation;

      const notifyFrame = () => {
        if (isCurrentMedia()) {
          onTimeUpdateRef.current();
        }
      };

      const scheduleFrameSync = () => {
        if (!isCurrentMedia() || element.paused || element.ended || pendingFrameRef.current) {
          return;
        }

        const tick = () => {
          pendingFrameRef.current = undefined;
          if (!isCurrentMedia() || element.paused || element.ended) {
            return;
          }
          notifyFrame();
          scheduleFrameSync();
        };

        if (typeof element.requestVideoFrameCallback === 'function') {
          pendingFrameRef.current = {
            kind: 'video',
            requestId: element.requestVideoFrameCallback(tick),
          };
        } else {
          pendingFrameRef.current = {
            kind: 'animation',
            requestId: window.requestAnimationFrame(tick),
          };
        }
      };

      const startFrameSync = () => {
        notifyFrame();
        scheduleFrameSync();
      };
      const stopFrameSync = () => {
        notifyFrame();
        cancelFrameSync();
      };
      const reportMediaError = () => {
        cancelFrameSync();
        if (isCurrentMedia()) onMediaErrorRef.current?.();
      };

      element.addEventListener('loadedmetadata', notifyFrame);
      element.addEventListener('seeked', notifyFrame);
      element.addEventListener('timeupdate', notifyFrame);
      element.addEventListener('play', startFrameSync);
      element.addEventListener('pause', stopFrameSync);
      element.addEventListener('ended', stopFrameSync);
      element.addEventListener('error', reportMediaError);

      // React reuses this element when the selected video changes. Explicitly
      // reset the resource selection algorithm so the decoder cannot retain a
      // disposed or failed source from the previously selected video.
      cancelFrameSync();
      element.pause();
      element.removeAttribute('src');
      element.src = source;
      element.currentTime = 0;
      element.load();

      return () => {
        if (isCurrentMedia()) {
          mediaGenerationRef.current += 1;
        }
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

    const tracks = overlay?.tracks.filter(
      (track) => !selectedOnly || track.track_id === selectedTrack,
    ) ?? [];

    return (
      <div className="relative bg-surface-container-lowest w-full h-full flex items-center justify-center overflow-hidden">
        <video
          ref={setVideoElement}
          className="w-full h-full object-contain"
          preload="auto"
          playsInline
        />
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox={`0 0 ${video.width} ${video.height}`}
          preserveAspectRatio="xMidYMid meet"
          aria-label="Pose and track overlay"
        >
          {tracks.map((track) => {
            const active = track.track_id === selectedTrack;
            return (
              <g
                key={track.track_id}
                className="pointer-events-auto cursor-pointer"
                onClick={() => onSelectTrack(track.track_id)}
              >
                {showBoxes && (
                  <>
                    <rect
                      x={track.bbox[0]}
                      y={track.bbox[1]}
                      width={track.bbox[2] - track.bbox[0]}
                      height={track.bbox[3] - track.bbox[1]}
                      fill="transparent"
                      stroke={active ? '#57f1db' : '#f59e0b'}
                      strokeWidth={active ? 3 : 2}
                      vectorEffect="non-scaling-stroke"
                    />
                    <rect
                      x={track.bbox[0]}
                      y={Math.max(0, track.bbox[1] - 20)}
                      width="72"
                      height="20"
                      fill={active ? '#2dd4bf' : '#b45309'}
                    />
                    <text
                      x={track.bbox[0] + 4}
                      y={Math.max(14, track.bbox[1] - 6)}
                      fontSize="12"
                      fill="#09100e"
                    >
                      TRACK {track.track_id}
                    </text>
                  </>
                )}
                {showSkeleton && EDGES.map(([start, end]) => (
                  track.keypoint_scores[start] >= 0.1
                    && track.keypoint_scores[end] >= 0.1
                    ? (
                      <line
                        key={`${start}-${end}`}
                        x1={track.keypoints[start][0]}
                        y1={track.keypoints[start][1]}
                        x2={track.keypoints[end][0]}
                        y2={track.keypoints[end][1]}
                        stroke={active ? '#57f1db' : '#fbbf24'}
                        strokeWidth="2"
                        vectorEffect="non-scaling-stroke"
                      />
                    ) : null
                ))}
              </g>
            );
          })}
        </svg>
        {tracks.length === 0 && video.processing_status === 'annotation_ready' && (
          <div className="absolute top-3 left-3 bg-surface-container/90 border border-outline-variant rounded px-2 py-1 text-label-sm">
            No pose at this frame
          </div>
        )}
      </div>
    );
  },
);
