/**
 * VideoWorkspace — main pose-video labeling workspace.
 *
 * Key UX changes vs previous version:
 * #1  Multi-segment: create/manage multiple segments per track independently.
 * #3  Fill-gaps: per-track button fills unlabeled ranges with a chosen class.
 * #4  Generated suggestions are materialized as editable segments; the LABEL
 *     bar renders those segments only.
 * #5  Source selector (Off/Threshold/AI) lives as a compact dropdown in the navbar.
 * #7  After import, the pipeline is auto-queued (backend handles it); no extra call needed.
 * #8  Multi-track merge: checkbox-based selection on track cards, Merge button appears.
 * #9  Approve/Unapprove button at sidebar bottom; Export Dataset button in navbar.
 * #10 Windows row removed from timeline; windows approved by default (backend default).
 * #11 Draggable segment handles via VideoTimeline's onSegmentResize callback.
 * #12 Per-track inline actions (Split, Exclude/Restore) on track cards; no dropdown.
 * #13 showBoxes toggle hides/shows both bbox and skeleton (single toggle).
 * #14 PoseVideoPlayer receives currentSegments for class label in bbox.
 * #15 Auto-trigger feature extraction 5 s after last segment change, on approve, on video change.
 * #16 Fullscreen: play/pause + scrubber handled inside PoseVideoPlayer.
 * #17 Rearranged segment action buttons (cleaner grid).
 * #18 Details tab: video facts, annotation summary, and overlay controls.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
  HelpCircle,
  Loader2,
  Maximize2,
  Minimize2,
  PanelLeft,
  PanelRight,
  Pause,
  Play,
  Redo2,
  Repeat2,
  Save,
  Scissors,
  SkipBack,
  SkipForward,
  Undo2,
  X,
} from 'lucide-react';

import {
  approveVideo,
  createVideoExport,
  deleteVideo as deleteImportedVideo,
  deleteVideoSegment,
  deleteVideoTrack,
  extendVideoSegment,
  flushVideoWorkspaceStateOnExit,
  getPoseOverlay,
  getVideoSegments,
  getVideoTracks,
  importVideos,
  mergeMultipleVideoTracks,
  mergeVideoSegments,
  processVideo,
  renameVideos,
  saveVideoSegment,
  saveVideoWorkspaceState,
  setVideoSegmentInclusion,
  setVideoTrackInclusion,
  splitVideoSegment,
  splitVideoTrack,
  trimVideo,
  unapproveVideo,
  videoHistoryAction,
  videoMediaUrl,
  getFeatures,
} from '../api/client';
import { ExportPanel } from '../features/video/ExportPanel';
import { PoseHelpDialog } from '../features/video/PoseHelpDialog';
import { PoseVideoPlayer } from '../features/video/PoseVideoPlayer';
import { SuggestionModeButton, type ProcessMode } from '../features/video/ProcessModeButton';
import { ProcessingQueue } from '../features/video/ProcessingQueue';
import { ShortcutGuideOverlay } from '../features/video/ShortcutGuideOverlay';
import { VideoBrowser } from '../features/video/VideoBrowser';
import { useVideoWorkspaceSync } from '../features/video/hooks/useVideoWorkspaceSync';
import { VideoTimeline } from '../features/video/VideoTimeline';
import { TrimTimeline } from '../features/video/TrimTimeline';
import type {
  FeatureWindow,
  GeneratedWindow,
  HumanVideoLabel,
  PoseTrackFrame,
  ProcessingJob,
  ProcessingOptions,
  SuggestionSource,
  VideoItem,
  VideoExportRecord,
  VideoProject,
  VideoSegment,
  VideoTrack,
  VideoWorkspaceEvent,
  VideoWorkspaceSnapshot,
  VideoWorkspaceState,
} from '../types';

/** Right-sidebar tabs. Suggestions tab removed (#4). */
type RightTab = 'annotate' | 'details';
type SelectionScope = 'video' | 'worker' | 'segment';

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'paused']);
const LEFT_SIDEBAR_WIDTH_KEY = 'video-workspace-left-sidebar-width';
const RIGHT_SIDEBAR_WIDTH_KEY = 'video-workspace-right-sidebar-width';
const SIDEBAR_MIN_WIDTH = 240;
const SIDEBAR_MAX_WIDTH = 520;

function savedSidebarWidth(key: string, fallback: number): number {
  const parsed = Number(window.localStorage.getItem(key));
  return Number.isFinite(parsed) && parsed >= SIDEBAR_MIN_WIDTH && parsed <= SIDEBAR_MAX_WIDTH
    ? parsed
    : fallback;
}
/** A five-second overlay batch balances playback smoothness and request count. */
const OVERLAY_CHUNK_FRAMES = 120;
const OVERLAY_RETRY_BASE_MS = 1_000;
const OVERLAY_RETRY_MAX_MS = 30_000;

interface OverlayCache {
  videoId?: string;
  frames: Map<number, PoseTrackFrame>;
  loaded: Set<number>;
  pending: Set<string>;
  retryAt: Map<string, number>;
  failureCount: Map<string, number>;
}

/** Build a per-video overlay cache with bounded retry state. */
function createOverlayCache(videoId?: string): OverlayCache {
  return {
    videoId,
    frames: new Map(),
    loaded: new Set(),
    pending: new Set(),
    retryAt: new Map(),
    failureCount: new Map(),
  };
}

/** Human-friendly label colors, reused for fill-gaps indicator. */
const LABEL_COLORS: Record<HumanVideoLabel, string> = {
  others: '#64748b',
  running: '#3b82f6',
  falling: '#ef4444',
};

function upsertJobRows(current: ProcessingJob[], incoming: ProcessingJob[]): ProcessingJob[] {
  const rows = new Map(current.map((job) => [job.job_id, job]));
  incoming.forEach((job) => rows.set(job.job_id, job));
  return [...rows.values()];
}

