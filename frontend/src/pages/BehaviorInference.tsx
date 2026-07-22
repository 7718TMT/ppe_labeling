import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, Film, Maximize2, Minimize2, Pause, Play,
  Trash2, Upload, Users,
} from 'lucide-react';
import { Link } from 'react-router-dom';

import {
  deleteVideo, getBehaviorInferenceResults,
  getBehaviorInferenceWorkspace, getPoseOverlay, importBehaviorInferenceVideos,
  videoMediaUrl, videoThumbnailUrl,
} from '../api/client';
import { InferenceTimeline } from '../features/video/InferenceTimeline';
import { PoseVideoPlayer } from '../features/video/PoseVideoPlayer';
import { userJobStage, userVideoStatus } from '../features/video/videoPresentation';
import type {
  BehaviorEvent, BehaviorInferenceResults, BehaviorInferenceWorkspace,
  PoseTrackFrame, VideoItem, VideoSegment,
} from '../types';

const LABEL_COLOR = { others: '#64748b', running: '#3b82f6', falling: '#ef4444' };
const STATUS_PRIORITY = { Ready: 0, Processing: 1, Failed: 2, Unprocessed: 3 };

export function orderInferenceVideos(
  videos: VideoItem[],
  jobs: BehaviorInferenceWorkspace['jobs'],
): VideoItem[] {
  return [...videos].sort((left, right) => {
    const statusDifference = (
      STATUS_PRIORITY[userVideoStatus(left, jobs)]
      - STATUS_PRIORITY[userVideoStatus(right, jobs)]
    );
    if (statusDifference !== 0) return statusDifference;
    return right.updated_at.localeCompare(left.updated_at);
  });
}

