import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';

interface TrimRange {
  start: number;
  end: number;
}

interface Props {
  frameCount: number;
  currentFrame: number;
  mediaUrl: string;
  range: TrimRange;
  minimumRange?: number;
  onFrame: (frame: number) => void;
  onRangeCommit: (range: TrimRange) => void;
}

interface DragState {
  edge: 'start' | 'end';
}

const PREVIEW_COUNT = 12;

/**
 * Dedicated media trim timeline. It intentionally has no annotation rows: the
 * thumbnails represent the raw video that will be written when saved.
 */
export function TrimTimeline({ frameCount, currentFrame, mediaUrl, range, minimumRange = 2, onFrame, onRangeCommit }: Props) {
  const [draft, setDraft] = useState(range);
  const [previews, setPreviews] = useState<Record<number, string>>({});
  const [hoverFrame, setHoverFrame] = useState<number>();
  const stripRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState>();

  useEffect(() => setDraft(range), [range]);

  useEffect(() => {
    let cancelled = false;
    const video = document.createElement('video');
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    const samples = Array.from(
      new Set(Array.from({ length: PREVIEW_COUNT }, (_, index) => Math.round(
        (index / (PREVIEW_COUNT - 1)) * Math.max(0, frameCount - 1),
      ))),
    );
    let sampleIndex = 0;

    const nextPreview = () => {
      if (cancelled || sampleIndex >= samples.length) return;
      const target = samples[sampleIndex];
      const ratio = target / Math.max(1, frameCount - 1);
      video.currentTime = ratio * video.duration;
    };
    const capturePreview = () => {
      if (cancelled || !context || video.videoWidth === 0 || video.videoHeight === 0) return;
      const target = samples[sampleIndex];
      canvas.width = 160;
      canvas.height = 90;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      try {
        setPreviews((current) => ({ ...current, [target]: canvas.toDataURL('image/jpeg', 0.72) }));
      } catch {
        // Canvas previews are optional when a browser disallows frame extraction.
      }
      sampleIndex += 1;
      nextPreview();
    };
    const start = () => { sampleIndex = 0; setPreviews({}); nextPreview(); };
    video.muted = true;
    video.preload = 'auto';
    video.src = mediaUrl;
    video.addEventListener('loadedmetadata', start);
    video.addEventListener('seeked', capturePreview);
    return () => {
      cancelled = true;
      video.removeEventListener('loadedmetadata', start);
      video.removeEventListener('seeked', capturePreview);
      video.removeAttribute('src');
      video.load();
    };
  }, [frameCount, mediaUrl]);

  const frameAt = (clientX: number) => {
    const rect = stripRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return 0;
    return Math.max(0, Math.min(frameCount - 1, Math.round(
      ((clientX - rect.left) / rect.width) * (frameCount - 1),
    )));
  };
  const toPercent = (value: number) => `${(value / Math.max(1, frameCount - 1)) * 100}%`;
  const minimumGap = Math.max(1, Math.min(minimumRange, frameCount) - 1);

  const moveHandle = (event: ReactPointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const nextFrame = frameAt(event.clientX);
    setDraft((current) => drag.edge === 'start'
      ? { ...current, start: Math.min(nextFrame, current.end - minimumGap) }
      : { ...current, end: Math.max(nextFrame, current.start + minimumGap) });
  };
  const releaseHandle = (event: ReactPointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const nextFrame = frameAt(event.clientX);
    const finalRange = drag.edge === 'start'
      ? { ...draft, start: Math.min(nextFrame, draft.end - minimumGap) }
      : { ...draft, end: Math.max(nextFrame, draft.start + minimumGap) };
    setDraft(finalRange);
    dragRef.current = undefined;
    onRangeCommit(finalRange);
  };
  const beginHandleDrag = (edge: DragState['edge'], event: ReactPointerEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    dragRef.current = { edge };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  return (
    <section className="bg-surface-container border-t border-outline-variant p-3 select-none" aria-label="Video trim timeline">
      <div className="flex items-center justify-between mb-2 font-label text-[10px] text-on-surface-variant">
        <span>FRAME PREVIEW</span>
        <span>Drag the two trim heads to keep frames {draft.start}–{draft.end}</span>
      </div>
      <div
        ref={stripRef}
        className="relative h-24 overflow-hidden border border-outline-variant bg-surface-container-lowest cursor-crosshair"
        onClick={(event) => { if (!dragRef.current) onFrame(frameAt(event.clientX)); }}
        onMouseMove={(event) => setHoverFrame(frameAt(event.clientX))}
        onMouseLeave={() => setHoverFrame(undefined)}
      >
        {Array.from({ length: PREVIEW_COUNT }, (_, index) => {
          const previewFrame = Math.round((index / (PREVIEW_COUNT - 1)) * Math.max(0, frameCount - 1));
          return (
            <div key={`${index}-${previewFrame}`} className="absolute inset-y-0 border-r border-black/30" style={{ left: `${(index / PREVIEW_COUNT) * 100}%`, width: `${100 / PREVIEW_COUNT}%` }}>
              {previews[previewFrame] && <img src={previews[previewFrame]} alt={`Frame ${previewFrame}`} className="w-full h-full object-cover" />}
              <span className="absolute bottom-0 left-1 text-[9px] text-white drop-shadow">{previewFrame}</span>
            </div>
          );
        })}
        <span className="absolute inset-y-0 bg-primary/10 pointer-events-none" style={{ left: toPercent(draft.start), right: `${100 - ((draft.end / Math.max(1, frameCount - 1)) * 100)}%` }} />
        <span className="absolute inset-y-0 left-0 bg-surface-container-lowest/85 pointer-events-none" style={{ width: toPercent(draft.start) }} />
        <span className="absolute inset-y-0 right-0 bg-surface-container-lowest/85 pointer-events-none" style={{ left: toPercent(draft.end + 1) }} />
        <span className="absolute top-0 bottom-0 w-px bg-primary pointer-events-none z-20" style={{ left: toPercent(currentFrame) }} />
        {(['start', 'end'] as const).map((edge) => (
          <button
            key={edge}
            type="button"
            aria-label={`Drag trim ${edge}`}
            title={`Drag trim ${edge}`}
            className="absolute z-30 -translate-x-1/2 top-0 bottom-0 w-5 bg-primary-container border-x border-primary-fixed cursor-ew-resize focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-fixed"
            style={{ left: toPercent(draft[edge]) }}
            onPointerDown={(event) => beginHandleDrag(edge, event)}
            onPointerMove={moveHandle}
            onPointerUp={releaseHandle}
            onPointerCancel={() => { dragRef.current = undefined; setDraft(range); }}
            onClick={(event) => event.stopPropagation()}
          ><span className="text-on-primary-container font-bold">{edge === 'start' ? '‹' : '›'}</span></button>
        ))}
      </div>
      <div className="h-5 relative font-label text-[10px] text-on-surface-variant">
        <span className="absolute left-0">0</span>
        <span className="absolute left-1/2 -translate-x-1/2">{Math.round((frameCount - 1) / 2)}</span>
        <span className="absolute right-0">{frameCount - 1}</span>
      </div>
      {hoverFrame !== undefined && <p className="text-center font-label text-[10px] text-on-surface-variant" aria-live="polite">Frame {hoverFrame}</p>}
    </section>
  );
}
