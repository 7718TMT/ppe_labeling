import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  Eye,
  EyeOff,
  Loader2,
  Maximize2,
  PanelLeft,
  PanelRight,
  Pause,
  Play,
  Redo2,
  Save,
  SkipBack,
  SkipForward,
  Undo2,
} from 'lucide-react';

import {
  approveVideo,
  controlVideoJob,
  deleteVideo as deleteImportedVideo,
  deleteVideoSegment,
  extendVideoSegment,
  getProcessingOptions,
  getFeatures,
  getPoseOverlay,
  getSuggestions,
  getVideoJobs,
  getVideoProject,
  getVideoSegments,
  getVideoTracks,
  getVideos,
  getWindows,
  importVideos,
  labelFullVideoTrack,
  mergeVideoSegments,
  mergeVideoTracks,
  processVideo,
  reviewSuggestion,
  reviewWindow,
  saveVideoSegment,
  saveVideoWorkspaceState,
  setVideoSegmentInclusion,
  setVideoTrackInclusion,
  splitVideoSegment,
  splitVideoTrack,
  videoHistoryAction,
} from '../api/client';
import { ExportPanel } from '../features/video/ExportPanel';
import { FeatureInspector } from '../features/video/FeatureInspector';
import { PoseHelpDialog } from '../features/video/PoseHelpDialog';
import { PoseVideoPlayer } from '../features/video/PoseVideoPlayer';
import { ProcessModeButton, type ProcessMode } from '../features/video/ProcessModeButton';
import { ProcessingQueue } from '../features/video/ProcessingQueue';
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
  VideoSuggestion,
  VideoTrack,
} from '../types';

type RightTab = 'annotate' | 'suggestions' | 'details';

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'paused']);

function processModeKey(projectId: string): string {
  return `pose-process-mode:${projectId}`;
}

function initialProcessMode(projectId: string): ProcessMode {
  return sessionStorage.getItem(processModeKey(projectId)) === 'Model' ? 'Model' : 'Threshold';
}

function upsertJobRows(current: ProcessingJob[], incoming: ProcessingJob[]): ProcessingJob[] {
  const rows = new Map(current.map((job) => [job.job_id, job]));
  incoming.forEach((job) => rows.set(job.job_id, job));
  return [...rows.values()];
}