function readableError(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

/** Narrow an opaque workspace-event payload before applying it to UI state. */
function asEventRecord(payload: unknown): Record<string, unknown> | undefined {
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : undefined;
}

interface WorkspaceRecoveryWrite {
  projectId: string;
  payload: VideoWorkspaceState;
  fingerprint: string;
}

/** Format a frame location as a compact playback timestamp. */
function formatFrameTimestamp(frameIndex: number, fps: number): string {
  const totalSeconds = Math.max(0, frameIndex) / Math.max(1, fps);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const tenths = Math.floor((totalSeconds % 1) * 10);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${tenths}`;
}

/** Render status values stored as snake case in a user-facing form. */
function displayStatus(value: string): string {
  return value.replaceAll('_', ' ');
}

/** Count the distinct video frames covered by at least one segment. */
function countCoveredFrames(segments: VideoSegment[], frameCount: number): number {
  if (frameCount <= 0) return 0;
  const ranges = segments
    .map((segment) => ({
      start: Math.max(0, segment.start_frame),
      end: Math.min(frameCount - 1, segment.end_frame),
    }))
    .filter((range) => range.start <= range.end)
    .sort((left, right) => left.start - right.start);
  let covered = 0;
  let rangeStart = -1;
  let rangeEnd = -1;
  for (const range of ranges) {
    if (rangeStart < 0) {
      rangeStart = range.start;
      rangeEnd = range.end;
    } else if (range.start <= rangeEnd + 1) {
      rangeEnd = Math.max(rangeEnd, range.end);
    } else {
      covered += rangeEnd - rangeStart + 1;
      rangeStart = range.start;
      rangeEnd = range.end;
    }
  }
  return rangeStart < 0 ? 0 : covered + rangeEnd - rangeStart + 1;
}

/**
 * Return ranges within [trackStart, trackEnd] that are NOT covered by any segment,
 * sorted by start_frame. Used for the fill-gaps feature (#3).
 */
function uncoveredRanges(
  segments: VideoSegment[],
  trackStart: number,
  trackEnd: number,
): Array<{ start: number; end: number }> {
  const sorted = [...segments].sort((a, b) => a.start_frame - b.start_frame);
  const gaps: Array<{ start: number; end: number }> = [];
  let cursor = trackStart;
  for (const seg of sorted) {
    if (seg.start_frame > cursor) {
      gaps.push({ start: cursor, end: seg.start_frame - 1 });
    }
    cursor = Math.max(cursor, seg.end_frame + 1);
  }
  if (cursor <= trackEnd) {
    gaps.push({ start: cursor, end: trackEnd });
  }
  return gaps;
}

export function VideoWorkspace() {
  const { projectId = '' } = useParams();
  const player = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const activeIdRef = useRef<string>();
  const videosRef = useRef<VideoItem[]>([]);
  const frameRef = useRef(0);
  const revisionRef = useRef(0);
  const activeLoadRef = useRef(0);
  const activeDetailLoadRef = useRef(0);
  const activeDetailAbortRef = useRef<AbortController>();
  const projectRef = useRef<VideoProject | null>(null);
  const processingTransitionRef = useRef<{ videoId?: string; active: boolean }>({ active: false });
  const pendingMediaSeekRef = useRef<{ videoId: string; seconds: number }>();
  const workspaceSaveChainRef = useRef<Promise<unknown>>(Promise.resolve());
  const workspaceLastSavedFingerprintRef = useRef<string>();
  const workspaceLatestWriteRef = useRef<WorkspaceRecoveryWrite>();
  const workspaceSaveTimerRef = useRef<number>();
  const workspaceStateRef = useRef<VideoWorkspaceState>();
  const savingRequestCountRef = useRef(0);
  const deletingSegmentIdRef = useRef<string>();
  const activeDetailRefreshTimerRef = useRef<number>();
  const overlayCacheRef = useRef<OverlayCache>(createOverlayCache());

  const [project, setProject] = useState<VideoProject | null>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [exports, setExports] = useState<VideoExportRecord[]>([]);
  const [active, setActive] = useState<VideoItem | null>(null);
  const [tracks, setTracks] = useState<VideoTrack[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<number>();
  /** Set of worker IDs selected for merge or bulk deletion. */
  const [mergeTrackIds, setMergeTrackIds] = useState<Set<number>>(new Set());
  const [segments, setSegments] = useState<VideoSegment[]>([]);
  const [revision, setRevision] = useState(0);
  const [selectedSegment, setSelectedSegment] = useState<VideoSegment>();
  const [selectedSegmentIds, setSelectedSegmentIds] = useState<Set<string>>(new Set());
  const [creatingSegment, setCreatingSegment] = useState(false);
  const [mergeSegmentId, setMergeSegmentId] = useState<string>();
  const [source, setSource] = useState<SuggestionSource>('Threshold');
  const [processingOptions, setProcessingOptions] = useState<ProcessingOptions>({
    threshold_available: true,
    model_available: false,
    model_message: 'Model suggestions are not configured for this project.',
  });
  /** Fill-gaps class picker per track; key=track_id, value=label to fill (#3). */
  const [fillClass, setFillClass] = useState<HumanVideoLabel>('others');
  const [overlay, setOverlay] = useState<PoseTrackFrame>();
  const [overlayCacheRevision, setOverlayCacheRevision] = useState(0);
  const [features, setFeatures] = useState<FeatureWindow[]>([]);
  const [frame, setFrame] = useState(0);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [label, setLabel] = useState<HumanVideoLabel>('others');
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [trimMode, setTrimMode] = useState(false);
  const [trimRange, setTrimRange] = useState<{ start: number; end: number }>();
  const [trimPreviewing, setTrimPreviewing] = useState(false);
  const [trimUndo, setTrimUndo] = useState<Array<{ start: number; end: number }>>([]);
  const [trimRedo, setTrimRedo] = useState<Array<{ start: number; end: number }>>([]);
  const [trimSaving, setTrimSaving] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  /** showBoxes now controls BOTH bbox and skeleton (#13). */
  const [showBoxes, setShowBoxes] = useState(true);
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [leftOpen, setLeftOpen] = useState(() => window.innerWidth >= 900);
  const [rightOpen, setRightOpen] = useState(() => window.innerWidth >= 1200);
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(() => savedSidebarWidth(LEFT_SIDEBAR_WIDTH_KEY, 320));
  const [rightSidebarWidth, setRightSidebarWidth] = useState(() => savedSidebarWidth(RIGHT_SIDEBAR_WIDTH_KEY, 360));
  const sidebarResizeRef = useRef<{ side: 'left' | 'right'; startX: number; startWidth: number }>();
  const [tab, setTab] = useState<RightTab>('annotate');
  const [saving, setSaving] = useState(false);
  const [autosaveFailedDraft, setAutosaveFailedDraft] = useState<string>();
  const [processingRequests, setProcessingRequests] = useState<Set<string>>(new Set());
  const [processingBatchVideoIds, setProcessingBatchVideoIds] = useState<Set<string>>(new Set());
  const [pendingDeleteIds, setPendingDeleteIds] = useState<string[]>([]);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());
  const [selectionScope, setSelectionScope] = useState<SelectionScope>();
  const [helpOpen, setHelpOpen] = useState(false);
  const [shortcutGuideVisible, setShortcutGuideVisible] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [historyUnavailable, setHistoryUnavailable] = useState<'undo' | 'redo' | null>(null);

  projectRef.current = project;
  videosRef.current = videos;
  activeIdRef.current = active?.video_id;
  frameRef.current = frame;
  revisionRef.current = revision;

  useEffect(() => () => { activeIdRef.current = undefined; }, []);

  /** Resize a sidebar locally; persistence happens only after the drag ends. */
  const resizeSidebar = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const drag = sidebarResizeRef.current;
    if (!drag) return;
    const direction = drag.side === 'left' ? 1 : -1;
    const maximum = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, window.innerWidth * 0.48));
    const width = Math.max(SIDEBAR_MIN_WIDTH, Math.min(maximum, drag.startWidth + (event.clientX - drag.startX) * direction));
    if (drag.side === 'left') setLeftSidebarWidth(width);
    else setRightSidebarWidth(width);
  }, []);

  const finishSidebarResize = useCallback(() => {
    const drag = sidebarResizeRef.current;
    if (!drag) return;
    const width = drag.side === 'left' ? leftSidebarWidth : rightSidebarWidth;
    window.localStorage.setItem(drag.side === 'left' ? LEFT_SIDEBAR_WIDTH_KEY : RIGHT_SIDEBAR_WIDTH_KEY, String(Math.round(width)));
    sidebarResizeRef.current = undefined;
    document.body.classList.remove('cursor-col-resize', 'select-none');
  }, [leftSidebarWidth, rightSidebarWidth]);

  const startSidebarResize = useCallback((side: 'left' | 'right', event: React.PointerEvent<HTMLDivElement>) => {
    sidebarResizeRef.current = { side, startX: event.clientX, startWidth: side === 'left' ? leftSidebarWidth : rightSidebarWidth };
    event.currentTarget.setPointerCapture(event.pointerId);
    document.body.classList.add('cursor-col-resize', 'select-none');
  }, [leftSidebarWidth, rightSidebarWidth]);

  useEffect(() => {
    if (!active) return;
    setTrimRange({ start: 0, end: active.canonical_frame_count - 1 });
    setTrimUndo([]);
    setTrimRedo([]);
    setTrimPreviewing(false);
  }, [active?.video_id, active?.canonical_frame_count]);

  useEffect(() => {
    const synchronizeFullscreen = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', synchronizeFullscreen);
    synchronizeFullscreen();
    return () => document.removeEventListener('fullscreenchange', synchronizeFullscreen);
  }, []);

  useEffect(() => {
    function showShortcutGuide(event: KeyboardEvent) {
      if (event.key === 'Alt' && !event.repeat && !helpOpen && pendingDeleteIds.length === 0 && !exportOpen) {
        setShortcutGuideVisible(true);
      }
    }
    function hideShortcutGuide(event: KeyboardEvent) {
      if (event.key === 'Alt') setShortcutGuideVisible(false);
    }
    function clearShortcutGuide() {
      setShortcutGuideVisible(false);
    }
    window.addEventListener('keydown', showShortcutGuide);
    window.addEventListener('keyup', hideShortcutGuide);
    window.addEventListener('blur', clearShortcutGuide);
    return () => {
      window.removeEventListener('keydown', showShortcutGuide);
      window.removeEventListener('keyup', hideShortcutGuide);
      window.removeEventListener('blur', clearShortcutGuide);
    };
  }, [exportOpen, helpOpen, pendingDeleteIds.length]);

  useEffect(() => {
    setHistoryUnavailable(null);
  }, [revision]);

  /** Reload only the active video's mutable annotation details after an event. */
  const refreshActiveDetails = useCallback(async (videoId: string) => {
    const generation = activeDetailLoadRef.current + 1;
    activeDetailLoadRef.current = generation;
    activeDetailAbortRef.current?.abort();
    const controller = new AbortController();
    activeDetailAbortRef.current = controller;
    try {
      const [trackRows, segmentData, featureData] = await Promise.all([
        getVideoTracks(projectId, videoId, controller.signal),
        getVideoSegments(projectId, videoId, controller.signal),
        getFeatures(projectId, videoId).catch(() => [] as FeatureWindow[]),
      ]);
      if (
        controller.signal.aborted
        || generation !== activeDetailLoadRef.current
        || activeIdRef.current !== videoId
      ) return;
      setTracks(trackRows);
      setSelectedTrack((current) => {
        if (current !== undefined && trackRows.some((track) => track.track_id === current)) return current;
        return trackRows.slice().sort(
          (left, right) => (right.end_frame - right.start_frame) - (left.end_frame - left.start_frame),
        )[0]?.track_id;
      });
      setSegments(segmentData.segments);
      setFeatures(featureData);
      setRevision(segmentData.revision);
      setSelectedSegment((current) => current
        ? segmentData.segments.find((item) => item.segment_id === current.segment_id)
        : undefined);
    } catch (reason) {
      if (
        !controller.signal.aborted
        && generation === activeDetailLoadRef.current
        && activeIdRef.current === videoId
      ) {
        setError(`Could not refresh annotation changes. ${readableError(reason)}`);
      }
    }
  }, [projectId]);

  /** Coalesce a burst of annotation events into one active-video detail read. */
  const queueActiveDetailsRefresh = useCallback((videoId: string) => {
    if (activeIdRef.current !== videoId || activeDetailRefreshTimerRef.current) return;
    activeDetailRefreshTimerRef.current = window.setTimeout(() => {
      activeDetailRefreshTimerRef.current = undefined;
      void refreshActiveDetails(videoId);
    }, 40);
  }, [refreshActiveDetails]);

  useEffect(() => () => {
    if (activeDetailRefreshTimerRef.current) {
      window.clearTimeout(activeDetailRefreshTimerRef.current);
    }
    activeDetailAbortRef.current?.abort();
  }, []);

  /** Apply the one compact snapshot used to initialize or recover the workspace. */
  const applyWorkspaceSnapshot = useCallback((snapshot: VideoWorkspaceSnapshot) => {
    const videoRows = snapshot.videos;
    const options = snapshot.processing_options;
    videosRef.current = videoRows;
    workspaceStateRef.current = snapshot.project.workspace_state ?? undefined;
    setProject(snapshot.project);
    setVideos(videoRows);
    setJobs(snapshot.jobs);
    setExports(snapshot.exports ?? []);
    setProcessingOptions(options);
    setSelectedVideoIds((current) => new Set(
      [...current].filter((videoId) => videoRows.some((item) => item.video_id === videoId)),
    ));
    setActive((current) => {
      if (current) return videoRows.find((item) => item.video_id === current.video_id) ?? videoRows[0] ?? null;
      return videoRows.find((item) => item.video_id === snapshot.project.workspace_state?.video_id)
        ?? videoRows[0]
        ?? null;
    });
    setSource((current) => {
      if (current !== 'Threshold') return current;
      const remembered = snapshot.project.workspace_state?.suggestion_source ?? 'Threshold';
      return remembered === 'AI' && !options.model_available ? 'Off' : remembered;
    });
  }, []);

  /** Apply a small outbox event without re-reading the full workspace shell. */
  const applyWorkspaceEvent = useCallback((event: VideoWorkspaceEvent) => {
    const payload = asEventRecord(event.payload);
    if (!payload) return;

    if (event.event_type === 'job.changed') {
      const job = payload.job as ProcessingJob | undefined;
      if (job?.job_id) setJobs((current) => upsertJobRows(current, [job]));
      return;
    }

    if (event.event_type === 'video.changed') {
      const videoId = typeof payload.video_id === 'string' ? payload.video_id : event.video_id;
      if (!videoId) return;
      if (payload.deleted === true) {
        const remaining = videosRef.current.filter((item) => item.video_id !== videoId);
        videosRef.current = remaining;
        setVideos(remaining);
        setJobs((current) => current.filter((job) => job.video_id !== videoId));
        setProcessingBatchVideoIds((current) => new Set(
          [...current].filter((candidate) => candidate !== videoId),
        ));
        setSelectedVideoIds((current) => {
          const next = new Set(current);
          next.delete(videoId);
          return next;
        });
        setActive((current) => current?.video_id === videoId ? remaining[0] ?? null : current);
        return;
      }
      const video = payload.video as VideoItem | undefined;
      if (!video?.video_id) return;
      const currentVideos = videosRef.current;
      const nextVideos = currentVideos.some((item) => item.video_id === video.video_id)
        ? currentVideos.map((item) => item.video_id === video.video_id ? video : item)
        : [...currentVideos, video];
      videosRef.current = nextVideos;
      setVideos(nextVideos);
      setActive((current) => {
        if (current?.video_id === video.video_id) return video;
        return current ?? nextVideos[0] ?? null;
      });
      return;
    }

    if (event.event_type === 'annotation.changed' || event.event_type === 'tracks.changed') {
      const videoId = typeof payload.video_id === 'string' ? payload.video_id : event.video_id;
      if (!videoId) return;
      const nextRevision = typeof payload.annotation_revision === 'number'
        ? payload.annotation_revision
        : undefined;
      const annotationStatus = typeof payload.annotation_status === 'string'
        ? payload.annotation_status
        : undefined;
      const approved = typeof payload.is_approved === 'boolean'
        ? Number(payload.is_approved)
        : undefined;
      const applySummary = (item: VideoItem): VideoItem => item.video_id !== videoId ? item : {
        ...item,
        ...(nextRevision === undefined ? {} : { annotation_revision: nextRevision }),
        ...(annotationStatus === undefined ? {} : { annotation_status: annotationStatus }),
        ...(approved === undefined ? {} : { is_approved: approved }),
      };
      setVideos((current) => {
        const next = current.map(applySummary);
        videosRef.current = next;
        return next;
      });
      setActive((current) => current ? applySummary(current) : current);
      const needsDetailRefresh = event.event_type === 'tracks.changed'
        || payload.reason === 'tracks_replaced'
        || nextRevision === undefined
        || nextRevision > revisionRef.current;
      if (activeIdRef.current === videoId && needsDetailRefresh) {
        queueActiveDetailsRefresh(videoId);
      }
      return;
    }

    if (event.event_type === 'export.changed') {
      const exportRecord = payload.export as VideoExportRecord | undefined;
      if (!exportRecord?.export_id) return;
      setExports((current) => {
        const existing = current.find((item) => item.export_id === exportRecord.export_id);
        if (existing) {
          return current.map((item) => item.export_id === exportRecord.export_id
            ? { ...item, ...exportRecord }
            : item);
        }
        return [exportRecord, ...current];
      });
    }
  }, [queueActiveDetailsRefresh]);

  const applyWorkspaceEvents = useCallback((events: VideoWorkspaceEvent[]) => {
    events.forEach(applyWorkspaceEvent);
  }, [applyWorkspaceEvent]);

  const workspaceSync = useVideoWorkspaceSync({
    projectId,
    onSnapshot: applyWorkspaceSnapshot,
    onEvent: applyWorkspaceEvent,
    onEvents: applyWorkspaceEvents,
  });
  const refreshShell = workspaceSync.refresh;

  function beginProcessingBatch(videoIds: string[]) {
    const activeVideoIds = new Set(
      jobs.filter((job) => ACTIVE_JOB_STATUSES.has(job.status) && job.video_id).map((job) => job.video_id as string),
    );
    setProcessingBatchVideoIds((current) => {
      const currentHasActiveWork = [...current].some((videoId) => activeVideoIds.has(videoId));
      return new Set(currentHasActiveWork ? [...current, ...videoIds] : videoIds);
    });
  }

  useEffect(() => {
    const activeVideoIds = new Set(
      jobs.filter((job) => ACTIVE_JOB_STATUSES.has(job.status) && job.video_id)
        .map((job) => job.video_id as string),
    );
    setProcessingBatchVideoIds((current) => {
      const next = new Set([...current].filter((videoId) => activeVideoIds.has(videoId)));
      if (next.size === current.size && [...next].every((videoId) => current.has(videoId))) {
        return current;
      }
      return next;
    });
  }, [jobs]);

  const loadActive = useCallback(async (video: VideoItem) => {
    const generation = activeLoadRef.current + 1;
    activeLoadRef.current = generation;
    const detailGeneration = activeDetailLoadRef.current + 1;
    activeDetailLoadRef.current = detailGeneration;
    activeDetailAbortRef.current?.abort();
    const detailController = new AbortController();
    activeDetailAbortRef.current = detailController;
    setError('');
    setMessage('');
    setPlaying(false);
    setOverlay(undefined);
    overlayCacheRef.current = createOverlayCache(video.video_id);
    setOverlayCacheRevision((c) => c + 1);
    setTracks([]);
    setSegments([]);
    setFeatures([]);
    setSelectedTrack(undefined);
    setMergeTrackIds(new Set());
    setSelectedSegment(undefined);
    setCreatingSegment(false);
    setMergeSegmentId(undefined);
    setAutosaveFailedDraft(undefined);
    setFrame(0);
    setStart(0);
    setEnd(0);
    setLabel('others');
    setLoop(false);
    try {
      const [trackRows, segmentData, featureData] = await Promise.all([
        getVideoTracks(projectId, video.video_id, detailController.signal),
        getVideoSegments(projectId, video.video_id, detailController.signal),
        getFeatures(projectId, video.video_id).catch(() => [] as FeatureWindow[]),
      ]);
      if (
        detailController.signal.aborted
        ||
        generation !== activeLoadRef.current
        || detailGeneration !== activeDetailLoadRef.current
        || activeIdRef.current !== video.video_id
      ) return;
      setTracks(trackRows);
      setSegments(segmentData.segments);
      setFeatures(featureData);
      setRevision(segmentData.revision);
      const workspace = workspaceStateRef.current ?? projectRef.current?.workspace_state;
      const rememberedTrack = workspace?.video_id === video.video_id ? workspace.track_id : undefined;
      const longestTrack = trackRows.slice().sort(
        (a, b) => (b.end_frame - b.start_frame) - (a.end_frame - a.start_frame),
      )[0];
      const nextTrack = trackRows.find((item) => item.track_id === rememberedTrack) ?? longestTrack;
      setSelectedTrack(nextTrack?.track_id);
      const rememberedFrame = workspace?.video_id === video.video_id ? workspace.frame_index : 0;
      const nextFrame = Math.max(0, Math.min(video.canonical_frame_count - 1, rememberedFrame ?? 0));
      setFrame(nextFrame);
      setStart(nextFrame);
      setEnd(nextFrame);
      pendingMediaSeekRef.current = { videoId: video.video_id, seconds: nextFrame / video.canonical_fps };
      window.requestAnimationFrame(() => {
        if (activeIdRef.current === video.video_id && player.current) {
          try { player.current.currentTime = nextFrame / video.canonical_fps; pendingMediaSeekRef.current = undefined; } catch { /* loadedmetadata will apply */ }
        }
      });
    } catch (reason) {
      if (
        !detailController.signal.aborted
        && generation === activeLoadRef.current
        && detailGeneration === activeDetailLoadRef.current
        && activeIdRef.current === video.video_id
      ) setError(readableError(reason));
    }
  }, [projectId]);

  useEffect(() => {
    if (active) {
      void loadActive(active);
    } else {
      activeLoadRef.current += 1;
      pendingMediaSeekRef.current = undefined;
      setTracks([]);
      setSegments([]);
      setOverlay(undefined);
      setPlaying(false);
    }
  }, [active?.video_id, loadActive]);

  useEffect(() => {
    if (!active || !showBoxes) { setOverlay(undefined); return; }
    const videoId = active.video_id;
    const requestedFrame = frame;
    let cache = overlayCacheRef.current;
    if (cache.videoId !== videoId) {
      cache = createOverlayCache(videoId);
      overlayCacheRef.current = cache;
    }
    if (cache.loaded.has(requestedFrame)) { setOverlay(cache.frames.get(requestedFrame)); return; }
    setOverlay(undefined);
    const chunkStart = Math.floor(requestedFrame / OVERLAY_CHUNK_FRAMES) * OVERLAY_CHUNK_FRAMES;
    const chunkEnd = Math.min(active.canonical_frame_count - 1, chunkStart + OVERLAY_CHUNK_FRAMES - 1);
    const chunkKey = `${chunkStart}:${chunkEnd}`;
    if ((cache.retryAt.get(chunkKey) ?? 0) > Date.now()) return;
    if (cache.pending.has(chunkKey)) return;
    cache.pending.add(chunkKey);
    getPoseOverlay(projectId, videoId, chunkStart, chunkEnd).then((rows) => {
      const currentCache = overlayCacheRef.current;
      if (currentCache !== cache || currentCache.videoId !== videoId) return;
      rows.forEach((item) => currentCache.frames.set(item.frame_index, item));
      for (let index = chunkStart; index <= chunkEnd; index += 1) currentCache.loaded.add(index);
      currentCache.pending.delete(chunkKey);
      currentCache.retryAt.delete(chunkKey);
      currentCache.failureCount.delete(chunkKey);
      if (activeIdRef.current === videoId) setOverlay(currentCache.frames.get(frameRef.current));
    }).catch(() => {
      const currentCache = overlayCacheRef.current;
      if (currentCache !== cache) return;
      if (currentCache.videoId === videoId) {
        currentCache.pending.delete(chunkKey);
        const failureCount = (currentCache.failureCount.get(chunkKey) ?? 0) + 1;
        currentCache.failureCount.set(chunkKey, failureCount);
        const retryDelay = Math.min(
          OVERLAY_RETRY_MAX_MS,
          OVERLAY_RETRY_BASE_MS * 2 ** Math.min(failureCount - 1, 5),
        );
        currentCache.retryAt.set(chunkKey, Date.now() + retryDelay);
      }
      if (activeIdRef.current === videoId && frameRef.current === requestedFrame) setOverlay(undefined);
    });
  }, [active?.video_id, active?.canonical_frame_count, frame, overlayCacheRevision, projectId, showBoxes]);

  /** Persist the newest recovery position without allowing older writes to win. */
  const flushWorkspaceRecoveryState = useCallback(() => {
    const pending = workspaceLatestWriteRef.current;
    if (!pending || workspaceLastSavedFingerprintRef.current === pending.fingerprint) return;
    if (workspaceSaveTimerRef.current) {
      window.clearTimeout(workspaceSaveTimerRef.current);
      workspaceSaveTimerRef.current = undefined;
    }
    workspaceSaveChainRef.current = workspaceSaveChainRef.current
      .catch(() => undefined)
      .then(async () => {
        if (workspaceLastSavedFingerprintRef.current === pending.fingerprint) return;
        await saveVideoWorkspaceState(pending.projectId, pending.payload);
        workspaceLastSavedFingerprintRef.current = pending.fingerprint;
        // A newer interaction may already have updated this ref optimistically.
        if (workspaceLatestWriteRef.current?.fingerprint !== pending.fingerprint) return;
        workspaceStateRef.current = pending.payload;
        setProject((current) => current
          ? { ...current, workspace_state: pending.payload }
          : current);
      })
      .catch(() => {
        if (activeIdRef.current === pending.payload.video_id) {
          setError('Workspace recovery state could not be saved.');
        }
      });
  }, []);

  useEffect(() => {
    const flushWhenHidden = () => {
      if (document.visibilityState === 'hidden') flushWorkspaceRecoveryState();
    };
    const flushOnPageHide = () => {
      const pending = workspaceLatestWriteRef.current;
      if (!pending || workspaceLastSavedFingerprintRef.current === pending.fingerprint) return;
      flushVideoWorkspaceStateOnExit(pending.projectId, pending.payload);
    };
    document.addEventListener('visibilitychange', flushWhenHidden);
    window.addEventListener('pagehide', flushOnPageHide);
    return () => {
      document.removeEventListener('visibilitychange', flushWhenHidden);
      window.removeEventListener('pagehide', flushOnPageHide);
      flushWorkspaceRecoveryState();
    };
  }, [flushWorkspaceRecoveryState]);

  // While playing, checkpoint recovery only every five seconds. Pausing,
  // changing workers, or changing the suggestion mode still saves the exact
  // current frame, so the reduced write rate does not weaken recovery UX.
  const workspaceFrameCheckpoint = active && playing
    ? Math.floor(frame / Math.max(1, Math.round(active.canonical_fps * 5)))
    : frame;

  useEffect(() => {
    if (!active) return undefined;
    const payload: VideoWorkspaceState = {
      video_id: active.video_id,
      track_id: selectedTrack,
      frame_index: frameRef.current,
      suggestion_source: source,
    };
    const fingerprint = JSON.stringify({ projectId, ...payload });
    workspaceStateRef.current = payload;
    workspaceLatestWriteRef.current = { projectId, payload, fingerprint };
    if (workspaceLastSavedFingerprintRef.current === fingerprint) return undefined;
    const timer = window.setTimeout(() => {
      if (workspaceSaveTimerRef.current === timer) {
        workspaceSaveTimerRef.current = undefined;
      }
      flushWorkspaceRecoveryState();
    }, 500);
    workspaceSaveTimerRef.current = timer;
    return () => {
      if (workspaceSaveTimerRef.current === timer) {
        window.clearTimeout(timer);
        workspaceSaveTimerRef.current = undefined;
      }
    };
  }, [
    active?.video_id,
    flushWorkspaceRecoveryState,
    playing,
    projectId,
    selectedTrack,
    source,
    workspaceFrameCheckpoint,
  ]);

  // ── Video playback helpers ──────────────────────────────────────────────────

  function seek(next: number) {
    if (!active) return;
    const value = Math.max(0, Math.min(active.canonical_frame_count - 1, Math.round(next)));
    setFrame(value);
    if (player.current) player.current.currentTime = value / active.canonical_fps;
  }

  async function togglePlay() {
    const element = player.current;
    if (!element) return;
    if (element.paused || element.ended) {
      if (element.ended) element.currentTime = 0;
      try { await element.play(); setPlaying(true); }
      catch { setPlaying(false); setError('The video could not start. Try selecting it again.'); }
    } else {
      element.pause();
      setPlaying(false);
    }
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await containerRef.current?.requestFullscreen();
      }
    } catch {
      setError('Fullscreen could not be changed.');
    }
  }

  useEffect(() => {
    if (player.current) player.current.loop = loop && !selectedSegment && !trimPreviewing;
  }, [loop, selectedSegment, trimPreviewing]);

  function updateTrimRange(next: { start: number; end: number }) {
    if (!trimRange || next.start === trimRange.start && next.end === trimRange.end) return;
    setTrimUndo((current) => [...current, trimRange]);
    setTrimRedo([]);
    setTrimRange(next);
  }

  function undoTrim() {
    const previous = trimUndo.at(-1);
    if (!previous || !trimRange) return;
    setTrimUndo((current) => current.slice(0, -1));
    setTrimRedo((current) => [...current, trimRange]);
    setTrimRange(previous);
  }

  function redoTrim() {
    const next = trimRedo.at(-1);
    if (!next || !trimRange) return;
    setTrimRedo((current) => current.slice(0, -1));
    setTrimUndo((current) => [...current, trimRange]);
    setTrimRange(next);
  }

  function previewTrim() {
    if (!trimRange) return;
    setTrimPreviewing(true);
    setLoop(true);
    seek(trimRange.start);
    void player.current?.play();
  }

  async function saveTrim(saveMode: 'replace' | 'copy') {
    if (!active || !trimRange || trimSaving) return;
    if (trimRange.end - trimRange.start + 1 < 60) {
      setError('Select at least 60 frames to create one analysis window.');
      return;
    }
    let copyFilename: string | undefined;
    if (saveMode === 'copy') {
      const defaultName = `${active.filename.replace(/\.[^.]+$/, '')}_copy.mp4`;
      const enteredName = window.prompt(
        `Name the trimmed copy. Leave blank to use "${defaultName}".`,
        '',
      );
      if (enteredName === null) return;
      copyFilename = enteredName.trim() || undefined;
    }
    if (saveMode === 'replace' && !window.confirm(
      'Replace this video with the trimmed range? Existing labels will be clipped to fit. Processing and approval data will be reset.',
    )) return;
    const videoAtSave = active;
    setTrimSaving(true);
    setError('');
    player.current?.pause();
    setPlaying(false);
    try {
      const result = await trimVideo(
        projectId,
        videoAtSave.video_id,
        trimRange.start,
        trimRange.end,
        saveMode,
        copyFilename,
        source === 'AI' ? 'model' : 'threshold',
      );
      setVideos((current) => {
        const next = saveMode === 'copy'
          ? [...current, result.video]
          : current.map((item) => item.video_id === result.video.video_id ? result.video : item);
        videosRef.current = next;
        return next;
      });
      setActive(result.video);
      setTrimMode(false);
      setTrimPreviewing(false);
      setTrimUndo([]);
      setTrimRedo([]);
      if (result.jobs?.length) {
        setJobs((current) => upsertJobRows(current, result.jobs ?? []));
        beginProcessingBatch(result.jobs.map((job) => job.video_id).filter(Boolean) as string[]);
      }
      await loadActive(result.video);
      const subject = saveMode === 'copy' ? 'Trimmed copy saved.' : 'Video replaced with the trimmed range.';
      setMessage(result.processing_action === 'keypoints_copied'
        ? `${subject} Overlapping labels and matching keypoints were retained.`
        : `${subject} Keypoint processing and automatic suggestions were queued.`);
    } catch (reason) {
      if (activeIdRef.current === videoAtSave.video_id) {
        setError(`Could not save the trim. ${readableError(reason)}`);
      }
    } finally {
      setTrimSaving(false);
    }
  }

  function synchronizePlayer() {
    const element = player.current;
    const currentVideo = active;
    if (!element || !currentVideo) return;
    const pendingSeek = pendingMediaSeekRef.current;
    if (pendingSeek?.videoId === currentVideo.video_id) {
      try { element.currentTime = pendingSeek.seconds; pendingMediaSeekRef.current = undefined; }
      catch { return; }
    }
    const current = Math.max(0, Math.min(currentVideo.canonical_frame_count - 1, Math.round(element.currentTime * currentVideo.canonical_fps)));
    const loopEnd = trimPreviewing ? trimRange?.end : selectedSegment?.end_frame;
    const loopStart = trimPreviewing ? trimRange?.start : selectedSegment?.start_frame;
    if (loop && loopEnd !== undefined && loopStart !== undefined && current >= loopEnd && !element.ended) {
      seek(loopStart); void element.play(); return;
    }
    setFrame(current);
    setPlaying(!element.paused && !element.ended);
  }

  // ── Segment helpers ─────────────────────────────────────────────────────────

  async function saveSegment(autosave = false) {
    if (!active || selectedTrack === undefined) return;
    const videoId = active.video_id;
    const segmentAtSave = selectedSegment;
    const attemptedDraft = segmentAtSave
      ? `${videoId}:${segmentAtSave.segment_id}:${selectedTrack}:${start}:${end}:${label}:${revision}`
      : undefined;
    if (!autosave) setAutosaveFailedDraft(undefined);
    savingRequestCountRef.current += 1;
    setSaving(true);
    setError('');
    try {
      const result = await saveVideoSegment(projectId, videoId, {
        track_id: selectedTrack, start_frame: start, end_frame: end, label, expected_revision: revision,
      }, selectedSegment?.segment_id);
      if (activeIdRef.current === videoId) {
        setRevision(result.revision);
        setSegments((current) => [
          ...current.filter((item) => item.segment_id !== result.segment.segment_id),
          result.segment,
        ].sort((a, b) => a.start_frame - b.start_frame));
        setSelectedSegment((current) => {
          if (!segmentAtSave) return result.segment;
          return current?.segment_id === segmentAtSave.segment_id ? result.segment : current;
        });
        setCreatingSegment(false);
        setAutosaveFailedDraft(undefined);
        if (!autosave) setMessage('Segment saved.');
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        if (attemptedDraft) setAutosaveFailedDraft(attemptedDraft);
        setError(`${autosave ? 'Autosave' : 'Save'} failed. ${readableError(reason)}`);
      }
    } finally {
      savingRequestCountRef.current = Math.max(0, savingRequestCountRef.current - 1);
      setSaving(savingRequestCountRef.current > 0);
    }
  }

  async function removeSegment() {
    if (!active || !selectedSegment) return;
    const videoId = active.video_id;
    const deletingSegment = selectedSegment;
    if (deletingSegmentIdRef.current === deletingSegment.segment_id) return;
    deletingSegmentIdRef.current = deletingSegment.segment_id;
    setSegments((current) => current.filter((item) => item.segment_id !== deletingSegment.segment_id));
    setSelectedSegment(undefined);
    setSelectedSegmentIds((current) => {
      const next = new Set(current);
      next.delete(deletingSegment.segment_id);
      return next;
    });
    setCreatingSegment(false);
    setMessage('Segment deleted.');
    savingRequestCountRef.current += 1;
    setSaving(true);
    try {
      const result = await deleteVideoSegment(projectId, videoId, deletingSegment.segment_id, revision);
      if (activeIdRef.current === videoId) {
        setRevision(result.revision);
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        setSegments((current) => current.some((item) => item.segment_id === deletingSegment.segment_id)
          ? current
          : [...current, deletingSegment].sort((left, right) => left.start_frame - right.start_frame));
        setError(`Could not delete the segment. ${readableError(reason)}`);
      }
    } finally {
      if (deletingSegmentIdRef.current === deletingSegment.segment_id) {
        deletingSegmentIdRef.current = undefined;
      }
      savingRequestCountRef.current = Math.max(0, savingRequestCountRef.current - 1);
      setSaving(savingRequestCountRef.current > 0);
    }
  }

  async function removeSelectedSegments() {
    if (!active) return;
    const ids = selectedSegmentIds.size > 0
      ? [...selectedSegmentIds]
      : selectedSegment ? [selectedSegment.segment_id] : [];
    if (ids.length === 0) return;
    if (ids.length > 1 && !window.confirm(`Delete ${ids.length} selected segments?`)) return;
    const videoId = active.video_id;
    const deleted = segments.filter((segment) => ids.includes(segment.segment_id));
    let nextRevision = revision;
    setSegments((current) => current.filter((segment) => !ids.includes(segment.segment_id)));
    setSelectedSegment(undefined);
    setSelectedSegmentIds(new Set());
    try {
      for (const segment of deleted) {
        const result = await deleteVideoSegment(projectId, videoId, segment.segment_id, nextRevision);
        nextRevision = result.revision;
      }
      if (activeIdRef.current === videoId) {
        setRevision(nextRevision);
        setMessage(`${deleted.length} segment${deleted.length === 1 ? '' : 's'} deleted.`);
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        await refreshSegments();
        setError(`Could not delete the selected segments. ${readableError(reason)}`);
      }
    }
  }

  async function removeSelectedTracks(trackIds?: number[]) {
    if (!active) return;
    const ids = trackIds ?? (mergeTrackIds.size > 0 ? [...mergeTrackIds] : selectedTrack === undefined ? [] : [selectedTrack]);
    if (ids.length === 0) return;
    if (!window.confirm(`Delete ${ids.length} worker${ids.length === 1 ? '' : 's'} and all of their segments?`)) return;
    try {
      await Promise.all(ids.map((trackId) => deleteVideoTrack(projectId, active.video_id, trackId)));
      setMergeTrackIds(new Set());
      setSelectedTrack(undefined);
      setSelectedSegment(undefined);
      setSelectedSegmentIds(new Set());
      await reloadActive();
      setMessage(`${ids.length} worker${ids.length === 1 ? '' : 's'} deleted.`);
    } catch (reason) {
      setError(`Could not delete the selected workers. ${readableError(reason)}`);
    }
  }

  async function mergeSelectedSegments() {
    if (!active || !canMergeSelectedSegments) return;
    const videoId = active.video_id;
    const selected = segments
      .filter((segment) => selectedSegmentIds.has(segment.segment_id))
      .sort((left, right) => left.start_frame - right.start_frame);
    try {
      const result = await mergeVideoSegments(
        projectId, videoId, selected.map((segment) => segment.segment_id), revision,
      );
      if (activeIdRef.current !== videoId) return;
      setRevision(result.revision);
      setSegments((current) => [
        ...current.filter((segment) => !selectedSegmentIds.has(segment.segment_id)),
        result.segment,
      ].sort((left, right) => left.start_frame - right.start_frame));
      setSelectedSegment(result.segment);
      setSelectedSegmentIds(new Set());
      setStart(result.segment.start_frame);
      setEnd(result.segment.end_frame);
      setLabel(result.segment.label);
      setMessage(`${selected.length} adjacent ${result.segment.label} segments merged.`);
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        setError(`Could not merge the selected segments. ${readableError(reason)}`);
      }
    }
  }

  async function expandSegment(segment: VideoSegment) {
    if (!active) return;
    const videoId = active.video_id;
    try {
      const result = await extendVideoSegment(projectId, videoId, segment.segment_id, revision);
      if (activeIdRef.current !== videoId) return;
      setRevision(result.revision);
      setSegments((current) => current.map((item) =>
        item.segment_id === result.segment.segment_id ? result.segment : item,
      ).sort((left, right) => left.start_frame - right.start_frame));
      if (selectedSegment?.segment_id === segment.segment_id) {
        setSelectedSegment(result.segment);
        setStart(result.segment.start_frame);
        setEnd(result.segment.end_frame);
      }
      if (result.segment.start_frame === segment.start_frame && result.segment.end_frame === segment.end_frame) {
        setMessage('No surrounding gap to expand into.');
      } else {
        setMessage('Segment expanded into surrounding gaps.');
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    }
  }

  async function history(action: 'undo' | 'redo') {
    if (!active) return;
    const videoId = active.video_id;
    try {
      const result = await videoHistoryAction(projectId, videoId, action, revision);
      const rows = await getVideoSegments(projectId, videoId);
      if (activeIdRef.current !== videoId) return;
      setRevision(result.revision);
      setSegments(rows.segments);
        setSelectedSegment(undefined);
      setCreatingSegment(false);
      setHistoryUnavailable(null);
      setMessage(action === 'undo' ? 'Undone.' : 'Redone.');
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        const msg = readableError(reason);
        if (/nothing to undo/i.test(msg)) {
          setHistoryUnavailable('undo');
          setMessage('No earlier annotation changes are available to undo.');
        } else if (/nothing to redo/i.test(msg)) {
          setHistoryUnavailable('redo');
          setMessage('No undone annotation changes are available to redo.');
        } else {
          setError(msg);
        }
      }
    }
  }

  /**
   * #3 — Fill all uncovered frame ranges for the given track with fillClass.
   * Creates one segment per gap in series (sequential revisions).
   */
  async function fillTrackGaps(track: VideoTrack) {
    if (!active) return;
    const videoId = active.video_id;
    const trackSegments = segments.filter((s) => s.track_id === track.track_id);
    const gaps = uncoveredRanges(trackSegments, track.start_frame, track.end_frame);
    if (gaps.length === 0) { setMessage('No unlabeled gaps found for this track.'); return; }
    let currentRevision = revision;
    try {
      for (const gap of gaps) {
        const result = await saveVideoSegment(projectId, videoId, {
          track_id: track.track_id, start_frame: gap.start, end_frame: gap.end,
          label: fillClass, expected_revision: currentRevision,
        });
        currentRevision = result.revision;
        if (activeIdRef.current !== videoId) return;
        setSegments((current) => [
          ...current.filter((item) => item.segment_id !== result.segment.segment_id),
          result.segment,
        ].sort((a, b) => a.start_frame - b.start_frame));
      }
      setRevision(currentRevision);
      setMessage(`Filled ${gaps.length} gap(s) with "${fillClass}".`);
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(`Fill gaps failed. ${readableError(reason)}`);
    }
  }

  async function toggleSegmentInclusion() {
    if (!active || !selectedSegment) return;
    const videoId = active.video_id;
    try {
      const include = !selectedSegment.include_in_export;
      const result = await setVideoSegmentInclusion(projectId, videoId, selectedSegment.segment_id, include, revision, include ? undefined : 'manual_exclusion');
      if (activeIdRef.current !== videoId) return;
      setRevision(result.revision);
      setSegments((rows) => rows.map((item) => item.segment_id === result.segment.segment_id ? result.segment : item));
      setSelectedSegment(result.segment);
      setMessage(include ? 'Segment included in export.' : 'Segment excluded from export.');
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    }
  }

  /** Approve the current video, or revoke its approval when already approved. */
  async function handleApproveToggle() {
    if (!active) return;
    const videoId = active.video_id;
    try {
      if (active.is_approved) {
        const updated = await unapproveVideo(projectId, videoId);
        setVideos((current) => {
          const next = current.map((item) => item.video_id === videoId ? { ...item, ...updated } : item);
          videosRef.current = next;
          return next;
        });
        setActive((current) => current?.video_id === videoId ? { ...current, ...updated } : current);
        setMessage('Approval revoked.');
      } else {
        const updated = await approveVideo(projectId, videoId);
        setVideos((current) => {
          const next = current.map((item) => item.video_id === videoId ? { ...item, ...updated } : item);
          videosRef.current = next;
          return next;
        });
        setActive((current) => current?.video_id === videoId ? { ...current, ...updated } : current);
        setMessage('Video approved.');
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    }
  }

  async function refreshSegments(video = active) {
    if (!video) return;
    const rows = await getVideoSegments(projectId, video.video_id);
    if (activeIdRef.current !== video.video_id) return;
    setSegments(rows.segments);
    setRevision(rows.revision);
    setSelectedSegment(undefined);
    setCreatingSegment(false);
  }

  async function reloadActive(video = active) {
    if (!video) return;
    await loadActive(video);
  }

  function chooseSegment(segment: VideoSegment) {
    setSelectionScope('segment');
    if (selectedSegment?.segment_id === segment.segment_id) {
      setSelectedSegment(undefined);
      setCreatingSegment(false);
      setMergeSegmentId(undefined);
      return;
    }
    setSelectedSegment(segment);
    setCreatingSegment(false);
    setMergeSegmentId(undefined);
    setSelectedTrack(segment.track_id);
    setStart(segment.start_frame);
    setEnd(segment.end_frame);
    setLabel(segment.label);
    seek(segment.start_frame);
    setTab('annotate');
  }

  function chooseTrack(trackId: number) {
    setSelectionScope('worker');
    setSelectedTrack(trackId);
    setSelectedSegment(undefined);
    setCreatingSegment(false);
    setMergeSegmentId(undefined);
  }

  function chooseCreateSegment() {
    const track = tracks.find((item) => item.track_id === selectedTrack);
    if (!track) return;
    if (creatingSegment) {
      setCreatingSegment(false);
      return;
    }
    const initialFrame = Math.max(track.start_frame, Math.min(frame, track.end_frame));
    setSelectedSegment(undefined);
    setCreatingSegment(true);
    setStart(initialFrame);
    setEnd(initialFrame);
    setLabel('others');
    setTab('annotate');
  }

  async function generateSuggestions() {
    if (!active || source === 'Off') return;
    const videoId = active.video_id;
    const mode: ProcessMode = source === 'AI' ? 'Model' : 'Threshold';
    const overwriteLabels = segments.length > 0;
    if (overwriteLabels && !window.confirm(
      'This video already has labels. Generating new suggestions will replace all current labels. Continue?',
    )) return;
    setProcessingRequests((current) => new Set(current).add(videoId));
    setError('');
    try {
      const rows = overwriteLabels
        ? await processVideo(projectId, videoId, mode, true)
        : await processVideo(projectId, videoId, mode);
      setJobs((current) => upsertJobRows(current, rows));
      beginProcessingBatch([videoId]);
      if (activeIdRef.current === videoId) {
        setMessage(`${source} suggestion generation started.`);
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(`Processing could not start. ${readableError(reason)}`);
    } finally {
      setProcessingRequests((current) => { const next = new Set(current); next.delete(videoId); return next; });
    }
  }

  function toggleVideoSelection(video: VideoItem) {
    setSelectionScope('video');
    setSelectedVideoIds((current) => {
      const next = new Set(current);
      if (next.has(video.video_id)) next.delete(video.video_id); else next.add(video.video_id);
      return next;
    });
  }

  function requestVideoDelete(video: VideoItem) {
    setPendingDeleteIds([video.video_id]);
  }

  async function confirmDeleteVideos() {
    if (pendingDeleteIds.length === 0 || deletingIds.size > 0) return;
    const targets = videos.filter((video) => pendingDeleteIds.includes(video.video_id));
    const activeTargetIndex = targets.findIndex((video) => video.video_id === activeIdRef.current);
    const deletingActive = activeTargetIndex >= 0;
    const activeIndex = videos.findIndex((video) => video.video_id === activeIdRef.current);
    const removed = new Set(targets.map((video) => video.video_id));
    setDeletingIds(new Set(targets.map((video) => video.video_id)));
    setError('');
    // Hide the deleted videos from the batch immediately. The backend deletion
    // transaction cascades their queued and running job records as well.
    setJobs((current) => current.filter((job) => !job.video_id || !removed.has(job.video_id)));
    setProcessingBatchVideoIds((current) => new Set(
      [...current].filter((videoId) => !removed.has(videoId)),
    ));
    if (deletingActive) {
      player.current?.pause();
      setPlaying(false);
      setOverlay(undefined);
      setActive(null);
      await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    }
    try {
      await Promise.all(targets.map((video) => deleteImportedVideo(projectId, video.video_id)));
      const remaining = videos.filter((item) => !removed.has(item.video_id));
      const next = remaining[Math.min(activeIndex, Math.max(0, remaining.length - 1))] ?? null;
      videosRef.current = remaining;
      setVideos(remaining);
      setJobs((current) => current.filter((job) => !job.video_id || !removed.has(job.video_id)));
      if (deletingActive) setActive(next);
      setSelectedVideoIds(new Set());
      setPendingDeleteIds([]);
      setMessage(`${targets.length} video${targets.length === 1 ? '' : 's'} deleted.`);
    } catch (reason) {
      void refreshShell();
      if (deletingActive) setActive(videos[activeIndex] ?? null);
      setError(`Could not delete the selected videos. ${readableError(reason)}`);
    } finally {
      setDeletingIds(new Set());
    }
  }

  async function handleImport(files: File[]) {
    if (files.length === 0) return;
    setError('');
    try {
      const mode: ProcessMode = source === 'AI' ? 'Model' : 'Threshold';
      const rows = await importVideos(projectId, files, mode);
      setVideos((current) => {
        const existing = new Set(current.map((item) => item.video_id));
        const next = [...current, ...rows.filter((item) => !existing.has(item.video_id))];
        videosRef.current = next;
        return next;
      });
      if (!active && rows[0]) setActive(rows[0]);
      beginProcessingBatch(rows.map((video) => video.video_id));
      setMessage(`${rows.length} video${rows.length === 1 ? '' : 's'} imported and queued for processing.`);
      await refreshShell();
    } catch (reason) {
      setError(`Import failed. ${readableError(reason)}`);
    }
  }

  async function handleRenameVideos(prefix: string) {
    if (!window.confirm(`Rename all ${videos.length} videos to ${prefix}_00001, ${prefix}_00002, and so on?`)) {
      return;
    }
    try {
      const rows = await renameVideos(projectId, prefix);
      videosRef.current = rows;
      setVideos(rows);
      setActive((current) => current
        ? rows.find((video) => video.video_id === current.video_id) ?? null
        : null);
      setMessage(`${rows.length} videos renamed with the prefix "${prefix}".`);
    } catch (reason) {
      setError(`Could not rename videos. ${readableError(reason)}`);
    }
  }

  /**
   * #8 — Multi-track merge: merge all checked tracks into the first selected one.
   */
  async function handleMergeSelectedTracks() {
    if (!active || mergeTrackIds.size < 2) return;
    const videoId = active.video_id;
    const trackIdList = [...mergeTrackIds].sort((a, b) => a - b);
    try {
      await mergeMultipleVideoTracks(projectId, videoId, trackIdList);
      setMergeTrackIds(new Set());
      await reloadActive();
      setMessage(`Merged ${trackIdList.length} workers into Worker ${trackIdList[0]}.`);
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(`Track merge failed. ${readableError(reason)}`);
    }
  }

  async function splitWorker(track: VideoTrack) {
    if (!active) return;
    const videoId = active.video_id;
    try {
      await splitVideoTrack(projectId, videoId, track.track_id, frame);
      if (activeIdRef.current !== videoId) return;
      await reloadActive();
      setMessage(`Worker ${track.track_id} split at frame ${frame}.`);
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        setError(`Could not split Worker ${track.track_id}. ${readableError(reason)}`);
      }
    }
  }

  async function toggleWorkerInclusion(track: VideoTrack) {
    if (!active) return;
    const videoId = active.video_id;
    const include = !track.include_in_export;
    try {
      await setVideoTrackInclusion(
        projectId, videoId, track.track_id, include,
        include ? undefined : 'manual_exclusion',
      );
      if (activeIdRef.current !== videoId) return;
      await reloadActive();
      setMessage(include ? `Worker ${track.track_id} included in export.` : `Worker ${track.track_id} excluded from export.`);
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        setError(`Could not update Worker ${track.track_id}. ${readableError(reason)}`);
      }
    }
  }

  async function splitSelectedSegment(segment: VideoSegment) {
    if (!active) return;
    const videoId = active.video_id;
    try {
      await splitVideoSegment(projectId, videoId, segment.segment_id, frame, revision);
      if (activeIdRef.current !== videoId) return;
      await refreshSegments();
      setMessage(`Segment split at frame ${frame}.`);
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        setError(`Could not split the segment. ${readableError(reason)}`);
      }
    }
  }

  /**
   * #11 — Commits one locally previewed timeline-boundary resize on release.
   */
  async function handleSegmentResize(segmentId: string, newStart: number, newEnd: number) {
    const seg = segments.find((s) => s.segment_id === segmentId);
    if (!seg || !active) return;
    const videoId = active.video_id;
    const optimisticSegment = { ...seg, start_frame: newStart, end_frame: newEnd };
    setSegments((current) => current.map((item) =>
      item.segment_id === segmentId ? optimisticSegment : item,
    ).sort((left, right) => left.start_frame - right.start_frame));
    if (selectedSegment?.segment_id === segmentId) {
      setSelectedSegment(optimisticSegment);
      setStart(newStart);
      setEnd(newEnd);
    }
    try {
      const result = await saveVideoSegment(projectId, videoId, {
        track_id: seg.track_id, start_frame: newStart, end_frame: newEnd,
        label: seg.label, expected_revision: revision,
      }, segmentId);
      if (activeIdRef.current !== videoId) return;
      setRevision(result.revision);
      setSegments((current) => [
        ...current.filter((item) => item.segment_id !== result.segment.segment_id),
        result.segment,
      ].sort((a, b) => a.start_frame - b.start_frame));
      if (selectedSegment?.segment_id === segmentId) {
        setSelectedSegment(result.segment);
        setStart(result.segment.start_frame);
        setEnd(result.segment.end_frame);
      }
      setMessage('Segment boundary updated.');
    } catch {
      if (activeIdRef.current !== videoId) return;
      setSegments((current) => current.map((item) => (
        item.segment_id === segmentId
        && item.start_frame === newStart
        && item.end_frame === newEnd
          ? seg
          : item
      )).sort((left, right) => left.start_frame - right.start_frame));
      if (selectedSegment?.segment_id === segmentId) {
        setSelectedSegment(seg);
        setStart(seg.start_frame);
        setEnd(seg.end_frame);
      }
      setError('Could not save the segment boundary. The last valid range was restored.');
    }
  }

  // ── Derived values for effects below ─────────────────────────────────────

  const activeProcessing = Boolean(active && jobs.some(
    (job) => job.video_id === active.video_id && ACTIVE_JOB_STATUSES.has(job.status),
  ));

  // ── Processing-complete refresh ─────────────────────────────────────────────

  useEffect(() => {
    const videoId = active?.video_id;
    const previous = processingTransitionRef.current;
    processingTransitionRef.current = { videoId, active: activeProcessing };
    if (!videoId || activeProcessing || previous.videoId !== videoId || !previous.active) return;

    overlayCacheRef.current = createOverlayCache(videoId);
    setOverlay(undefined);
    setOverlayCacheRevision((c) => c + 1);

    void refreshActiveDetails(videoId);
  }, [active?.video_id, activeProcessing, refreshActiveDetails]);

  // ── Autosave ────────────────────────────────────────────────────────────────

  const draftDirty = Boolean(
    selectedSegment && (
      selectedSegment.track_id !== selectedTrack
      || selectedSegment.start_frame !== start
      || selectedSegment.end_frame !== end
      || selectedSegment.label !== label
    ),
  );
  const draftSignature = selectedSegment && active
    ? `${active.video_id}:${selectedSegment.segment_id}:${selectedTrack}:${start}:${end}:${label}:${revision}`
    : undefined;

  useEffect(() => {
    if (!draftDirty || !draftSignature || saving || autosaveFailedDraft === draftSignature) return undefined;
    const timer = window.setTimeout(() => void saveSegment(true), 700);
    return () => window.clearTimeout(timer);
  }, [autosaveFailedDraft, draftDirty, draftSignature, saving]);

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────

  useEffect(() => {
    function key(event: KeyboardEvent) {
      if (helpOpen || pendingDeleteIds.length > 0) return;
      const target = event.target;
      const editingText = target instanceof HTMLElement && (
        target.isContentEditable
        || target.closest('input, textarea, select, [contenteditable="true"]')
      );
      if (editingText) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); if (trimMode) undoTrim(); else void history('undo'); return; }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') { event.preventDefault(); if (trimMode) redoTrim(); else void history('redo'); return; }
      if (event.key === 'Escape' && selectedSegment) {
        event.preventDefault();
        setSelectedSegment(undefined);
        setCreatingSegment(false);
        setMergeSegmentId(undefined);
        return;
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectionScope === 'segment' && (selectedSegmentIds.size > 0 || selectedSegment)) {
        event.preventDefault();
        void removeSelectedSegments();
        return;
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectionScope === 'worker' && (mergeTrackIds.size > 0 || selectedTrack !== undefined)) {
        event.preventDefault();
        void removeSelectedTracks();
        return;
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && selectionScope === 'video' && selectedVideoIds.size > 0) {
        event.preventDefault();
        setPendingDeleteIds([...selectedVideoIds]);
        return;
      }
      if (target instanceof HTMLElement && target.closest('button, a')) return;
      const actions: Record<string, () => void> = {
        ' ': () => void togglePlay(),
        ArrowLeft: () => seek(frame - (event.shiftKey ? 10 : 1)),
        ArrowRight: () => seek(frame + (event.shiftKey ? 10 : 1)),
        i: () => setStart(frame),
        o: () => setEnd(frame),
        '1': () => setLabel('others'),
        '2': () => setLabel('running'),
        '3': () => setLabel('falling'),
        t: () => setSource('Threshold'),
        m: () => modelAvailable && setSource('AI'),
        s: () => setSource('Off'),
        x: () => void toggleSegmentInclusion(),
        Enter: () => void saveSegment(),
      };
      const action = actions[event.key] ?? actions[event.key.toLowerCase()];
      if (action) { event.preventDefault(); action(); }
    }
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  });

  // ── Derived values ──────────────────────────────────────────────────────────

  const modelAvailable = processingOptions.model_available;
  const activeTrack = tracks.find((item) => item.track_id === selectedTrack);
  const selectedVideoIndex = videos.findIndex((item) => item.video_id === active?.video_id);
  const activeSegments = segments.filter((item) => selectedTrack === undefined || item.track_id === selectedTrack);
  const detailLabelCounts = segments.reduce<Record<HumanVideoLabel, number>>((counts, segment) => {
    counts[segment.label] += 1;
    return counts;
  }, { others: 0, running: 0, falling: 0 });
  const coveredFrames = active ? countCoveredFrames(segments, active.canonical_frame_count) : 0;
  const annotationCoverage = active && active.canonical_frame_count > 0
    ? Math.round((coveredFrames / active.canonical_frame_count) * 100)
    : 0;
  const generatedSegmentCount = segments.filter((segment) => segment.source_type !== 'manual').length;
  const activeJob = active ? jobs.find((job) => job.video_id === active.video_id && ACTIVE_JOB_STATUSES.has(job.status)) : undefined;
  const selectedSegmentsForMerge = segments
    .filter((segment) => selectedSegmentIds.has(segment.segment_id))
    .sort((left, right) => left.start_frame - right.start_frame);
  const canMergeSelectedSegments = selectedSegmentsForMerge.length >= 2
    && new Set(selectedSegmentsForMerge.map((segment) => `${segment.track_id}:${segment.label}`)).size === 1
    && selectedSegmentsForMerge.every((segment, index) => index === 0
      || segment.start_frame <= selectedSegmentsForMerge[index - 1].end_frame + 1);
  const activeProcessingVideoIds = new Set(
    jobs.filter((job) => ACTIVE_JOB_STATUSES.has(job.status) && job.video_id).map((job) => job.video_id as string),
  );
  const processingBatchIds = processingBatchVideoIds.size > 0
    ? processingBatchVideoIds : activeProcessingVideoIds;
  const processingBatchRemaining = [...processingBatchIds]
    .filter((videoId) => activeProcessingVideoIds.has(videoId)).length;
  const approvedVideoCount = videos.filter((video) => Boolean(video.is_approved)).length;
  const videosRemainingApproval = videos.length - approvedVideoCount;
  const approvalProgress = videos.length > 0 ? (approvedVideoCount / videos.length) * 100 : 0;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="workspace-shell h-screen bg-background text-on-background flex flex-col overflow-hidden">

      {/* ── Navbar ── */}
      <header className="h-toolbar-height bg-surface-container border-b border-outline-variant flex items-center px-gutter justify-between shrink-0 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button type="button" aria-label="Toggle video browser" onClick={() => setLeftOpen(!leftOpen)} className="toolbar-icon"><PanelLeft size={18} /></button>
          <Link to="/" className="font-headline-sm font-bold text-primary">Home</Link>
          <span className="text-on-surface-variant">/</span>
          <Link to="/behavior" className="text-on-surface hover:text-primary">Behavior</Link>
          <span className="text-on-surface-variant">/</span>
          <Link to="/video" className="text-on-surface hover:text-primary">Labeling</Link>
          <span className="hidden md:inline text-on-surface-variant">/</span>
          <span className="hidden md:inline truncate max-w-48">{project?.name ?? 'Loading…'}</span>
          {active && <><span className="hidden xl:inline text-on-surface-variant">/</span><span className="hidden xl:inline truncate max-w-48">{active.filename}</span></>}
        </div>

        <div className="hidden lg:flex items-center gap-1">
          <button type="button" aria-label="Undo" disabled={trimMode ? trimUndo.length === 0 : historyUnavailable === 'undo'} title="Undo" onClick={() => trimMode ? undoTrim() : void history('undo')} className="toolbar-icon disabled:opacity-30"><Undo2 size={17} /></button>
          <button type="button" aria-label="Redo" disabled={trimMode ? trimRedo.length === 0 : historyUnavailable === 'redo'} title="Redo" onClick={() => trimMode ? redoTrim() : void history('redo')} className="toolbar-icon disabled:opacity-30"><Redo2 size={17} /></button>
          <button type="button" title="Previous video" disabled={selectedVideoIndex <= 0} onClick={() => setActive(videos[selectedVideoIndex - 1])} className="toolbar-icon disabled:opacity-30"><ChevronLeft size={17} /></button>
          <button type="button" title="Next video" disabled={selectedVideoIndex < 0 || selectedVideoIndex >= videos.length - 1} onClick={() => setActive(videos[selectedVideoIndex + 1])} className="toolbar-icon disabled:opacity-30"><ChevronRight size={17} /></button>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="hidden xl:flex font-label text-label-sm text-on-surface-variant gap-1 items-center">
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            {saving ? 'Saving…' : draftDirty ? 'Unsaved changes' : 'Saved'}
          </span>

          {/* #5 — Source selector compact dropdown in navbar */}
          <button type="button" onClick={() => setHelpOpen(true)} className="h-8 px-2 border border-outline-variant rounded font-label text-label-sm flex items-center gap-1"><HelpCircle size={15} />Help</button>

          <button type="button" aria-label="Toggle inspector" onClick={() => setRightOpen(!rightOpen)} className="toolbar-icon"><PanelRight size={18} /></button>
        </div>
      </header>

      {/* ── Status bar ── */}
      {(error || message) && (
        <div className={`status-message px-4 py-2 text-label-sm border-b ${error ? 'bg-error-container/40 border-error/40 text-error' : 'bg-primary/10 border-primary/30'}`} role={error ? 'alert' : 'status'}>
          {error || message}
          <button type="button" aria-label="Dismiss message" className="float-right" onClick={() => { setError(''); setMessage(''); }}>×</button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">

        {/* ── Left sidebar ── */}
        {leftOpen && (
          <>
          <aside className="panel-rail-left bg-surface-container border-r border-outline-variant flex flex-col shrink-0" style={{ width: leftSidebarWidth }}>
            <VideoBrowser
              videos={videos}
              jobs={jobs}
              selectedId={active?.video_id}
              selectedIds={selectedVideoIds}
              deletingIds={deletingIds}
              onSelect={setActive}
              onToggleSelection={toggleVideoSelection}
              onImport={(files) => void handleImport(files)}
              onExport={() => setExportOpen(true)}
              onRename={handleRenameVideos}
              onDelete={requestVideoDelete}
              onDeleteSelected={() => setPendingDeleteIds([...selectedVideoIds])}
            />
            <ProcessingQueue
              jobs={jobs}
              remainingVideos={processingBatchRemaining}
              totalVideos={processingBatchIds.size}
            />
          </aside>
          <div
            role="separator"
            aria-label="Resize video browser"
            aria-orientation="vertical"
            className="w-1 shrink-0 cursor-col-resize bg-outline-variant/60 hover:bg-primary transition-colors touch-none"
            onPointerDown={(event) => startSidebarResize('left', event)}
            onPointerMove={resizeSidebar}
            onPointerUp={finishSidebarResize}
            onPointerCancel={finishSidebarResize}
          />
          </>
        )}

        {/* ── Main workspace ── */}
        <main className="stage-ambient technical-grid flex-1 min-w-0 flex flex-col bg-surface-container-lowest" ref={containerRef}>
          {!active ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 text-on-surface-variant"><div className="empty-state-illustration" aria-hidden="true" /><p>Import or select a video to begin.</p></div>
          ) : (
            <>
              <div className="flex-1 min-h-[220px]">
                <PoseVideoPlayer
                  ref={player}
                  projectId={projectId}
                  video={active}
                  overlay={overlay}
                  selectedTrack={selectedTrack}
                  selectedOnly={selectedOnly}
                  showBoxes={showBoxes}
                  currentSegments={segments}
                  currentFrame={frame}
                  features={features}
                  playing={playing}
                  onSelectTrack={chooseTrack}
                  onTimeUpdate={synchronizePlayer}
                  onSeek={seek}
                  onPlayPause={() => void togglePlay()}
                  onMediaError={() => setError('This video format is unsupported or the media file is damaged. Annotations and pose data are still available.')}
                  playbackRate={playbackRate}
                />
              </div>

              {/* Player controls */}
              <div className="h-12 bg-surface-container border-t border-outline-variant flex items-center justify-center gap-2 px-3">
                <button type="button" title="Back 10 frames" onClick={() => seek(frame - 10)} className="toolbar-icon"><SkipBack size={17} /></button>
                <button type="button" title={playing ? 'Pause' : 'Play'} onClick={() => void togglePlay()} className="w-8 h-8 bg-primary-container text-on-primary-container rounded flex items-center justify-center">
                  {playing ? <Pause size={17} /> : <Play size={17} />}
                </button>
                <button type="button" title="Forward 10 frames" onClick={() => seek(frame + 10)} className="toolbar-icon"><SkipForward size={17} /></button>
                <input aria-label="Current frame" type="number" min={0} max={active.canonical_frame_count - 1} value={frame} onChange={(e) => seek(Number(e.target.value))} className="w-24 h-8 bg-surface-container-lowest border border-outline-variant rounded px-2 font-label text-label-sm" />
                <span className="font-label text-label-sm text-on-surface-variant">/ {active.canonical_frame_count - 1}</span>
                <select aria-label="Playback speed" value={playbackRate} onChange={(e) => setPlaybackRate(Number(e.target.value))} className="h-8 bg-surface-container-lowest border border-outline-variant rounded px-2">
                  <option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1">1×</option><option value="2">2×</option>
                </select>
                <button type="button" aria-label="Loop" title={selectedSegment ? 'Loop selected segment' : 'Loop full video'} onClick={() => setLoop(!loop)} className={`toolbar-icon ${loop ? 'border-primary text-primary' : 'border-outline-variant'}`}>
                  <Repeat2 size={17} />
                </button>
                {/* #13 — single toggle for bbox + skeleton */}
                <button type="button" title={showBoxes ? 'Hide overlay' : 'Show overlay'} onClick={() => setShowBoxes(!showBoxes)} className="toolbar-icon">
                  {showBoxes ? <Eye size={16} /> : <EyeOff size={16} />}
                </button>
                <button type="button" aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} onClick={() => void toggleFullscreen()} className="toolbar-icon">
                  {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </button>
                <button type="button" aria-label="Toggle video trim mode" title="Video trim mode" onClick={() => { setTrimMode((enabled) => !enabled); setTrimPreviewing(false); }} className={`toolbar-icon ${trimMode ? 'border-primary bg-primary/10 text-primary' : ''}`}>
                  <Scissors size={16} />
                </button>
                <SuggestionModeButton
                  compact
                  source={source}
                  disabled={!active}
                  generating={Boolean(active && processingRequests.has(active.video_id)) || activeProcessing}
                  modelAvailable={modelAvailable}
                  modelUnavailableReason={processingOptions.model_message ?? 'Model suggestions are unavailable.'}
                  onSourceChange={setSource}
                  onGenerate={() => void generateSuggestions()}
                />
              </div>

              {trimMode && trimRange && (
                <div className="px-3 py-2 bg-surface-container border-t border-primary/30 border-l-2 border-l-primary flex flex-wrap items-center gap-2 text-label-sm">
                  <span className="font-label font-medium text-primary">Video trim</span>
                  <span className="text-on-surface-variant">Keep frames {trimRange.start}–{trimRange.end} ({trimRange.end - trimRange.start + 1} frames)</span>
                  <button type="button" className="panel-button" onClick={previewTrim}>Preview range</button>
                  <button type="button" className="panel-button" onClick={() => updateTrimRange({ start: 0, end: active.canonical_frame_count - 1 })}>Reset</button>
                  <button type="button" className="panel-button bg-primary-container text-on-primary-container border-primary-container hover:bg-primary" disabled={trimSaving || trimRange.end - trimRange.start + 1 < 60} onClick={() => void saveTrim('copy')}>{trimSaving ? 'Saving…' : 'Save copy'}</button>
                  <button type="button" className="panel-button bg-error-container text-on-error-container border-error-container hover:brightness-110" disabled={trimSaving || trimRange.end - trimRange.start + 1 < 60} onClick={() => void saveTrim('replace')}>{trimSaving ? 'Saving…' : 'Replace video'}</button>
                  {trimRange.end - trimRange.start + 1 < 60 && <span className="text-[10px] text-error">Select at least 60 frames to save a video.</span>}
                  <span className="text-[10px] text-on-surface-variant">Saving re-encodes the selected frames. Replacing clears frame-based labels; a copy preserves the original video.</span>
                </div>
              )}

              {trimMode && trimRange ? (
                <TrimTimeline
                  frameCount={active.canonical_frame_count}
                  currentFrame={frame}
                  mediaUrl={videoMediaUrl(projectId, active.video_id)}
                  range={trimRange}
                  minimumRange={60}
                  onFrame={seek}
                  onRangeCommit={updateTrimRange}
                />
              ) : (
                <VideoTimeline
                  frameCount={active.canonical_frame_count}
                  currentFrame={frame}
                  segments={segments}
                  tracks={tracks}
                  selectedSegment={selectedSegment?.segment_id}
                  onFrame={seek}
                  onSegment={chooseSegment}
                  onSegmentResize={handleSegmentResize}
                />
              )}
            </>
          )}
        </main>

        {/* ── Right sidebar ── */}
        {rightOpen && (
          <>
          <div
            role="separator"
            aria-label="Resize inspector"
            aria-orientation="vertical"
            className="w-1 shrink-0 cursor-col-resize bg-outline-variant/60 hover:bg-primary transition-colors touch-none"
            onPointerDown={(event) => startSidebarResize('right', event)}
            onPointerMove={resizeSidebar}
            onPointerUp={finishSidebarResize}
            onPointerCancel={finishSidebarResize}
          />
          <aside className="panel-rail-right bg-surface-container border-l border-outline-variant flex flex-col shrink-0 min-h-0" style={{ width: rightSidebarWidth }}>
            {/* Tab header — #4: only Annotate and Details */}
            <div className="grid grid-cols-2 border-b border-outline-variant shrink-0">
              {(['annotate', 'details'] as RightTab[]).map((name) => (
                <button type="button" key={name} onClick={() => setTab(name)} className={`h-10 capitalize font-label text-label-sm border-b-2 ${tab === name ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant'}`}>{name}</button>
              ))}
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto">

              {/* ── Annotate tab ── */}
              {tab === 'annotate' && (
                <div className="p-3 space-y-4">

                  {/* ── Worker track cards — #12: inline actions, #8: checkbox multi-select ── */}
                  <section>
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-label text-label-caps uppercase text-on-surface-variant">Workers</p>
                      {/* Multi-merge button (#8) */}
                      {mergeTrackIds.size >= 2 && (
                        <button
                          type="button"
                          onClick={() => void handleMergeSelectedTracks()}
                          className="h-7 px-2 bg-primary-container text-on-primary-container rounded font-label text-label-sm flex items-center gap-1"
                        >
                          <Check size={13} />Merge {mergeTrackIds.size}
                        </button>
                      )}
                      {mergeTrackIds.size > 0 && (
                        <button
                          type="button"
                          onClick={() => void removeSelectedTracks()}
                          className="h-7 px-2 border border-error/50 text-error rounded font-label text-label-sm"
                        >
                          Delete selected ({mergeTrackIds.size})
                        </button>
                      )}
                    </div>
                    <div className="space-y-1">
                      {tracks.map((track) => {
                        const isSelected = selectedTrack === track.track_id;
                        const isChecked = mergeTrackIds.has(track.track_id);
                        return (
                          <div
                            key={track.track_id}
                            className={`work-card rounded border p-2 ${isSelected ? 'border-primary bg-primary/10' : 'border-outline-variant'}`}
                          >
                            <div className="flex items-center gap-2">
                              {/* Checkbox for multi-merge (#8) */}
                              {tracks.length > 1 && (
                                <input
                                  type="checkbox"
                                  aria-label={`Select Worker ${track.track_id} for merge`}
                                  checked={isChecked}
                                  onChange={(e) => {
                                    setSelectionScope('worker');
                                    setMergeTrackIds((prev) => {
                                      const next = new Set(prev);
                                      if (e.target.checked) next.add(track.track_id); else next.delete(track.track_id);
                                      return next;
                                    });
                                  }}
                                  className="shrink-0"
                                />
                              )}
                              <button
                                type="button"
                                onClick={(event) => {
                                  if (event.ctrlKey || event.metaKey) {
                                    setSelectionScope('worker');
                                    setMergeTrackIds((current) => {
                                      const next = new Set(current);
                                      if (next.has(track.track_id)) next.delete(track.track_id); else next.add(track.track_id);
                                      return next;
                                    });
                                    return;
                                  }
                                  chooseTrack(track.track_id);
                                }}
                                className="flex-1 text-left min-w-0"
                              >
                                <div className="flex justify-between">
                                  <span className="font-medium">Worker {track.track_id}</span>
                                  <span className="font-label text-label-sm">{Math.round(track.avg_keypoint_confidence * 100)}% pose</span>
                                </div>
                                <p className="text-[10px] text-on-surface-variant mt-0.5">Frames {track.start_frame}–{track.end_frame}</p>
                              </button>
                            </div>
                            {/* #12 — Inline track actions (no dropdown) */}
                            {isSelected && active && (
                              <div className="flex gap-1 mt-2 flex-wrap">
                                <button
                                  type="button"
                                  onClick={() => void splitWorker(track)}
                                  className="panel-button flex-1"
                                >
                                  Split
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void toggleWorkerInclusion(track)}
                                  className="panel-button flex-1"
                                >
                                  {track.include_in_export ? 'Exclude' : 'Restore'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSelectionScope('worker');
                                    setMergeTrackIds(new Set([track.track_id]));
                                    void removeSelectedTracks([track.track_id]);
                                  }}
                                  className="panel-button flex-1 text-error border-error/50 hover:bg-error/10 hover:border-error"
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {tracks.length === 0 && <p className="text-label-sm text-on-surface-variant">Process the video to detect worker tracks.</p>}
                    </div>
                    <label className="flex items-center gap-2 text-label-sm mt-2">
                      <input type="checkbox" checked={selectedOnly} onChange={(e) => setSelectedOnly(e.target.checked)} />Show selected worker only
                    </label>
                  </section>

                  {/* ── Segment editor ── */}
                  {activeTrack && (
                    <section className="border-t border-outline-variant pt-3">
                      <div className="flex items-center justify-between mb-2">
                        <p className="font-label text-label-caps uppercase text-on-surface-variant">Segments ({activeSegments.length})</p>
                        {selectedSegmentIds.size > 0 && (
                          <div className="flex items-center gap-1">
                            {canMergeSelectedSegments && (
                              <button type="button" onClick={() => void mergeSelectedSegments()} className="h-7 px-2 bg-primary-container text-on-primary-container rounded font-label text-label-sm flex items-center gap-1">
                                <Check size={13} />Merge {selectedSegmentIds.size}
                              </button>
                            )}
                            <button type="button" onClick={() => void removeSelectedSegments()} className="h-7 px-2 border border-error/50 text-error rounded font-label text-label-sm">
                              Delete selected ({selectedSegmentIds.size})
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {activeSegments.map((seg) => {
                          const isMultiSelected = selectedSegmentIds.has(seg.segment_id);
                          return (
                          <div key={seg.segment_id} className={`work-card w-full rounded text-left border ${selectedSegment?.segment_id === seg.segment_id ? 'border-primary bg-primary/10' : 'border-outline-variant'}`}>
                            <div className="w-full p-2 text-label-sm flex items-center gap-2">
                              <input
                                type="checkbox"
                                aria-label={`Select ${seg.label} segment ${seg.start_frame} to ${seg.end_frame}`}
                                checked={isMultiSelected}
                                onChange={() => {
                                  setSelectionScope('segment');
                                  setSelectedSegmentIds((current) => {
                                    const next = new Set(current);
                                    if (next.has(seg.segment_id)) next.delete(seg.segment_id); else next.add(seg.segment_id);
                                    return next;
                                  });
                                }}
                              />
                              <button type="button" onClick={(event) => {
                                if (event.ctrlKey || event.metaKey) {
                                  setSelectionScope('segment');
                                  setSelectedSegmentIds((current) => {
                                    const next = new Set(current);
                                    if (next.has(seg.segment_id)) next.delete(seg.segment_id); else next.add(seg.segment_id);
                                    return next;
                                  });
                                  return;
                                }
                                chooseSegment(seg);
                              }} className="flex-1 text-left flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: LABEL_COLORS[seg.label] }} />
                              <span className="capitalize font-medium">{seg.label}</span>
                              <span className="text-on-surface-variant ml-auto">{seg.start_frame}–{seg.end_frame}</span>
                              </button>
                            </div>
                            {selectedSegment?.segment_id === seg.segment_id && (
                              <div className="px-2 pb-2 flex gap-2">
                                <button type="button" disabled={frame <= seg.start_frame || frame >= seg.end_frame} onClick={() => void splitSelectedSegment(seg)} className="panel-button flex-1 disabled:opacity-40">Split</button>
                                <button type="button" onClick={() => void expandSegment(seg)} className="panel-button flex-1">Expand</button>
                                <button type="button" onClick={() => void removeSegment()} className="panel-button flex-1 text-error border-error/50 hover:bg-error/10 hover:border-error">Delete</button>
                              </div>
                            )}
                          </div>
                        );
                        })}
                        <button type="button" onClick={chooseCreateSegment} className={`w-full rounded border border-dashed p-2 text-left text-label-sm font-medium ${creatingSegment ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant text-on-surface-variant hover:border-primary/50'}`}>
                          + Create Segment
                        </button>
                      </div>

                      {(selectedSegment || creatingSegment) && (
                        <div className="mt-3 border-t border-outline-variant pt-3">
                          <p className="font-label text-label-caps uppercase text-on-surface-variant mb-2">{selectedSegment ? 'Modify segment' : 'Create segment'}</p>
                          <div className="grid grid-cols-2 gap-2">
                            <label className="text-label-sm">Start<input aria-label="Start" type="number" value={start} onChange={(e) => setStart(Number(e.target.value))} className="editor-input" /></label>
                            <label className="text-label-sm">End<input aria-label="End" type="number" value={end} onChange={(e) => setEnd(Number(e.target.value))} className="editor-input" /></label>
                          </div>
                          {active && (
                            <div className="grid grid-cols-2 gap-2 mt-2">
                              <button type="button" onClick={() => setStart(frame)} className="h-8 border border-outline-variant hover:border-primary rounded font-label text-label-sm transition-colors">+ Start Point</button>
                              <button type="button" onClick={() => setEnd(frame)} className="h-8 border border-outline-variant hover:border-primary rounded font-label text-label-sm transition-colors">+ End Point</button>
                            </div>
                          )}
                          <div className="grid grid-cols-3 gap-1 mt-2">
                            {(['others', 'running', 'falling'] as HumanVideoLabel[]).map((value) => (
                              <button type="button" key={value} onClick={() => setLabel(value)} className={`h-8 rounded border text-label-sm capitalize ${label === value ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant text-on-surface-variant hover:border-primary/50'}`} style={{ borderLeftWidth: label === value ? '1px' : '4px', borderLeftColor: LABEL_COLORS[value] }}>{value}</button>
                            ))}
                          </div>
                          <div className="flex gap-2 mt-3">
                            <button type="button" onClick={() => void saveSegment()} className="h-8 px-3 bg-primary-container text-on-primary-container rounded flex-1 font-label text-label-sm">
                              {selectedSegment ? 'Modify segment' : 'Add segment'}
                            </button>
                          </div>
                        </div>
                      )}
                    </section>
                  )}

                  {/* #3 — Fill unlabeled gaps */}
                  {activeTrack && (
                    <section className="border-t border-outline-variant pt-3">
                      <p className="font-label text-label-caps uppercase text-on-surface-variant mb-2">Fill unlabeled gaps</p>
                      <div className="flex gap-2 items-center">
                        <select
                          aria-label="Fill class"
                          value={fillClass}
                          onChange={(e) => setFillClass(e.target.value as HumanVideoLabel)}
                          className="flex-1 h-8 bg-surface-container-lowest border border-outline-variant rounded px-2 font-label text-label-sm"
                        >
                          <option value="others">others</option>
                          <option value="running">running</option>
                          <option value="falling">falling</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => void fillTrackGaps(activeTrack)}
                          className="h-8 px-3 border border-outline-variant rounded font-label text-label-sm"
                          style={{ borderColor: LABEL_COLORS[fillClass] }}
                        >
                          Fill gaps
                        </button>
                      </div>
                    </section>
                  )}

                  {/* #1 — Segment list for the active track */}
                </div>
              )}

              {/* ── Details tab: video facts, annotation summary, and controls ── */}
              {tab === 'details' && (
                <div className="p-3 space-y-3">
                  {/* Video facts */}
                  <section className="border border-outline-variant rounded p-3">
                    <p className="font-label text-label-caps uppercase text-on-surface-variant">Video</p>
                    {active ? (
                      <dl className="mt-2 space-y-2 text-label-sm">
                        <div className="flex items-start justify-between gap-3">
                          <dt className="text-on-surface-variant shrink-0">Name</dt>
                          <dd className="truncate text-right" title={active.filename}>{active.filename}</dd>
                        </div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Resolution</dt><dd>{active.width} × {active.height}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Frame rate</dt><dd>{active.original_fps === active.canonical_fps ? `${active.canonical_fps} fps` : `${active.original_fps} source · ${active.canonical_fps} annotation`}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Duration</dt><dd>{active.duration_seconds.toFixed(1)} s · {active.canonical_frame_count} frames</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Playhead</dt><dd>{frame + 1} / {active.canonical_frame_count} · {formatFrameTimestamp(frame, active.canonical_fps)}</dd></div>
                      </dl>
                    ) : <p className="text-label-sm text-on-surface-variant mt-2">No video selected.</p>}
                  </section>

                  {active && (
                    <section className="border border-outline-variant rounded p-3">
                      <p className="font-label text-label-caps uppercase text-on-surface-variant">Annotation</p>
                      <dl className="mt-2 space-y-2 text-label-sm">
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Workers</dt><dd>{tracks.length}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Segments</dt><dd>{segments.length}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Timeline coverage</dt><dd>{annotationCoverage}% · {coveredFrames} frames</dd></div>
                        {(['others', 'running', 'falling'] as HumanVideoLabel[]).map((item) => (
                          <div key={item} className="flex justify-between gap-3">
                            <dt className="flex items-center gap-1.5 capitalize text-on-surface-variant"><span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: LABEL_COLORS[item] }} />{item}</dt>
                            <dd>{detailLabelCounts[item]} segment{detailLabelCounts[item] === 1 ? '' : 's'}</dd>
                          </div>
                        ))}
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">System generated</dt><dd>{generatedSegmentCount} segment{generatedSegmentCount === 1 ? '' : 's'}</dd></div>
                      </dl>
                    </section>
                  )}

                  {active && (
                    <section className="border border-outline-variant rounded p-3">
                      <p className="font-label text-label-caps uppercase text-on-surface-variant">Workflow</p>
                      <dl className="mt-2 space-y-2 text-label-sm">
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Processing</dt><dd className="capitalize">{activeJob ? `${displayStatus(activeJob.stage)} in progress` : displayStatus(active.processing_status)}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Suggestion mode</dt><dd>{source}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Dataset</dt><dd>{active.include_in_export ? 'Included in export' : 'Excluded'}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Approval</dt><dd>{active.is_approved ? 'Approved' : 'Not approved'}</dd></div>
                      </dl>
                    </section>
                  )}

                  {/* Overlay controls */}
                  <section className="border border-outline-variant rounded p-3 space-y-2">
                    <p className="font-label text-label-caps uppercase text-on-surface-variant">Overlay</p>
                    <label className="flex items-center gap-2 text-label-sm">
                      <input type="checkbox" checked={showBoxes} onChange={(e) => setShowBoxes(e.target.checked)} />
                      Bounding boxes &amp; pose skeleton
                    </label>
                    <label className="flex items-center gap-2 text-label-sm">
                      <input type="checkbox" checked={selectedOnly} onChange={(e) => setSelectedOnly(e.target.checked)} />
                      Selected worker only
                    </label>
                  </section>

                  {active && (
                    <details className="border border-outline-variant rounded p-3 group">
                      <summary className="font-label text-label-sm cursor-pointer text-on-surface-variant group-open:text-on-surface">Technical details</summary>
                      <dl className="mt-3 space-y-2 text-label-sm">
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Original frames</dt><dd>{active.original_frame_count}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Annotation quality</dt><dd className="capitalize">{displayStatus(active.quality_status)}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Revision</dt><dd>{active.annotation_revision}</dd></div>
                        <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Last updated</dt><dd>{new Date(active.updated_at).toLocaleString()}</dd></div>
                        {!active.include_in_export && active.exclude_reason && <div className="flex justify-between gap-3"><dt className="text-on-surface-variant">Exclusion reason</dt><dd className="text-right">{active.exclude_reason}</dd></div>}
                      </dl>
                      {active.last_error && <p role="status" className="mt-3 rounded bg-error/10 px-2 py-1.5 text-label-sm text-error">{active.last_error}</p>}
                    </details>
                  )}
                </div>
              )}
            </div>

            {/* #9 — Approve / Unapprove button at sidebar bottom */}
            {active && (
              <div className="shrink-0 p-3 border-t border-outline-variant">
                <div className="mb-2" aria-label={`Approval progress: ${approvedVideoCount} approved, ${videosRemainingApproval} remaining, ${videos.length} total`}>
                  <div className="flex justify-between gap-2 font-label text-[10px] text-on-surface-variant">
                    <span>Approval progress</span>
                    <span>{approvedVideoCount} / {videos.length} approved · {videosRemainingApproval} left</span>
                  </div>
                  <div className="h-1 mt-1 bg-surface-container-highest rounded overflow-hidden">
                    <div className="h-full bg-primary transition-all" style={{ width: `${approvalProgress}%` }} />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void handleApproveToggle()}
                  className={`w-full h-9 rounded font-label text-label-sm font-bold flex items-center justify-center gap-2 transition-colors ${
                    active.is_approved
                      ? 'bg-error/10 text-error border border-error/50 hover:bg-error/20'
                      : 'bg-primary-container text-on-primary-container hover:brightness-110'
                  }`}
                >
                  {active.is_approved ? (
                    <><X size={15} />Unapprove</>
                  ) : (
                    <><Check size={15} />Approve video</>
                  )}
                </button>
              </div>
            )}
          </aside>
          </>
        )}
      </div>

      {/* ── Dialogs ── */}
      <PoseHelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
      <ShortcutGuideOverlay visible={shortcutGuideVisible} />

      {/* Export modal (#9) */}
      {exportOpen && (
        <div className="fixed inset-0 z-[110] bg-black/60 flex items-center justify-center p-4" onMouseDown={() => setExportOpen(false)}>
          <section role="dialog" aria-modal="true" aria-labelledby="export-dialog-title" onMouseDown={(e) => e.stopPropagation()} className="decorative-dialog w-full max-w-md bg-surface-container-high border border-outline-variant rounded-lg p-5">
            <h2 id="export-dialog-title" className="font-headline-sm mb-3">Export Dataset</h2>
            <ExportPanel projectId={projectId} exports={exports} />
            <button type="button" onClick={() => setExportOpen(false)} className="mt-4 h-8 px-3 border border-outline-variant rounded font-label text-label-sm">Close</button>
          </section>
        </div>
      )}

      {/* Delete confirmation */}
      {pendingDeleteIds.length > 0 && (
        <div className="fixed inset-0 z-[110] bg-black/60 flex items-center justify-center p-4" onMouseDown={() => deletingIds.size === 0 && setPendingDeleteIds([])}>
          <section role="alertdialog" aria-modal="true" aria-labelledby="delete-video-title" onMouseDown={(e) => e.stopPropagation()} className="decorative-dialog w-full max-w-md bg-surface-container-high border border-outline-variant rounded-lg p-5">
            <div className="flex gap-3"><AlertTriangle className="text-error shrink-0" size={22} /><div><h2 id="delete-video-title" className="font-headline-sm">{pendingDeleteIds.length === 1 ? `Delete ${videos.find((video) => video.video_id === pendingDeleteIds[0])?.filename ?? 'video'}?` : `Delete ${pendingDeleteIds.length} videos?`}</h2><p className="text-body-md text-on-surface-variant mt-2">This removes the managed copy, annotations, jobs, thumbnail, and derived pose data.</p></div></div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" disabled={deletingIds.size > 0} onClick={() => setPendingDeleteIds([])} className="h-8 px-3 border border-outline-variant rounded disabled:opacity-40">Cancel</button>
              <button type="button" disabled={deletingIds.size > 0} onClick={() => void confirmDeleteVideos()} className="h-8 px-3 bg-error-container text-on-error-container rounded flex items-center gap-2 disabled:opacity-40">{deletingIds.size > 0 && <Loader2 size={14} className="animate-spin" />}Delete video{pendingDeleteIds.length === 1 ? '' : 's'}</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
