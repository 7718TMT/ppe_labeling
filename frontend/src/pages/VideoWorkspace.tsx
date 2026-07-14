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
 * #18 Details tab: only Video info + Overlay controls remain.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
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
  SkipBack,
  SkipForward,
  Undo2,
  X,
} from 'lucide-react';

import {
  approveVideo,
  controlVideoJob,
  createVideoExport,
  deleteVideo as deleteImportedVideo,
  deleteVideoSegment,
  deleteVideoTrack,
  getProcessingOptions,
  getFeatures,
  getPoseOverlay,
  getVideoJobs,
  getVideoProject,
  getVideoSegments,
  getVideoTracks,
  getVideos,
  importVideos,
  mergeMultipleVideoTracks,
  processVideo,
  saveVideoSegment,
  saveVideoWorkspaceState,
  setVideoSegmentInclusion,
  setVideoTrackInclusion,
  splitVideoSegment,
  splitVideoTrack,
  unapproveVideo,
  videoHistoryAction,
} from '../api/client';
import { ExportPanel } from '../features/video/ExportPanel';
import { PoseHelpDialog } from '../features/video/PoseHelpDialog';
import { PoseVideoPlayer } from '../features/video/PoseVideoPlayer';
import { SuggestionModeButton, type ProcessMode } from '../features/video/ProcessModeButton';
import { ProcessingQueue } from '../features/video/ProcessingQueue';
import { ShortcutGuideOverlay } from '../features/video/ShortcutGuideOverlay';
import { VideoBrowser } from '../features/video/VideoBrowser';
import { VideoTimeline } from '../features/video/VideoTimeline';
import type {
  FeatureWindow,
  GeneratedWindow,
  HumanVideoLabel,
  PoseTrackFrame,
  ProcessingJob,
  ProcessingOptions,
  SuggestionSource,
  VideoItem,
  VideoProject,
  VideoSegment,
  VideoTrack,
} from '../types';