export function BehaviorInference() {
  const [workspace, setWorkspace] = useState<BehaviorInferenceWorkspace>();
  const [active, setActive] = useState<VideoItem>();
  const [results, setResults] = useState<BehaviorInferenceResults>();
  const [overlay, setOverlay] = useState<PoseTrackFrame>();
  const [frame, setFrame] = useState(0);
  const [selectedTrack, setSelectedTrack] = useState<number>();
  const [playing, setPlaying] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingVideoId, setDeletingVideoId] = useState<string>();
  const [failedThumbnails, setFailedThumbnails] = useState<Set<string>>(
    new Set(),
  );
  const [error, setError] = useState('');
  const player = useRef<HTMLVideoElement>(null);
  const fullscreenStage = useRef<HTMLDivElement>(null);
  const overlayChunks = useRef(new Map<string, PoseTrackFrame[]>());
  const [isFullscreen, setIsFullscreen] = useState(false);

  async function refresh() {
    const next = await getBehaviorInferenceWorkspace();
    const videos = orderInferenceVideos(next.videos, next.jobs);
    setWorkspace({ ...next, videos });
    setActive((current) => (
      videos.find((item) => item.video_id === current?.video_id) ?? videos[0]
    ));
  }

  useEffect(() => { void refresh().catch((reason) => setError(String(reason))); }, []);

  useEffect(() => {
    const synchronizeFullscreenState = () => {
      setIsFullscreen(document.fullscreenElement === fullscreenStage.current);
    };
    document.addEventListener('fullscreenchange', synchronizeFullscreenState);
    return () => {
      document.removeEventListener(
        'fullscreenchange',
        synchronizeFullscreenState,
      );
    };
  }, []);

  const activeJob = active && workspace?.jobs.find((job) => job.video_id === active.video_id && ['queued', 'running', 'paused'].includes(job.status));
  useEffect(() => {
    if (!activeJob) return undefined;
    const timer = window.setInterval(() => void refresh().catch(() => undefined), 1000);
    return () => window.clearInterval(timer);
  }, [activeJob?.job_id, activeJob?.status]);

  useEffect(() => {
    setFrame(0); setResults(undefined); setOverlay(undefined); setPlaying(false); setSelectedTrack(undefined); overlayChunks.current.clear();
    if (!active || active.processing_status !== 'model_suggestion_ready') return;
    void getBehaviorInferenceResults(active.video_id).then((value) => {
      setResults(value); setSelectedTrack(value.tracks[0]?.track_id);
    }).catch((reason) => setError(String(reason)));
  }, [active?.video_id, active?.processing_status]);

  useEffect(() => {
    if (!workspace || !active || !active.pose_cache_version) return;
    const start = Math.floor(frame / 120) * 120;
    const key = `${active.video_id}:${start}`;
    const cached = overlayChunks.current.get(key);
    if (cached) { setOverlay(cached.find((row) => row.frame_index === frame)); return; }
    void getPoseOverlay(workspace.project.project_id, active.video_id, start, Math.min(active.canonical_frame_count - 1, start + 119))
      .then((rows) => { overlayChunks.current.set(key, rows); setOverlay(rows.find((row) => row.frame_index === frame)); })
      .catch(() => setOverlay(undefined));
  }, [workspace?.project.project_id, active?.video_id, active?.pose_cache_version, frame]);

  const segments = useMemo<VideoSegment[]>(() => {
    if (!results) return [];
    return results.tracks.flatMap((track) => {
      const prediction = results.windows
        .filter((item) => (
          item.track_id === track.track_id
          && item.start_frame <= frame
          && item.end_frame >= frame
        ))
        .sort((left, right) => right.start_frame - left.start_frame)[0];
      if (!prediction) return [];
      return [{
        segment_id: prediction.prediction_id,
        track_id: prediction.track_id,
        start_frame: prediction.start_frame,
        end_frame: prediction.end_frame,
        label: prediction.predicted_label,
        quality_status: prediction.quality_status,
        include_in_export: 1,
        source_type: 'model',
      }];
    });
  }, [frame, results]);
  const windows = results?.windows.filter((item) => selectedTrack === undefined || item.track_id === selectedTrack) ?? [];

  function seekFrame(targetFrame: number) {
    if (!active || !player.current) return;
    setFrame(targetFrame);
    player.current.currentTime = targetFrame / active.canonical_fps;
  }

  function jump(startFrame: number, trackId: number) {
    setSelectedTrack(trackId);
    seekFrame(startFrame);
  }

  /** Toggle the combined inference player and timeline fullscreen surface. */
  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await fullscreenStage.current?.requestFullscreen();
      }
    } catch {
      setError('Fullscreen mode could not be changed.');
    }
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true); setError('');
    try { await importBehaviorInferenceVideos([...files]); await refresh(); }
    catch (reason) { setError(String(reason)); }
    finally { setUploading(false); }
  }

  async function removeVideo(video: VideoItem) {
    if (!workspace || !window.confirm(`Delete "${video.filename}"? This cannot be undone.`)) return;
    setDeletingVideoId(video.video_id); setError('');
    if (active?.video_id === video.video_id) player.current?.pause();
    try {
      await deleteVideo(workspace.project.project_id, video.video_id);
      await refresh();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setDeletingVideoId(undefined);
    }
  }

  return <div className="h-screen flex flex-col bg-background text-on-background">
    <header className="h-toolbar-height shrink-0 bg-surface-container border-b border-outline-variant flex items-center px-gutter gap-3">
      <Link to="/" className="font-bold text-primary">Home</Link><span>/</span><Link to="/behavior" className="hover:text-primary">Behavior</Link><span>/</span><span>Inference</span>
      <span className="ml-auto font-label text-label-sm text-on-surface-variant">{workspace?.model.name ?? 'Behavior model'}</span>
    </header>
    {error && <div role="alert" className="px-4 py-2 bg-error-container/40 text-error">{error}</div>}
    <div className="flex flex-1 min-h-0">
      <aside className="w-72 shrink-0 border-r border-outline-variant bg-surface-container flex flex-col">
        <div className="p-3 border-b border-outline-variant"><label className="h-9 px-3 rounded bg-primary-container text-on-primary-container flex items-center justify-center gap-2 cursor-pointer font-label text-label-sm"><Upload size={15} />{uploading ? 'Uploading…' : 'Upload videos'}<input className="sr-only" type="file" accept="video/*" multiple disabled={uploading} onChange={(event) => void upload(event.target.files)} /></label></div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">{workspace?.videos.map((video) => {
          const job = workspace.jobs.find((item) => item.video_id === video.video_id && ['queued', 'running', 'paused'].includes(item.status));
          return <div key={video.video_id} className={`w-full rounded border flex items-start transition-colors ${active?.video_id === video.video_id ? 'border-primary bg-primary/10' : 'border-transparent hover:bg-surface-container-high'}`}><button type="button" aria-label={`Open ${video.filename}`} onClick={() => setActive(video)} className="min-w-0 flex-1 text-left p-2 flex gap-2"><div className="w-20 h-14 shrink-0 rounded-sm overflow-hidden bg-black flex items-center justify-center">{failedThumbnails.has(video.video_id) ? <Film size={20} className="text-on-surface-variant" aria-label="Thumbnail unavailable" /> : <img src={videoThumbnailUrl(video.project_id, video.video_id)} alt="" loading="lazy" className="w-full h-full object-cover" onError={() => setFailedThumbnails((current) => new Set(current).add(video.video_id))} />}</div><div className="min-w-0 flex-1"><p className="truncate text-label-sm font-medium">{video.filename}</p><p className="mt-1 text-[10px] text-on-surface-variant">{job ? `${userJobStage(job.stage)} · ${Math.round(job.progress * 100)}%` : userVideoStatus(video, workspace.jobs)}</p>{job && <div className="mt-2 h-1 bg-surface-container-highest rounded"><div className="h-full bg-primary" style={{ width: `${job.progress * 100}%` }} /></div>}{video.processing_status === 'failed' && <p className="mt-2 text-[10px] text-error">{video.last_error ?? 'Processing failed. Check the application log.'}</p>}</div></button><button type="button" aria-label={`Delete ${video.filename}`} title="Delete video" disabled={deletingVideoId === video.video_id} onClick={() => void removeVideo(video)} className="m-2 p-1.5 rounded text-on-surface-variant hover:text-error hover:bg-error-container/20 disabled:opacity-50"><Trash2 size={14} /></button></div>;
        })}</div>
      </aside>

      <main className="flex-1 min-w-0 flex flex-col bg-surface-container-lowest">
        {!active ? <div className="flex-1 grid place-items-center text-on-surface-variant">Upload a video to run behavior inference.</div> : <>
          <div
            ref={fullscreenStage}
            data-testid="inference-fullscreen-stage"
            className={`flex-1 min-h-0 flex flex-col bg-surface-container-lowest ${isFullscreen ? 'h-screen w-screen' : ''}`}
          >
            <div className="flex-1 min-h-[240px] relative"><PoseVideoPlayer ref={player} projectId={workspace!.project.project_id} video={active} overlay={overlay} selectedTrack={selectedTrack} selectedOnly={false} showBoxes currentSegments={segments} currentFrame={frame} onSelectTrack={setSelectedTrack} onSeek={seekFrame} onTimeUpdate={() => setFrame(Math.min(active.canonical_frame_count - 1, Math.round((player.current?.currentTime ?? 0) * active.canonical_fps)))} playing={playing} onPlayPause={() => setPlaying((current) => { if (!player.current) return current; if (current) player.current.pause(); else void player.current.play(); return !current; })} /></div>
            <div className="h-12 shrink-0 border-t border-outline-variant flex items-center gap-3 px-4"><button type="button" aria-label={playing ? 'Pause video' : 'Play video'} className="toolbar-icon" onClick={() => { if (!player.current) return; if (playing) player.current.pause(); else void player.current.play(); setPlaying(!playing); }}>{playing ? <Pause size={16} /> : <Play size={16} />}</button><button type="button" aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} className="toolbar-icon" onClick={() => void toggleFullscreen()}>{isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}</button><span className="font-label text-label-sm">Frame {frame} / {active.canonical_frame_count - 1}</span>{activeJob && <span className="ml-auto flex items-center gap-2 text-label-sm text-primary"><Activity className="animate-spin" size={15} />{userJobStage(activeJob.stage)} {Math.round(activeJob.progress * 100)}%</span>}</div>
            <InferenceTimeline frameCount={active.canonical_frame_count} currentFrame={frame} mediaUrl={videoMediaUrl(workspace!.project.project_id, active.video_id)} tracks={results?.tracks ?? []} events={results?.events ?? []} selectedTrack={selectedTrack} onFrame={seekFrame} onSegment={(segment) => jump(segment.startFrame, segment.trackId)} />
          </div>
          <section className="h-40 border-t border-outline-variant overflow-auto p-3"><div className="flex items-center justify-between"><h2 className="font-label text-label-caps uppercase text-on-surface-variant">Raw 60-frame predictions</h2><span className="text-[10px] text-on-surface-variant">12-frame stride</span></div><div className="flex gap-1 mt-3 min-w-max">{windows.map((item) => <button key={item.prediction_id} onClick={() => jump(item.start_frame, item.track_id)} title={`${item.predicted_label} ${(item.confidence * 100).toFixed(1)}%`} className="h-16 w-16 rounded border border-outline-variant text-[10px]" style={{ borderColor: LABEL_COLOR[item.predicted_label] }}><span className="capitalize">{item.predicted_label}</span><strong className="block mt-1">{Math.round(item.confidence * 100)}%</strong><span>{item.start_frame}</span></button>)}</div></section>
        </>}
      </main>

      <aside className="w-80 shrink-0 border-l border-outline-variant bg-surface-container overflow-y-auto p-3 space-y-5">
        <section><h2 className="font-label text-label-caps uppercase text-on-surface-variant">Events</h2><div className="mt-2 space-y-2">{results?.events.length ? results.events.map((event: BehaviorEvent) => <button key={event.suggestion_id} onClick={() => jump(event.start_frame, event.track_id)} className="w-full text-left rounded border border-outline-variant p-3 hover:border-primary"><div className="flex justify-between"><strong className="capitalize" style={{ color: LABEL_COLOR[event.suggested_label] }}>{event.suggested_label}</strong><span>{Math.round(event.confidence * 100)}%</span></div><p className="text-[10px] text-on-surface-variant mt-1">Worker {event.track_id} · frames {event.start_frame}–{event.end_frame}</p></button>) : <p className="text-label-sm text-on-surface-variant">No falling or running events.</p>}</div></section>
        <section><h2 className="font-label text-label-caps uppercase text-on-surface-variant">Workers</h2>{results && results.tracks.length === 0 && <p className="mt-2 text-label-sm text-error flex gap-2"><AlertTriangle size={15} />No workers were detected. Pose quality is insufficient for behavior inference.</p>}<div className="mt-2 space-y-2">{results?.track_summaries.map((track) => <button key={track.track_id} onClick={() => jump(track.start_frame, track.track_id)} className={`w-full rounded border p-3 text-left ${selectedTrack === track.track_id ? 'border-primary' : 'border-outline-variant'}`}><div className="flex justify-between"><span className="flex gap-2"><Users size={15} />Worker {track.track_id}</span><span>{Math.round(track.avg_keypoint_confidence * 100)}%</span></div><p className="text-[10px] text-on-surface-variant mt-1">{track.falling_events} falling · {track.running_events} running</p>{track.quality_status === 'low_quality' && <p className="mt-2 text-[10px] text-error flex gap-1"><AlertTriangle size={12} />Low pose quality</p>}</button>)}</div></section>
      </aside>
    </div>
  </div>;
}