function readableError(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

export function VideoWorkspace() {
  const { projectId = '' } = useParams();
  const player = useRef<HTMLVideoElement>(null);
  const activeIdRef = useRef<string>();
  const frameRef = useRef(0);
  const activeLoadRef = useRef(0);
  const suggestionLoadRef = useRef(0);
  const projectRef = useRef<VideoProject | null>(null);
  const processingTransitionRef = useRef<{ videoId?: string; active: boolean }>({ active: false });
  const pendingMediaSeekRef = useRef<{ videoId: string; seconds: number }>();
  const workspaceSaveChainRef = useRef<Promise<unknown>>(Promise.resolve());
  const savingRequestCountRef = useRef(0);
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
  const [mergeTrackId, setMergeTrackId] = useState<number>();
  const [segments, setSegments] = useState<VideoSegment[]>([]);
  const [revision, setRevision] = useState(0);
  const [selectedSegment, setSelectedSegment] = useState<VideoSegment>();
  const [mergeSegmentId, setMergeSegmentId] = useState<string>();
  const [suggestions, setSuggestions] = useState<VideoSuggestion[]>([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState<VideoSuggestion>();
  const [source, setSource] = useState<SuggestionSource>('Threshold');
  const [processMode, setProcessMode] = useState<ProcessMode>(() => initialProcessMode(projectId));
  const [processingOptions, setProcessingOptions] = useState<ProcessingOptions>({
    threshold_available: true,
    model_available: false,
    model_message: 'Model suggestions are not configured for this project.',
  });
  const [windows, setWindows] = useState<GeneratedWindow[]>([]);
  const [features, setFeatures] = useState<FeatureWindow[]>([]);
  const [overlay, setOverlay] = useState<PoseTrackFrame>();
  const [overlayCacheRevision, setOverlayCacheRevision] = useState(0);
  const [frame, setFrame] = useState(0);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [label, setLabel] = useState<HumanVideoLabel>('others');
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);
  const [showSkeleton, setShowSkeleton] = useState(true);
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
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  projectRef.current = project;
  activeIdRef.current = active?.video_id;
  frameRef.current = frame;

  useEffect(() => () => {
    activeIdRef.current = undefined;
  }, []);

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
    refreshShell().catch((reason) => !cancelled && setError(readableError(reason)));
    const timer = window.setInterval(() => {
      Promise.all([getVideoJobs(projectId), getVideos(projectId)])
        .then(([jobRows, videoRows]) => {
          if (cancelled) return;
          setJobs(jobRows);
          setVideos(videoRows);
          setActive((current) => {
            if (!current) return videoRows[0] ?? null;
            return videoRows.find((item) => item.video_id === current.video_id) ?? videoRows[0] ?? null;
          });
        })
        .catch(() => undefined);
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [projectId, refreshShell]);

  const loadActive = useCallback(async (video: VideoItem) => {
    const generation = activeLoadRef.current + 1;
    activeLoadRef.current = generation;
    setError('');
    setMessage('');
    setPlaying(false);
    setOverlay(undefined);
    overlayCacheRef.current = {
      videoId: video.video_id,
      frames: new Map(),
      loaded: new Set(),
      pending: new Set(),
    };
    setOverlayCacheRevision((current) => current + 1);
    setTracks([]);
    setSegments([]);
    setSuggestions([]);
    setWindows([]);
    setFeatures([]);
    setSelectedTrack(undefined);
    setMergeTrackId(undefined);
    setSelectedSegment(undefined);
    setMergeSegmentId(undefined);
    setAutosaveFailedDraft(undefined);
    setSelectedSuggestion(undefined);
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
      void Promise.allSettled([
        getWindows(projectId, video.video_id),
        getFeatures(projectId, video.video_id),
      ]).then(([windowResult, featureResult]) => {
        if (generation !== activeLoadRef.current || activeIdRef.current !== video.video_id) return;
        setWindows(windowResult.status === 'fulfilled' ? windowResult.value : []);
        setFeatures(featureResult.status === 'fulfilled' ? featureResult.value : []);
      });
      const workspace = projectRef.current?.workspace_state;
      const rememberedTrack = workspace?.video_id === video.video_id ? workspace.track_id : undefined;
      const longestTrack = trackRows.slice().sort(
        (left, right) => (right.end_frame - right.start_frame) - (left.end_frame - left.start_frame),
      )[0];
      const nextTrack = trackRows.find((item) => item.track_id === rememberedTrack) ?? longestTrack;
      setSelectedTrack(nextTrack?.track_id);
      const rememberedFrame = workspace?.video_id === video.video_id ? workspace.frame_index : 0;
      const nextFrame = Math.max(0, Math.min(video.canonical_frame_count - 1, rememberedFrame ?? 0));
      setFrame(nextFrame);
      setStart(nextFrame);
      setEnd(nextFrame);
      pendingMediaSeekRef.current = {
        videoId: video.video_id,
        seconds: nextFrame / video.canonical_fps,
      };
      window.requestAnimationFrame(() => {
        if (activeIdRef.current === video.video_id && player.current) {
          try {
            player.current.currentTime = nextFrame / video.canonical_fps;
            pendingMediaSeekRef.current = undefined;
          } catch {
            // loadedmetadata will apply the pending seek through synchronizePlayer.
          }
        }
      });
    } catch (reason) {
      if (generation === activeLoadRef.current && activeIdRef.current === video.video_id) {
        setError(readableError(reason));
      }
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
      setSuggestions([]);
      setWindows([]);
      setFeatures([]);
      setOverlay(undefined);
      setPlaying(false);
    }
  }, [active?.video_id, loadActive]);

  useEffect(() => {
    const generation = suggestionLoadRef.current + 1;
    suggestionLoadRef.current = generation;
    setSelectedSuggestion(undefined);
    if (!active || source === 'Off') {
      setSuggestions([]);
      return;
    }
    const videoId = active.video_id;
    getSuggestions(projectId, videoId, source, selectedTrack)
      .then((rows) => {
        if (generation === suggestionLoadRef.current && activeIdRef.current === videoId) setSuggestions(rows);
      })
      .catch(() => {
        if (generation === suggestionLoadRef.current && activeIdRef.current === videoId) setSuggestions([]);
      });
  }, [active?.video_id, source, selectedTrack, projectId]);

  useEffect(() => {
    if (!active) {
      setOverlay(undefined);
      return;
    }
    const videoId = active.video_id;
    const requestedFrame = frame;
    let cache = overlayCacheRef.current;
    if (cache.videoId !== videoId) {
      cache = { videoId, frames: new Map(), loaded: new Set(), pending: new Set() };
      overlayCacheRef.current = cache;
    }
    if (cache.loaded.has(requestedFrame)) {
      setOverlay(cache.frames.get(requestedFrame));
      return;
    }
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
      if (activeIdRef.current === videoId) {
        setOverlay(currentCache.frames.get(frameRef.current));
      }
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
    const payload = {
      video_id: videoId,
      track_id: selectedTrack,
      frame_index: frame,
      suggestion_source: source,
    };
    const timer = window.setTimeout(() => {
      workspaceSaveChainRef.current = workspaceSaveChainRef.current
        .catch(() => undefined)
        .then(() => saveVideoWorkspaceState(projectId, payload))
        .catch(() => {
          if (activeIdRef.current === videoId) {
            setError('Workspace recovery state could not be saved. Your committed annotations are unchanged.');
          }
        });
    }, 500);
    return () => window.clearTimeout(timer);
  }, [active?.video_id, selectedTrack, frame, source, projectId]);

  useEffect(() => {
    sessionStorage.setItem(processModeKey(projectId), processMode);
  }, [processMode, projectId]);

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
      try {
        await element.play();
        setPlaying(true);
      } catch {
        setPlaying(false);
        setError('The video could not start. Try selecting it again.');
      }
    } else {
      element.pause();
      setPlaying(false);
    }
  }

  function synchronizePlayer() {
    const element = player.current;
    const currentVideo = active;
    if (!element || !currentVideo) return;
    const pendingSeek = pendingMediaSeekRef.current;
    if (pendingSeek?.videoId === currentVideo.video_id) {
      try {
        element.currentTime = pendingSeek.seconds;
        pendingMediaSeekRef.current = undefined;
      } catch {
        return;
      }
    }
    const current = Math.max(
      0,
      Math.min(currentVideo.canonical_frame_count - 1, Math.round(element.currentTime * currentVideo.canonical_fps)),
    );
    if (loop && selectedSegment && current >= selectedSegment.end_frame && !element.ended) {
      seek(selectedSegment.start_frame);
      void element.play();
      return;
    }
    setFrame(current);
    setPlaying(!element.paused && !element.ended);
  }

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
        track_id: selectedTrack,
        start_frame: start,
        end_frame: end,
        label,
        expected_revision: revision,
      }, selectedSegment?.segment_id);
      if (activeIdRef.current === videoId) {
        setRevision(result.revision);
        setSegments((current) => [
          ...current.filter((item) => item.segment_id !== result.segment.segment_id),
          result.segment,
        ].sort((left, right) => left.start_frame - right.start_frame));
        setSelectedSegment((current) => {
          if (!segmentAtSave) return result.segment;
          return current?.segment_id === segmentAtSave.segment_id ? result.segment : current;
        });
        setAutosaveFailedDraft(undefined);
        if (!autosave) setMessage('Segment saved.');
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) {
        if (attemptedDraft) setAutosaveFailedDraft(attemptedDraft);
        setError(`${autosave ? 'Autosave' : 'Save'} failed. The annotation may have changed elsewhere; reload before retrying. ${readableError(reason)}`);
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
        setMessage('Segment deleted.');
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
      setMessage(action === 'undo' ? 'Undone.' : 'Redone.');
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    }
  }

  async function suggestionAction(action: 'accept' | 'modify' | 'reject') {
    if (!active || !selectedSuggestion || source === 'Off') return;
    const videoId = active.video_id;
    try {
      const changes = action === 'modify'
        ? { track_id: selectedTrack, start_frame: start, end_frame: end, label }
        : undefined;
      const result = await reviewSuggestion(
        projectId,
        videoId,
        source,
        selectedSuggestion.suggestion_id,
        action,
        revision,
        changes,
      );
      if (activeIdRef.current !== videoId) return;
      if (result.revision) setRevision(result.revision);
      if (result.segment) {
        setSegments((current) => [
          ...current.filter((item) => item.segment_id !== result.segment.segment_id),
          result.segment,
        ]);
      }
      setSuggestions((current) => current.map((item) => (
        item.suggestion_id === selectedSuggestion.suggestion_id
          ? { ...item, review_status: action === 'modify' ? 'modified' : action === 'accept' ? 'accepted' : 'rejected' }
          : item
      )));
      setSelectedSuggestion(undefined);
      setMessage(action === 'reject' ? 'Suggestion rejected.' : 'Suggestion copied to human annotations.');
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    }
  }

  async function toggleSegmentInclusion() {
    if (!active || !selectedSegment) return;
    const videoId = active.video_id;
    try {
      const include = !selectedSegment.include_in_export;
      const result = await setVideoSegmentInclusion(
        projectId,
        videoId,
        selectedSegment.segment_id,
        include,
        revision,
        include ? undefined : 'manual_exclusion',
      );
      if (activeIdRef.current !== videoId) return;
      setRevision(result.revision);
      setSegments((rows) => rows.map((item) => item.segment_id === result.segment.segment_id ? result.segment : item));
      setSelectedSegment(result.segment);
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(readableError(reason));
    }
  }

  async function approveAndNext() {
    if (!active) return;
    const videoId = active.video_id;
    try {
      await approveVideo(projectId, videoId);
      const index = videos.findIndex((item) => item.video_id === videoId);
      const next = videos.slice(index + 1).find((item) => !item.is_approved) ?? videos[index + 1] ?? null;
      setVideos((current) => current.map((item) => item.video_id === videoId
        ? { ...item, is_approved: 1, annotation_status: 'approved' }
        : item));
      if (activeIdRef.current === videoId && next) setActive(next);
      setMessage('Video completed.');
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
  }

  async function reloadActive(video = active) {
    if (!video) return;
    await loadActive(video);
  }

  function chooseSegment(segment: VideoSegment) {
    setSelectedSegment(segment);
    setMergeSegmentId(undefined);
    setSelectedSuggestion(undefined);
    setSelectedTrack(segment.track_id);
    setStart(segment.start_frame);
    setEnd(segment.end_frame);
    setLabel(segment.label);
    seek(segment.start_frame);
    setTab('annotate');
  }

  function chooseTrack(trackId: number) {
    setSelectedTrack(trackId);
    setMergeTrackId(undefined);
    setSelectedSegment(undefined);
    setMergeSegmentId(undefined);
    setSelectedSuggestion(undefined);
  }

  function chooseSuggestion(item: VideoSuggestion) {
    setSelectedSuggestion(item);
    setSelectedSegment(undefined);
    setSelectedTrack(item.track_id);
    setStart(item.start_frame);
    setEnd(item.end_frame);
    setLabel(item.suggested_label);
    seek(item.start_frame);
    setTab('suggestions');
  }

  async function handleProcess() {
    if (!active) return;
    const videoId = active.video_id;
    setProcessingRequests((current) => new Set(current).add(videoId));
    setError('');
    try {
      const rows = await processVideo(projectId, videoId, processMode);
      setJobs((current) => upsertJobRows(current, rows));
      if (activeIdRef.current === videoId) {
        setSource(processMode === 'Threshold' ? 'Threshold' : 'AI');
        setMessage(`${processMode} processing started.`);
      }
    } catch (reason) {
      if (activeIdRef.current === videoId) setError(`Processing could not start. ${readableError(reason)}`);
    } finally {
      setProcessingRequests((current) => {
        const next = new Set(current);
        next.delete(videoId);
        return next;
      });
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
      // Let React unmount the media element so Windows can release any active
      // range response before the managed raw copy is staged for deletion.
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
      const rows = await importVideos(projectId, files);
      setVideos((current) => {
        const existing = new Set(current.map((item) => item.video_id));
        return [...current, ...rows.filter((item) => !existing.has(item.video_id))];
      });
      if (!active && rows[0]) setActive(rows[0]);
      setMessage(`${rows.length} video${rows.length === 1 ? '' : 's'} imported.`);
      await refreshShell();
    } catch (reason) {
      setError(`Import failed. ${readableError(reason)}`);
    }
  }

  useEffect(() => {
    function key(event: KeyboardEvent) {
      if (helpOpen || pendingDelete) return;
      const target = event.target as HTMLElement;
      if (
        target.isContentEditable
        || target.closest('input, textarea, select, button, a, [contenteditable="true"]')
      ) return;
      if (event.ctrlKey && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        void history('undo');
        return;
      }
      if (event.ctrlKey && event.key.toLowerCase() === 'y') {
        event.preventDefault();
        void history('redo');
        return;
      }
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
        a: () => void suggestionAction('accept'),
        r: () => void suggestionAction('reject'),
        x: () => void toggleSegmentInclusion(),
        Enter: () => void saveSegment(),
        n: () => void approveAndNext(),
      };
      const action = actions[event.key] ?? actions[event.key.toLowerCase()];
      if (action) {
        event.preventDefault();
        action();
      }
    }
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  });

  const modelAvailable = processingOptions.model_available;
  const activeTrack = tracks.find((item) => item.track_id === selectedTrack);
  const draftDirty = Boolean(
    selectedSegment
      && (
        selectedSegment.track_id !== selectedTrack
        || selectedSegment.start_frame !== start
        || selectedSegment.end_frame !== end
        || selectedSegment.label !== label
      ),
  );
  const draftSignature = selectedSegment && active
    ? `${active.video_id}:${selectedSegment.segment_id}:${selectedTrack}:${start}:${end}:${label}:${revision}`
    : undefined;
  const activeFeatures = features.filter((item) => selectedTrack === undefined || item.track_id === selectedTrack);
  const activeWindows = windows.filter((item) => selectedTrack === undefined || item.track_id === selectedTrack);
  const activeProcessing = Boolean(active && jobs.some(
    (job) => job.video_id === active.video_id && ACTIVE_JOB_STATUSES.has(job.status),
  ));
  const activePipelineJob = active && jobs.find(
    (job) => job.video_id === active.video_id && ACTIVE_JOB_STATUSES.has(job.status),
  );
  const displayedProcessMode: ProcessMode = activePipelineJob?.target_mode === 'model'
    ? 'Model'
    : activePipelineJob?.target_mode === 'threshold' ? 'Threshold' : processMode;

  useEffect(() => {
    const videoId = active?.video_id;
    const previous = processingTransitionRef.current;
    processingTransitionRef.current = { videoId, active: activeProcessing };
    if (!videoId || activeProcessing || previous.videoId !== videoId || !previous.active) return;

    overlayCacheRef.current = { videoId, frames: new Map(), loaded: new Set(), pending: new Set() };
    setOverlay(undefined);
    setOverlayCacheRevision((current) => current + 1);

    const suggestionRequest = source === 'Off'
      ? Promise.resolve([] as VideoSuggestion[])
      : getSuggestions(projectId, videoId, source, selectedTrack);
    Promise.all([
      getVideoTracks(projectId, videoId),
      getVideoSegments(projectId, videoId),
      getWindows(projectId, videoId),
      getFeatures(projectId, videoId),
      suggestionRequest,
    ]).then(([trackRows, segmentData, windowRows, featureRows, suggestionRows]) => {
      if (activeIdRef.current !== videoId) return;
      setTracks(trackRows);
      setSelectedTrack((current) => {
        if (current !== undefined && trackRows.some((track) => track.track_id === current)) return current;
        return trackRows.slice().sort(
          (left, right) => (right.end_frame - right.start_frame) - (left.end_frame - left.start_frame),
        )[0]?.track_id;
      });
      setSegments(segmentData.segments);
      setRevision(segmentData.revision);
      setSelectedSegment((current) => (
        current
          ? segmentData.segments.find((segment) => segment.segment_id === current.segment_id)
          : undefined
      ));
      setWindows(windowRows);
      setFeatures(featureRows);
      setSuggestions(suggestionRows);
    }).catch(() => {
      if (activeIdRef.current === videoId) {
        setError('Processing finished, but its new results could not be loaded. Select the video again.');
      }
    });
  }, [active?.video_id, activeProcessing, projectId, selectedTrack, source]);

  useEffect(() => {
    if (!draftDirty || !draftSignature || saving || autosaveFailedDraft === draftSignature) return undefined;
    const timer = window.setTimeout(() => void saveSegment(true), 700);
    return () => window.clearTimeout(timer);
  }, [autosaveFailedDraft, draftDirty, draftSignature, saving]);

  const selectedVideoIndex = videos.findIndex((item) => item.video_id === active?.video_id);
  const pendingSuggestions = useMemo(
    () => suggestions.filter((item) => item.review_status === 'pending'),
    [suggestions],
  );

  return (
    <div className="h-screen bg-background text-on-background flex flex-col overflow-hidden">
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
          <button type="button" title="Undo" onClick={() => void history('undo')} className="toolbar-icon"><Undo2 size={17} /></button>
          <button type="button" title="Redo" onClick={() => void history('redo')} className="toolbar-icon"><Redo2 size={17} /></button>
          <button type="button" title="Previous video" disabled={selectedVideoIndex <= 0} onClick={() => setActive(videos[selectedVideoIndex - 1])} className="toolbar-icon disabled:opacity-30"><ChevronLeft size={17} /></button>
          <button type="button" title="Next video" disabled={selectedVideoIndex < 0 || selectedVideoIndex >= videos.length - 1} onClick={() => setActive(videos[selectedVideoIndex + 1])} className="toolbar-icon disabled:opacity-30"><ChevronRight size={17} /></button>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="hidden xl:flex font-label text-label-sm text-on-surface-variant gap-1 items-center">
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            {saving ? 'Saving…' : draftDirty ? 'Unsaved changes' : 'Saved'}
          </span>
          <button type="button" onClick={() => setHelpOpen(true)} className="h-8 px-2 border border-outline-variant rounded font-label text-label-sm flex items-center gap-1"><HelpCircle size={15} />Help</button>
          <ProcessModeButton
            mode={displayedProcessMode}
            disabled={!active}
            processing={Boolean(active && processingRequests.has(active.video_id)) || activeProcessing}
            modelAvailable={modelAvailable}
            modelUnavailableReason={processingOptions.model_message ?? 'Model suggestions are unavailable.'}
            onModeChange={setProcessMode}
            onProcess={() => void handleProcess()}
          />
          <button type="button" disabled={!active} onClick={() => void approveAndNext()} className="h-8 px-3 bg-primary-container text-on-primary-container rounded font-label text-label-sm font-bold flex items-center gap-2 disabled:opacity-40"><Check size={15} /><span className="hidden sm:inline">Complete & Next</span></button>
          <button type="button" aria-label="Toggle inspector" onClick={() => setRightOpen(!rightOpen)} className="toolbar-icon"><PanelRight size={18} /></button>
        </div>
      </header>

      {(error || message) && (
        <div className={`px-4 py-2 text-label-sm border-b ${error ? 'bg-error-container/40 border-error/40 text-error' : 'bg-primary/10 border-primary/30'}`} role={error ? 'alert' : 'status'}>
          {error || message}
          <button type="button" aria-label="Dismiss message" className="float-right" onClick={() => { setError(''); setMessage(''); }}>×</button>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
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

        <main className="flex-1 min-w-0 flex flex-col bg-surface-container-lowest">
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
                  showSkeleton={showSkeleton}
                  showBoxes={showBoxes}
                  onSelectTrack={chooseTrack}
                  onTimeUpdate={synchronizePlayer}
                  onMediaError={() => setError('This video format is unsupported or the media file is damaged. Annotations and pose data are still available.')}
                />
              </div>
              <div className="h-12 bg-surface-container border-t border-outline-variant flex items-center justify-center gap-2 px-3">
                <button type="button" title="Back 10 frames" onClick={() => seek(frame - 10)} className="toolbar-icon"><SkipBack size={17} /></button>
                <button type="button" title={playing ? 'Pause' : 'Play'} onClick={() => void togglePlay()} className="w-8 h-8 bg-primary-container text-on-primary-container rounded flex items-center justify-center">{playing ? <Pause size={17} /> : <Play size={17} />}</button>
                <button type="button" title="Forward 10 frames" onClick={() => seek(frame + 10)} className="toolbar-icon"><SkipForward size={17} /></button>
                <input aria-label="Current frame" type="number" min={0} max={active.canonical_frame_count - 1} value={frame} onChange={(event) => seek(Number(event.target.value))} className="w-24 h-8 bg-surface-container-lowest border border-outline-variant rounded px-2 font-label text-label-sm" />
                <span className="font-label text-label-sm text-on-surface-variant">/ {active.canonical_frame_count - 1}</span>
                <select aria-label="Playback speed" defaultValue="1" onChange={(event) => { if (player.current) player.current.playbackRate = Number(event.target.value); }} className="h-8 bg-surface-container-lowest border border-outline-variant rounded px-2">
                  <option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1">1×</option><option value="2">2×</option>
                </select>
                <button type="button" onClick={() => setLoop(!loop)} className={`h-8 px-2 border rounded text-label-sm ${loop ? 'border-primary text-primary' : 'border-outline-variant'}`}>Loop segment</button>
                <button type="button" title="Toggle boxes" onClick={() => setShowBoxes(!showBoxes)} className="toolbar-icon">{showBoxes ? <Eye size={16} /> : <EyeOff size={16} />}</button>
                <button type="button" title="Fullscreen" onClick={() => void player.current?.parentElement?.requestFullscreen()} className="toolbar-icon"><Maximize2 size={16} /></button>
              </div>
              <VideoTimeline
                frameCount={active.canonical_frame_count}
                currentFrame={frame}
                segments={segments.filter((item) => selectedTrack === undefined || item.track_id === selectedTrack)}
                suggestions={suggestions}
                windows={activeWindows}
                source={source}
                selectedSegment={selectedSegment?.segment_id}
                onFrame={seek}
                onSegment={chooseSegment}
                onSuggestion={chooseSuggestion}
              />
            </>
          )}
        </main>

        {rightOpen && (
          <aside className="w-[360px] bg-surface-container border-l border-outline-variant flex flex-col shrink-0 min-h-0">
            <div className="grid grid-cols-3 border-b border-outline-variant">
              {(['annotate', 'suggestions', 'details'] as RightTab[]).map((name) => (
                <button type="button" key={name} onClick={() => setTab(name)} className={`h-10 capitalize font-label text-label-sm border-b-2 ${tab === name ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant'}`}>{name}</button>
              ))}
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto">
              {tab === 'annotate' && (
                <div className="p-3 space-y-4">
                  <section>
                    <p className="font-label text-label-caps uppercase text-on-surface-variant mb-2">Worker track</p>
                    <div className="space-y-1">
                      {tracks.map((track) => (
                        <button type="button" key={track.track_id} onClick={() => chooseTrack(track.track_id)} className={`w-full border rounded p-2 text-left ${selectedTrack === track.track_id ? 'border-primary bg-primary/10' : 'border-outline-variant'}`}>
                          <div className="flex justify-between"><span>Track {track.track_id}</span><span className="font-label text-label-sm">{Math.round(track.avg_keypoint_confidence * 100)}% pose quality</span></div>
                          <p className="text-[10px] text-on-surface-variant mt-1">Frames {track.start_frame}–{track.end_frame}</p>
                        </button>
                      ))}
                      {tracks.length === 0 && <p className="text-label-sm text-on-surface-variant">Process the video to detect worker tracks.</p>}
                    </div>
                  </section>
                  <label className="flex items-center gap-2 text-label-sm"><input type="checkbox" checked={selectedOnly} onChange={(event) => setSelectedOnly(event.target.checked)} />Show selected worker only</label>
                  {active && activeTrack && (
                    <div className="grid grid-cols-3 gap-1">
                      <select
                        aria-label="Worker to merge"
                        value={mergeTrackId ?? ''}
                        onChange={(event) => setMergeTrackId(event.target.value ? Number(event.target.value) : undefined)}
                        className="panel-button col-span-2"
                      >
                        <option value="">Choose worker to merge</option>
                        {tracks.filter((track) => track.track_id !== activeTrack.track_id).map((track) => (
                          <option key={track.track_id} value={track.track_id}>Worker {track.track_id}</option>
                        ))}
                      </select>
                      <button type="button" disabled={mergeTrackId === undefined} onClick={() => {
                        if (mergeTrackId !== undefined) void mergeVideoTracks(projectId, active.video_id, activeTrack.track_id, mergeTrackId).then(() => reloadActive()).catch((reason) => setError(readableError(reason)));
                      }} className="panel-button disabled:opacity-40">Merge</button>
                      <button type="button" onClick={() => void splitVideoTrack(projectId, active.video_id, activeTrack.track_id, frame).then(() => reloadActive()).catch((reason) => setError(readableError(reason)))} className="panel-button">Split here</button>
                      <button type="button" onClick={() => void setVideoTrackInclusion(projectId, active.video_id, activeTrack.track_id, !activeTrack.include_in_export, activeTrack.include_in_export ? 'manual_exclusion' : undefined).then(() => reloadActive()).catch((reason) => setError(readableError(reason)))} className="panel-button">{activeTrack.include_in_export ? 'Exclude' : 'Restore'}</button>
                    </div>
                  )}
                  <section className="border-t border-outline-variant pt-3">
                    <p className="font-label text-label-caps uppercase text-on-surface-variant mb-2">Segment</p>
                    <div className="grid grid-cols-2 gap-2">
                      <label className="text-label-sm">Start<input aria-label="Start" type="number" value={start} onChange={(event) => setStart(Number(event.target.value))} className="editor-input" /></label>
                      <label className="text-label-sm">End<input aria-label="End" type="number" value={end} onChange={(event) => setEnd(Number(event.target.value))} className="editor-input" /></label>
                    </div>
                    {active && (
                      <>
                        <input aria-label="Drag start boundary" type="range" min={activeTrack?.start_frame ?? 0} max={activeTrack?.end_frame ?? active.canonical_frame_count - 1} value={start} onChange={(event) => setStart(Math.min(Number(event.target.value), end))} onPointerUp={() => selectedSegment && void saveSegment()} className="w-full mt-2" />
                        <input aria-label="Drag end boundary" type="range" min={activeTrack?.start_frame ?? 0} max={activeTrack?.end_frame ?? active.canonical_frame_count - 1} value={end} onChange={(event) => setEnd(Math.max(Number(event.target.value), start))} onPointerUp={() => selectedSegment && void saveSegment()} className="w-full" />
                      </>
                    )}
                    <div className="grid grid-cols-3 gap-1 mt-2">
                      {(['others', 'running', 'falling'] as HumanVideoLabel[]).map((value) => (
                        <button type="button" key={value} onClick={() => setLabel(value)} className={`h-8 rounded border text-label-sm capitalize ${label === value ? 'border-primary bg-primary/10' : 'border-outline-variant'}`}>{value}</button>
                      ))}
                    </div>
                    <div className="flex gap-2 mt-3">
                      <button type="button" onClick={() => void saveSegment()} className="h-8 px-3 bg-primary-container text-on-primary-container rounded flex-1">{selectedSegment ? 'Update' : 'Create'} segment</button>
                      {selectedSegment && <button type="button" onClick={() => void removeSegment()} className="h-8 px-3 border border-error/50 text-error rounded">Delete</button>}
                    </div>
                    {active && activeTrack && (
                      <div className="grid grid-cols-3 gap-1 mt-2">
                        <button type="button" className="panel-button" onClick={() => void labelFullVideoTrack(projectId, active.video_id, activeTrack.track_id, label, revision).then(() => refreshSegments()).catch((reason) => setError(readableError(reason)))}>Full track</button>
                        <button type="button" disabled={!selectedSegment} className="panel-button disabled:opacity-40" onClick={() => selectedSegment && void splitVideoSegment(projectId, active.video_id, selectedSegment.segment_id, frame, revision).then(() => refreshSegments()).catch((reason) => setError(readableError(reason)))}>Split</button>
                        <button type="button" disabled={!selectedSegment} className="panel-button disabled:opacity-40" onClick={() => selectedSegment && void extendVideoSegment(projectId, active.video_id, selectedSegment.segment_id, revision).then(() => refreshSegments()).catch((reason) => setError(readableError(reason)))}>Extend</button>
                        <button type="button" className="panel-button" onClick={() => {
                          const previous = segments.filter((item) => item.track_id === activeTrack.track_id && item.end_frame < start).sort((left, right) => right.end_frame - left.end_frame)[0];
                          if (previous) setLabel(previous.label);
                        }}>Copy previous</button>
                        <select
                          aria-label="Adjacent segment to merge"
                          disabled={!selectedSegment}
                          value={mergeSegmentId ?? ''}
                          onChange={(event) => setMergeSegmentId(event.target.value || undefined)}
                          className="panel-button col-span-2 disabled:opacity-40"
                        >
                          <option value="">Choose adjacent segment</option>
                          {segments.filter((item) => (
                            selectedSegment
                            && item.segment_id !== selectedSegment.segment_id
                            && item.track_id === selectedSegment.track_id
                            && item.label === selectedSegment.label
                            && (item.end_frame + 1 === selectedSegment.start_frame || selectedSegment.end_frame + 1 === item.start_frame)
                          )).map((item) => (
                            <option key={item.segment_id} value={item.segment_id}>Frames {item.start_frame}–{item.end_frame}</option>
                          ))}
                        </select>
                        <button type="button" disabled={!selectedSegment || !mergeSegmentId} className="panel-button disabled:opacity-40" onClick={() => {
                          if (selectedSegment && mergeSegmentId) void mergeVideoSegments(projectId, active.video_id, [selectedSegment.segment_id, mergeSegmentId], revision).then(() => refreshSegments()).catch((reason) => setError(readableError(reason)));
                        }}>Merge</button>
                        <button type="button" disabled={!selectedSegment} className="panel-button disabled:opacity-40" onClick={() => void toggleSegmentInclusion()}>{selectedSegment?.include_in_export ? 'Exclude' : 'Include'}</button>
                      </div>
                    )}
                  </section>
                </div>
              )}

              {tab === 'suggestions' && (
                <div className="p-3 space-y-4">
                  <section>
                    <p className="font-label text-label-caps uppercase text-on-surface-variant mb-2">Show suggestions</p>
                    <div className="flex bg-surface-container-lowest border border-outline-variant rounded p-0.5">
                      {(['Off', 'Threshold', 'AI'] as SuggestionSource[]).map((value) => {
                        const disabled = value === 'AI' && !modelAvailable;
                        return (
                          <button
                            type="button"
                            key={value}
                            disabled={disabled}
                            title={disabled ? processingOptions.model_message ?? 'Model suggestions are unavailable.' : undefined}
                            onClick={() => setSource(value)}
                            className={`flex-1 h-7 rounded text-label-sm disabled:opacity-40 ${source === value ? 'bg-primary-container text-on-primary-container' : 'text-on-surface-variant'}`}
                          >{value}</button>
                        );
                      })}
                    </div>
                    <p className="text-[10px] text-on-surface-variant mt-2">Suggestions are review aids and never replace human labels automatically.</p>
                  </section>
                  {source === 'Off' ? (
                    <p className="text-body-md text-on-surface-variant">Choose Threshold or AI to review generated suggestions.</p>
                  ) : pendingSuggestions.length === 0 ? (
                    <p className="text-body-md text-on-surface-variant">No pending {source === 'AI' ? 'model' : 'threshold'} suggestions for this worker.</p>
                  ) : (
                    <section className="space-y-2">
                      {pendingSuggestions.map((item) => (
                        <button type="button" key={item.suggestion_id} onClick={() => chooseSuggestion(item)} className={`w-full p-2 rounded text-left border ${source === 'AI' ? 'border-dashed border-blue-400/70' : 'border-amber-400/60'} ${selectedSuggestion?.suggestion_id === item.suggestion_id ? 'bg-primary/10 ring-1 ring-primary' : ''}`}>
                          <div className="flex justify-between"><span className="capitalize font-medium">{item.suggested_label}</span><span>{Math.round(item.confidence * 100)}%</span></div>
                          <p className="text-label-sm text-on-surface-variant">Frames {item.start_frame}–{item.end_frame}</p>
                        </button>
                      ))}
                    </section>
                  )}
                  {selectedSuggestion && (
                    <section className={`p-3 border rounded ${source === 'AI' ? 'border-dashed border-blue-400' : 'border-amber-400/60'}`}>
                      <p className="capitalize">{selectedSuggestion.suggested_label} · {Math.round(selectedSuggestion.confidence * 100)}%</p>
                      <p className="text-label-sm text-on-surface-variant">Adjust frames or class in Annotate before Modify.</p>
                      <details className="mt-2 text-label-sm">
                        <summary className="cursor-pointer text-primary">Why this suggestion?</summary>
                        <div className="mt-2 space-y-2 text-on-surface-variant">
                          {selectedSuggestion.triggered_conditions?.length ? (
                            <ul className="list-disc pl-4">
                              {selectedSuggestion.triggered_conditions.map((condition) => <li key={condition}>{condition}</li>)}
                            </ul>
                          ) : null}
                          {selectedSuggestion.supporting_features && Object.keys(selectedSuggestion.supporting_features).length > 0 && (
                            <dl className="grid grid-cols-2 gap-x-2">
                              {Object.entries(selectedSuggestion.supporting_features).map(([name, value]) => (
                                <div key={name} className="contents"><dt>{name.replaceAll('_', ' ')}</dt><dd>{Number(value).toFixed(2)}</dd></div>
                              ))}
                            </dl>
                          )}
                          {selectedSuggestion.probabilities && Object.keys(selectedSuggestion.probabilities).length > 0 && (
                            <dl className="grid grid-cols-2 gap-x-2">
                              {Object.entries(selectedSuggestion.probabilities).map(([name, value]) => (
                                <div key={name} className="contents"><dt className="capitalize">{name}</dt><dd>{Math.round(Number(value) * 100)}%</dd></div>
                              ))}
                            </dl>
                          )}
                          {!selectedSuggestion.triggered_conditions?.length
                            && !Object.keys(selectedSuggestion.supporting_features ?? {}).length
                            && !Object.keys(selectedSuggestion.probabilities ?? {}).length
                            && <p>No additional explanation was provided.</p>}
                        </div>
                      </details>
                      <div className="grid grid-cols-3 gap-2 mt-3">
                        <button type="button" onClick={() => void suggestionAction('accept')} className="panel-button">Accept</button>
                        <button type="button" onClick={() => void suggestionAction('modify')} className="panel-button">Modify</button>
                        <button type="button" onClick={() => void suggestionAction('reject')} className="panel-button">Reject</button>
                      </div>
                    </section>
                  )}
                </div>
              )}

              {tab === 'details' && (
                <div className="p-3 space-y-3">
                  <section className="border border-outline-variant rounded p-3">
                    <p className="font-label text-label-caps uppercase text-on-surface-variant">Video</p>
                    {active ? (
                      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 mt-2 text-label-sm">
                        <dt className="text-on-surface-variant">Duration</dt><dd>{active.duration_seconds.toFixed(1)} seconds</dd>
                        <dt className="text-on-surface-variant">Frames</dt><dd>{active.canonical_frame_count}</dd>
                        <dt className="text-on-surface-variant">Workers</dt><dd>{tracks.length}</dd>
                        <dt className="text-on-surface-variant">Quality</dt><dd className="capitalize">{active.quality_status.replaceAll('_', ' ')}</dd>
                      </dl>
                    ) : <p className="text-label-sm text-on-surface-variant mt-2">No video selected.</p>}
                  </section>
                  {activeTrack && (
                    <section className="border border-outline-variant rounded p-3">
                      <p className="font-label text-label-caps uppercase text-on-surface-variant">Selected worker</p>
                      <p className="mt-2">Track {activeTrack.track_id}</p>
                      <p className="text-label-sm text-on-surface-variant mt-1">Pose quality {Math.round(activeTrack.avg_keypoint_confidence * 100)}% · valid frames {Math.round(activeTrack.valid_frame_ratio * 100)}%</p>
                    </section>
                  )}
                  <section className="border border-outline-variant rounded p-3 space-y-2">
                    <p className="font-label text-label-caps uppercase text-on-surface-variant">Overlay</p>
                    <label className="flex items-center gap-2 text-label-sm"><input type="checkbox" checked={showBoxes} onChange={(event) => setShowBoxes(event.target.checked)} />Worker boxes and IDs</label>
                    <label className="flex items-center gap-2 text-label-sm"><input type="checkbox" checked={showSkeleton} onChange={(event) => setShowSkeleton(event.target.checked)} />Pose skeleton</label>
                    <label className="flex items-center gap-2 text-label-sm"><input type="checkbox" checked={selectedOnly} onChange={(event) => setSelectedOnly(event.target.checked)} />Selected worker only</label>
                  </section>
                  <details className="border border-outline-variant rounded">
                    <summary className="p-3 cursor-pointer font-medium">Window review ({activeWindows.length})</summary>
                    <div className="p-3 pt-0 space-y-2">
                      {activeWindows.length === 0 && <p className="text-label-sm text-on-surface-variant">No windows generated yet.</p>}
                      {activeWindows.map((windowItem) => (
                        <div key={windowItem.window_id} className="border-t border-outline-variant pt-2">
                          <div className="flex justify-between"><span>{windowItem.start_frame}–{windowItem.end_frame}</span><span className="capitalize">{windowItem.label ?? 'Unresolved'}</span></div>
                          <p className="text-label-sm text-on-surface-variant">{windowItem.include_in_export ? 'Included' : 'Excluded'}</p>
                          {active && <button type="button" className="panel-button mt-2" onClick={() => void reviewWindow(projectId, active.video_id, windowItem.window_id, !windowItem.include_in_export, windowItem.include_in_export ? 'manual_exclusion' : undefined).then((updated) => setWindows((rows) => rows.map((item) => item.window_id === updated.window_id ? updated : item))).catch((reason) => setError(readableError(reason)))}>{windowItem.include_in_export ? 'Exclude' : 'Include'}</button>}
                        </div>
                      ))}
                    </div>
                  </details>
                  <details className="border border-outline-variant rounded">
                    <summary className="p-3 cursor-pointer font-medium">Motion details</summary>
                    <FeatureInspector features={activeFeatures} frame={frame} />
                  </details>
                  <details className="border border-outline-variant rounded">
                    <summary className="p-3 cursor-pointer font-medium">Export dataset</summary>
                    <ExportPanel projectId={projectId} />
                  </details>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      <PoseHelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} />

      {pendingDelete && (
        <div className="fixed inset-0 z-[110] bg-black/60 flex items-center justify-center p-4" onMouseDown={() => !deletingId && setPendingDelete(undefined)}>
          <section role="alertdialog" aria-modal="true" aria-labelledby="delete-video-title" onMouseDown={(event) => event.stopPropagation()} className="w-full max-w-md bg-surface-container-high border border-outline-variant rounded-lg p-5 shadow-2xl">
            <div className="flex gap-3"><AlertTriangle className="text-error shrink-0" size={22} /><div><h2 id="delete-video-title" className="font-headline-sm text-headline-sm">Delete {pendingDelete.filename}?</h2><p className="text-body-md text-on-surface-variant mt-2">This removes the copy managed by this project, its annotations, jobs, thumbnail, and derived pose data. It does not delete an external original outside this project.</p></div></div>
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