/** Right-sidebar tabs. Suggestions tab removed (#4). */
type RightTab = 'annotate' | 'details';

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'paused']);

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
  const frameRef = useRef(0);
  const activeLoadRef = useRef(0);
  const projectRef = useRef<VideoProject | null>(null);
  const processingTransitionRef = useRef<{ videoId?: string; active: boolean }>({ active: false });
  const pendingMediaSeekRef = useRef<{ videoId: string; seconds: number }>();
  const workspaceSaveChainRef = useRef<Promise<unknown>>(Promise.resolve());
  const savingRequestCountRef = useRef(0);
  const featureAutoTimerRef = useRef<number>();
  const overlayCacheRef = useRef<{
    videoId?: string;
    frames: Map<number, PoseTrackFrame>;
    loaded: Set<number>;
    pending: Set<string>;
  }>({ frames: new Map(), loaded: new Set(), pending: new Set() });

  const [project, setProject] = useState<VideoProject | null>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [active, setActive] = useState<VideoItem | null>(null);
  const [tracks, setTracks] = useState<VideoTrack[]>([]);
  const [selectedTrack, setSelectedTrack] = useState<number>();
  /** Set of track IDs checked for multi-merge (#8). */
  const [mergeTrackIds, setMergeTrackIds] = useState<Set<number>>(new Set());
  const [segments, setSegments] = useState<VideoSegment[]>([]);
  const [revision, setRevision] = useState(0);
  const [selectedSegment, setSelectedSegment] = useState<VideoSegment>();
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
  const [features, setFeatures] = useState<FeatureWindow[]>([]);
  const [overlay, setOverlay] = useState<PoseTrackFrame>();
  const [overlayCacheRevision, setOverlayCacheRevision] = useState(0);
  const [frame, setFrame] = useState(0);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [label, setLabel] = useState<HumanVideoLabel>('others');
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  /** showBoxes now controls BOTH bbox and skeleton (#13). */
  const [showBoxes, setShowBoxes] = useState(true);
  const [selectedOnly, setSelectedOnly] = useState(false);
  const [leftOpen, setLeftOpen] = useState(() => window.innerWidth >= 900);
  const [rightOpen, setRightOpen] = useState(() => window.innerWidth >= 1200);
  const [tab, setTab] = useState<RightTab>('annotate');
  const [saving, setSaving] = useState(false);
  const [autosaveFailedDraft, setAutosaveFailedDraft] = useState<string>();
  const [processingRequests, setProcessingRequests] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<VideoItem>();
  const [deletingId, setDeletingId] = useState<string>();
  const [helpOpen, setHelpOpen] = useState(false);
  const [shortcutGuideVisible, setShortcutGuideVisible] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [historyUnavailable, setHistoryUnavailable] = useState<'undo' | 'redo' | null>(null);

  projectRef.current = project;
  activeIdRef.current = active?.video_id;
  frameRef.current = frame;

  useEffect(() => () => { activeIdRef.current = undefined; }, []);

  useEffect(() => {
    const synchronizeFullscreen = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', synchronizeFullscreen);
    synchronizeFullscreen();
    return () => document.removeEventListener('fullscreenchange', synchronizeFullscreen);
  }, []);

  useEffect(() => {
    function showShortcutGuide(event: KeyboardEvent) {
      if (event.key === 'Alt' && !event.repeat && !helpOpen && !pendingDelete && !exportOpen) {
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
  }, [exportOpen, helpOpen, pendingDelete]);

  useEffect(() => {
    setHistoryUnavailable(null);
  }, [revision]);

  const refreshShell = useCallback(async () => {
    const [projectData, videoRows, jobRows, options] = await Promise.all([
      getVideoProject(projectId),
      getVideos(projectId),
      getVideoJobs(projectId),
      getProcessingOptions(projectId).catch(() => ({
        threshold_available: true,
        model_available: false,
        model_message: 'Model suggestions are currently unavailable.',
      })),
    ]);
    setProject(projectData);
    setVideos(videoRows);
    setJobs(jobRows);
    setProcessingOptions(options);
    setActive((current) => {
      if (current) return videoRows.find((item) => item.video_id === current.video_id) ?? videoRows[0] ?? null;
      return videoRows.find((item) => item.video_id === projectData.workspace_state?.video_id) ?? videoRows[0] ?? null;
    });
    setSource((current) => {
      if (current !== 'Threshold') return current;
      const remembered = projectData.workspace_state?.suggestion_source ?? 'Threshold';
      return remembered === 'AI' && !options.model_available ? 'Off' : remembered;
    });
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const poll = () => {
      Promise.all([getVideoJobs(projectId), getVideos(projectId)])
        .then(([jobRows, videoRows]) => {
          if (cancelled) return;
          setJobs(jobRows);
          setVideos(videoRows);
          setActive((current) => {
            if (!current) return videoRows[0] ?? null;
            return videoRows.find((item) => item.video_id === current.video_id) ?? videoRows[0] ?? null;
          });
          const hasActiveJobs = jobRows.some((job) => ACTIVE_JOB_STATUSES.has(job.status));
          timer = window.setTimeout(poll, hasActiveJobs ? 3000 : 30000);
        })
        .catch(() => { if (!cancelled) timer = window.setTimeout(poll, 30000); });
    };
    refreshShell()
      .catch((reason) => !cancelled && setError(readableError(reason)))
      .finally(() => { if (!cancelled) timer = window.setTimeout(poll, 3000); });
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [projectId, refreshShell]);

  const loadActive = useCallback(async (video: VideoItem) => {
    const generation = activeLoadRef.current + 1;
    activeLoadRef.current = generation;
    setError('');
    setMessage('');
    setPlaying(false);
    setOverlay(undefined);
    overlayCacheRef.current = { videoId: video.video_id, frames: new Map(), loaded: new Set(), pending: new Set() };
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
      const [trackRows, segmentData] = await Promise.all([
        getVideoTracks(projectId, video.video_id),
        getVideoSegments(projectId, video.video_id),
      ]);
      if (generation !== activeLoadRef.current || activeIdRef.current !== video.video_id) return;
      setTracks(trackRows);
      setSegments(segmentData.segments);
      setRevision(segmentData.revision);
      void getFeatures(projectId, video.video_id).then((rows) => {
        if (generation !== activeLoadRef.current || activeIdRef.current !== video.video_id) return;
        setFeatures(rows);
      });
      const workspace = projectRef.current?.workspace_state;
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
      if (generation === activeLoadRef.current && activeIdRef.current === video.video_id) setError(readableError(reason));
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
      setFeatures([]);
      setOverlay(undefined);
      setPlaying(false);
    }
  }, [active?.video_id, loadActive]);

  useEffect(() => {
    if (!active) { setOverlay(undefined); return; }
    const videoId = active.video_id;
    const requestedFrame = frame;
    let cache = overlayCacheRef.current;
    if (cache.videoId !== videoId) {
      cache = { videoId, frames: new Map(), loaded: new Set(), pending: new Set() };
      overlayCacheRef.current = cache;
    }
    if (cache.loaded.has(requestedFrame)) { setOverlay(cache.frames.get(requestedFrame)); return; }
    setOverlay(undefined);
    const chunkStart = Math.floor(requestedFrame / 48) * 48;
    const chunkEnd = Math.min(active.canonical_frame_count - 1, chunkStart + 47);
    const chunkKey = `${chunkStart}:${chunkEnd}`;
    if (cache.pending.has(chunkKey)) return;
    cache.pending.add(chunkKey);
    getPoseOverlay(projectId, videoId, chunkStart, chunkEnd).then((rows) => {
      const currentCache = overlayCacheRef.current;
      if (currentCache !== cache || currentCache.videoId !== videoId) return;
      rows.forEach((item) => currentCache.frames.set(item.frame_index, item));
      for (let index = chunkStart; index <= chunkEnd; index += 1) currentCache.loaded.add(index);
      currentCache.pending.delete(chunkKey);
      if (activeIdRef.current === videoId) setOverlay(currentCache.frames.get(frameRef.current));
    }).catch(() => {
      const currentCache = overlayCacheRef.current;
      if (currentCache !== cache) return;
      if (currentCache.videoId === videoId) currentCache.pending.delete(chunkKey);
      if (activeIdRef.current === videoId && frameRef.current === requestedFrame) setOverlay(undefined);
    });
  }, [active?.video_id, active?.canonical_frame_count, frame, overlayCacheRevision, projectId]);

  useEffect(() => {
    if (!active) return undefined;
    const videoId = active.video_id;
    const payload = { video_id: videoId, track_id: selectedTrack, frame_index: frame, suggestion_source: source };
    const timer = window.setTimeout(() => {
      workspaceSaveChainRef.current = workspaceSaveChainRef.current
        .catch(() => undefined)
        .then(() => saveVideoWorkspaceState(projectId, payload))
        .catch(() => { if (activeIdRef.current === videoId) setError('Workspace recovery state could not be saved.'); });
    }, 500);
    return () => window.clearTimeout(timer);
  }, [active?.video_id, selectedTrack, frame, source, projectId]);

  /** #15 — Auto-trigger feature extraction after 5 s of no segment changes. */
  const scheduleFeatureExtraction = useCallback(() => {
    if (featureAutoTimerRef.current) window.clearTimeout(featureAutoTimerRef.current);
    const videoId = active?.video_id;
    if (!videoId || !active) return;
    featureAutoTimerRef.current = window.setTimeout(() => {
      processVideo(projectId, videoId, 'Threshold').catch(() => undefined);
    }, 5000);
  }, [active?.video_id, projectId]);

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
    if (player.current) player.current.loop = loop && !selectedSegment;
  }, [loop, selectedSegment]);

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
    if (loop && selectedSegment && current >= selectedSegment.end_frame && !element.ended) {
      seek(selectedSegment.start_frame); void element.play(); return;
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
        scheduleFeatureExtraction(); // #15
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
    savingRequestCountRef.current += 1;
    setSaving(true);
    try {
      const result = await deleteVideoSegment(projectId, videoId, selectedSegment.segment_id, revision);
      if (activeIdRef.current === videoId) {
        setRevision(result.revision);
        setSegments((current) => current.filter((item) => item.segment_id !== selectedSegment.segment_id));
        setSelectedSegment(undefined);
        setCreatingSegment(false);
        setMessage('Segment deleted.');
        scheduleFeatureExtraction(); // #15
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    } finally {
      savingRequestCountRef.current = Math.max(0, savingRequestCountRef.current - 1);
      setSaving(savingRequestCountRef.current > 0);
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
      scheduleFeatureExtraction(); // #15
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
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    }
  }

  /**
   * #9 — Approve the current video. On success, triggers auto feature extraction (#15).
   * If already approved, calls unapprove instead.
   */
  async function handleApproveToggle() {
    if (!active) return;
    const videoId = active.video_id;
    try {
      if (active.is_approved) {
        const updated = await unapproveVideo(projectId, videoId);
        setVideos((current) => current.map((item) => item.video_id === videoId ? { ...item, ...updated } : item));
        setActive((current) => current?.video_id === videoId ? { ...current, ...updated } : current);
        setMessage('Approval revoked.');
      } else {
        const updated = await approveVideo(projectId, videoId);
        setVideos((current) => current.map((item) => item.video_id === videoId ? { ...item, ...updated } : item));
        setActive((current) => current?.video_id === videoId ? { ...current, ...updated } : current);
        setMessage('Video approved.');
        // Auto-trigger feature extraction immediately on approval (#15)
        if (featureAutoTimerRef.current) window.clearTimeout(featureAutoTimerRef.current);
        processVideo(projectId, videoId, 'Threshold').catch(() => undefined);
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
    setProcessingRequests((current) => new Set(current).add(videoId));
    setError('');
    try {
      const rows = await processVideo(projectId, videoId, mode);
      setJobs((current) => upsertJobRows(current, rows));
      if (activeIdRef.current === videoId) {
        setMessage(`${source} suggestion generation started.`);
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(`Processing could not start. ${readableError(reason)}`);
    } finally {
      setProcessingRequests((current) => { const next = new Set(current); next.delete(videoId); return next; });
    }
  }

  async function confirmDeleteVideo() {
    if (!pendingDelete || deletingId) return;
    const target = pendingDelete;
    const targetIndex = videos.findIndex((item) => item.video_id === target.video_id);
    const deletingActive = activeIdRef.current === target.video_id;
    setDeletingId(target.video_id);
    setError('');
    if (deletingActive) {
      player.current?.pause();
      setPlaying(false);
      setOverlay(undefined);
      setActive(null);
      await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    }
    try {
      await deleteImportedVideo(projectId, target.video_id);
      const remaining = videos.filter((item) => item.video_id !== target.video_id);
      const next = remaining[Math.min(targetIndex, Math.max(0, remaining.length - 1))] ?? null;
      setVideos(remaining);
      setJobs((current) => current.filter((job) => job.video_id !== target.video_id));
      if (deletingActive) setActive(next);
      setPendingDelete(undefined);
      setMessage(`${target.filename} was deleted.`);
    } catch (reason) {
      if (deletingActive) setActive(target);
      setError(`Could not delete ${target.filename}. ${readableError(reason)}`);
    } finally {
      setDeletingId(undefined);
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
        return [...current, ...rows.filter((item) => !existing.has(item.video_id))];
      });
      if (!active && rows[0]) setActive(rows[0]);
      setMessage(`${rows.length} video${rows.length === 1 ? '' : 's'} imported and queued for processing.`);
      await refreshShell();
    } catch (reason) {
      setError(`Import failed. ${readableError(reason)}`);
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

  /**
   * #11 — Commits one locally previewed timeline-boundary resize on release.
   */
  async function handleSegmentResize(segmentId: string, newStart: number, newEnd: number) {
    const seg = segments.find((s) => s.segment_id === segmentId);
    if (!seg || !active) return;
    const videoId = active.video_id;
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
      scheduleFeatureExtraction(); // #15
    } catch { /* drag resize failures are silent; the segment stays in its last valid state */ }
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

    overlayCacheRef.current = { videoId, frames: new Map(), loaded: new Set(), pending: new Set() };
    setOverlay(undefined);
    setOverlayCacheRevision((c) => c + 1);

    Promise.all([
      getVideoTracks(projectId, videoId),
      getVideoSegments(projectId, videoId),
      getFeatures(projectId, videoId),
    ]).then(([trackRows, segmentData, featureRows]) => {
      if (activeIdRef.current !== videoId) return;
      setTracks(trackRows);
      setSelectedTrack((current) => {
        if (current !== undefined && trackRows.some((track) => track.track_id === current)) return current;
        return trackRows.slice().sort((a, b) => (b.end_frame - b.start_frame) - (a.end_frame - a.start_frame))[0]?.track_id;
      });
      setSegments(segmentData.segments);
      setRevision(segmentData.revision);
      setSelectedSegment((current) => current
        ? segmentData.segments.find((s) => s.segment_id === current.segment_id)
        : undefined);
      setFeatures(featureRows);
    }).catch(() => {
      if (activeIdRef.current === videoId) setError('Processing finished, but its new results could not be loaded.');
    });
  }, [active?.video_id, activeProcessing, projectId]);

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
      if (helpOpen || pendingDelete) return;
      const target = event.target;
      if (target instanceof HTMLElement && (
        target.isContentEditable
        || target.closest('input, textarea, select, button, a, [contenteditable="true"]')
      )) return;
      if (event.ctrlKey && event.key.toLowerCase() === 'z') { event.preventDefault(); void history('undo'); return; }
      if (event.ctrlKey && event.key.toLowerCase() === 'y') { event.preventDefault(); void history('redo'); return; }
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

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen bg-background text-on-background flex flex-col overflow-hidden">

      {/* ── Navbar ── */}
      <header className="h-toolbar-height bg-surface-container border-b border-outline-variant flex items-center px-gutter justify-between shrink-0 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button type="button" aria-label="Toggle video browser" onClick={() => setLeftOpen(!leftOpen)} className="toolbar-icon"><PanelLeft size={18} /></button>
          <Link to="/" className="font-headline-sm font-bold text-primary">Home</Link>
          <span className="text-on-surface-variant">/</span>
          <Link to="/video" className="text-on-surface hover:text-primary">Pose</Link>
          <span className="hidden md:inline text-on-surface-variant">/</span>
          <span className="hidden md:inline truncate max-w-48">{project?.name ?? 'Loading…'}</span>
          {active && <><span className="hidden xl:inline text-on-surface-variant">/</span><span className="hidden xl:inline truncate max-w-48">{active.filename}</span></>}
        </div>

        <div className="hidden lg:flex items-center gap-1">
          <button type="button" aria-label="Undo" disabled={historyUnavailable === 'undo'} title={historyUnavailable === 'undo' ? 'No changes available to undo' : 'Undo'} onClick={() => void history('undo')} className="toolbar-icon disabled:opacity-30"><Undo2 size={17} /></button>
          <button type="button" aria-label="Redo" disabled={historyUnavailable === 'redo'} title={historyUnavailable === 'redo' ? 'No changes available to redo' : 'Redo'} onClick={() => void history('redo')} className="toolbar-icon disabled:opacity-30"><Redo2 size={17} /></button>
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

          {/* #9 — Export button replaces "Complete & Next". */}
          <button
            type="button"
            disabled={!active}
            onClick={() => setExportOpen(true)}
            className="h-8 px-3 bg-surface-container text-on-surface border border-outline-variant rounded font-label text-label-sm flex items-center gap-2 disabled:opacity-40"
          >
            <Download size={15} /><span className="hidden sm:inline">Export</span>
          </button>

          <SuggestionModeButton
            source={source}
            disabled={!active}
            generating={Boolean(active && processingRequests.has(active.video_id)) || activeProcessing}
            modelAvailable={modelAvailable}
            modelUnavailableReason={processingOptions.model_message ?? 'Model suggestions are unavailable.'}
            onSourceChange={setSource}
            onGenerate={() => void generateSuggestions()}
          />

          <button type="button" aria-label="Toggle inspector" onClick={() => setRightOpen(!rightOpen)} className="toolbar-icon"><PanelRight size={18} /></button>
        </div>
      </header>

      {/* ── Status bar ── */}
      {(error || message) && (
        <div className={`px-4 py-2 text-label-sm border-b ${error ? 'bg-error-container/40 border-error/40 text-error' : 'bg-primary/10 border-primary/30'}`} role={error ? 'alert' : 'status'}>
          {error || message}
          <button type="button" aria-label="Dismiss message" className="float-right" onClick={() => { setError(''); setMessage(''); }}>×</button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">

        {/* ── Left sidebar ── */}
        {leftOpen && (
          <aside className="w-[320px] bg-surface-container border-r border-outline-variant flex flex-col shrink-0">
            <VideoBrowser
              videos={videos}
              jobs={jobs}
              selectedId={active?.video_id}
              deletingId={deletingId}
              onSelect={setActive}
              onImport={(files) => void handleImport(files)}
              onDelete={setPendingDelete}
            />
            <ProcessingQueue
              jobs={jobs}
              onControl={(job, action) => {
                void controlVideoJob(projectId, job.job_id, action)
                  .then(refreshShell)
                  .catch((reason) => setError(readableError(reason)));
              }}
            />
          </aside>
        )}

        {/* ── Main workspace ── */}
        <main className="flex-1 min-w-0 flex flex-col bg-surface-container-lowest" ref={containerRef}>
          {!active ? (
            <div className="flex-1 flex items-center justify-center text-on-surface-variant">Import or select a video to begin.</div>
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
                  playing={playing}
                  onSelectTrack={chooseTrack}
                  onTimeUpdate={synchronizePlayer}
                  onSeek={seek}
                  onPlayPause={() => void togglePlay()}
                  onMediaError={() => setError('This video format is unsupported or the media file is damaged. Annotations and pose data are still available.')}
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
                <select aria-label="Playback speed" defaultValue="1" onChange={(e) => { if (player.current) player.current.playbackRate = Number(e.target.value); }} className="h-8 bg-surface-container-lowest border border-outline-variant rounded px-2">
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
              </div>

              {/* #10 — VideoTimeline: no Windows row; segments from all/selected tracks */}
              <VideoTimeline
                frameCount={active.canonical_frame_count}
                currentFrame={frame}
                segments={segments}
                selectedSegment={selectedSegment?.segment_id}
                onFrame={seek}
                onSegment={chooseSegment}
                onSegmentResize={handleSegmentResize}
              />
            </>
          )}
        </main>

        {/* ── Right sidebar ── */}
        {rightOpen && (
          <aside className="w-[360px] bg-surface-container border-l border-outline-variant flex flex-col shrink-0 min-h-0">
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
                    </div>
                    <div className="space-y-1">
                      {tracks.map((track) => {
                        const isSelected = selectedTrack === track.track_id;
                        const isChecked = mergeTrackIds.has(track.track_id);
                        return (
                          <div
                            key={track.track_id}
                            className={`rounded border p-2 ${isSelected ? 'border-primary bg-primary/10' : 'border-outline-variant'}`}
                          >
                            <div className="flex items-center gap-2">
                              {/* Checkbox for multi-merge (#8) */}
                              {tracks.length > 1 && (
                                <input
                                  type="checkbox"
                                  aria-label={`Select Worker ${track.track_id} for merge`}
                                  checked={isChecked}
                                  onChange={(e) => {
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
                                onClick={() => chooseTrack(track.track_id)}
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
                                  onClick={() => void splitVideoTrack(projectId, active.video_id, track.track_id, frame).then(() => reloadActive()).catch((r) => setError(readableError(r)))}
                                  className="panel-button flex-1"
                                >
                                  Split here
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void setVideoTrackInclusion(projectId, active.video_id, track.track_id, !track.include_in_export, track.include_in_export ? 'manual_exclusion' : undefined).then(() => reloadActive()).catch((r) => setError(readableError(r)))}
                                  className="panel-button flex-1"
                                >
                                  {track.include_in_export ? 'Exclude' : 'Restore'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (window.confirm('Delete this worker and all its segments?')) {
                                      deleteVideoTrack(projectId, active.video_id, track.track_id)
                                        .then(() => reloadActive())
                                        .catch(e => setError(readableError(e)));
                                    }
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
                      <p className="font-label text-label-caps uppercase text-on-surface-variant mb-2">Segments ({activeSegments.length})</p>
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {activeSegments.map((seg) => (
                          <div key={seg.segment_id} className={`w-full rounded text-left border overflow-hidden ${selectedSegment?.segment_id === seg.segment_id ? 'border-primary bg-primary/10' : 'border-outline-variant'}`}>
                            <button type="button" onClick={() => chooseSegment(seg)} className="w-full p-2 text-label-sm flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: LABEL_COLORS[seg.label] }} />
                              <span className="capitalize font-medium">{seg.label}</span>
                              <span className="text-on-surface-variant ml-auto">{seg.start_frame}–{seg.end_frame}</span>
                            </button>
                            {selectedSegment?.segment_id === seg.segment_id && (
                              <div className="px-2 pb-2 flex gap-2">
                                <button type="button" onClick={() => void removeSegment()} className="h-6 px-2 bg-error/10 border border-error/50 text-error rounded text-[11px] font-medium hover:bg-error/20 transition-colors">Delete</button>
                                <button type="button" disabled={frame <= seg.start_frame || frame >= seg.end_frame} onClick={() => {
                                  if (!active) return;
                                  splitVideoSegment(projectId, active.video_id, seg.segment_id, frame, revision)
                                    .then(() => refreshSegments())
                                    .catch(e => setError(readableError(e)));
                                }} className="h-6 px-2 bg-surface-container border border-outline-variant rounded text-[11px] hover:border-primary/50 disabled:opacity-40 transition-colors">Split at frame</button>
                              </div>
                            )}
                          </div>
                        ))}
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
                            {selectedSegment && (
                              <button type="button" onClick={() => void removeSegment()} className="h-8 px-3 border border-error/50 text-error rounded font-label text-label-sm">Delete</button>
                            )}
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

              {/* ── Details tab — #18: only Video info + Overlay controls ── */}
              {tab === 'details' && (
                <div className="p-3 space-y-3">
                  {/* Video info */}
                  <section className="border border-outline-variant rounded p-3">
                    <p className="font-label text-label-caps uppercase text-on-surface-variant">Video</p>
                    {active ? (
                      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 mt-2 text-label-sm">
                        <dt className="text-on-surface-variant">Duration</dt><dd>{active.duration_seconds.toFixed(1)} s</dd>
                        <dt className="text-on-surface-variant">Frames</dt><dd>{active.canonical_frame_count}</dd>
                        <dt className="text-on-surface-variant">Workers</dt><dd>{tracks.length}</dd>
                        <dt className="text-on-surface-variant">Quality</dt><dd className="capitalize">{active.quality_status.replaceAll('_', ' ')}</dd>
                        <dt className="text-on-surface-variant">Status</dt><dd className="capitalize">{active.annotation_status.replaceAll('_', ' ')}</dd>
                      </dl>
                    ) : <p className="text-label-sm text-on-surface-variant mt-2">No video selected.</p>}
                  </section>

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
                </div>
              )}
            </div>

            {/* #9 — Approve / Unapprove button at sidebar bottom */}
            {active && (
              <div className="shrink-0 p-3 border-t border-outline-variant">
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
        )}
      </div>

      {/* ── Dialogs ── */}
      <PoseHelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
      <ShortcutGuideOverlay visible={shortcutGuideVisible} />

      {/* Export modal (#9) */}
      {exportOpen && (
        <div className="fixed inset-0 z-[110] bg-black/60 flex items-center justify-center p-4" onMouseDown={() => setExportOpen(false)}>
          <section role="dialog" aria-modal="true" aria-labelledby="export-dialog-title" onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-md bg-surface-container-high border border-outline-variant rounded-lg p-5 shadow-2xl">
            <h2 id="export-dialog-title" className="font-headline-sm mb-3">Export Dataset</h2>
            <ExportPanel projectId={projectId} />
            <button type="button" onClick={() => setExportOpen(false)} className="mt-4 h-8 px-3 border border-outline-variant rounded font-label text-label-sm">Close</button>
          </section>
        </div>
      )}

      {/* Delete confirmation */}
      {pendingDelete && (
        <div className="fixed inset-0 z-[110] bg-black/60 flex items-center justify-center p-4" onMouseDown={() => !deletingId && setPendingDelete(undefined)}>
          <section role="alertdialog" aria-modal="true" aria-labelledby="delete-video-title" onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-md bg-surface-container-high border border-outline-variant rounded-lg p-5 shadow-2xl">
            <div className="flex gap-3"><AlertTriangle className="text-error shrink-0" size={22} /><div><h2 id="delete-video-title" className="font-headline-sm">Delete {pendingDelete.filename}?</h2><p className="text-body-md text-on-surface-variant mt-2">This removes the managed copy, annotations, jobs, thumbnail, and derived pose data.</p></div></div>
            <div className="flex justify-end gap-2 mt-5">
              <button type="button" disabled={Boolean(deletingId)} onClick={() => setPendingDelete(undefined)} className="h-8 px-3 border border-outline-variant rounded disabled:opacity-40">Cancel</button>
              <button type="button" disabled={Boolean(deletingId)} onClick={() => void confirmDeleteVideo()} className="h-8 px-3 bg-error-container text-on-error-container rounded flex items-center gap-2 disabled:opacity-40">{deletingId && <Loader2 size={14} className="animate-spin" />}Delete video</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
