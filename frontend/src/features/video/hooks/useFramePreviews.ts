import { useEffect, useMemo, useState } from 'react';


/** Return evenly distributed canonical frames for a preview strip. */
export function previewFrames(frameCount: number, previewCount = 12): number[] {
  return Array.from(new Set(Array.from(
    { length: previewCount },
    (_, index) => Math.round(
      (index / Math.max(1, previewCount - 1)) * Math.max(0, frameCount - 1),
    ),
  )));
}

/** Decode a small, bounded set of browser-local video frame previews. */
export function useFramePreviews(
  frameCount: number,
  mediaUrl: string,
  previewCount = 12,
): { samples: number[]; previews: Record<number, string> } {
  const samples = useMemo(
    () => previewFrames(frameCount, previewCount),
    [frameCount, previewCount],
  );
  const [previews, setPreviews] = useState<Record<number, string>>({});

  useEffect(() => {
    let cancelled = false;
    const video = document.createElement('video');
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    let sampleIndex = 0;

    const seekNext = () => {
      if (cancelled || sampleIndex >= samples.length) return;
      const target = samples[sampleIndex];
      video.currentTime = (target / Math.max(1, frameCount - 1)) * video.duration;
    };
    const capture = () => {
      if (
        cancelled || sampleIndex >= samples.length || !context || video.videoWidth === 0
        || video.videoHeight === 0
      ) return;
      const target = samples[sampleIndex];
      canvas.width = 160;
      canvas.height = 90;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      try {
        setPreviews((current) => ({
          ...current,
          [target]: canvas.toDataURL('image/jpeg', 0.72),
        }));
      } catch {
        // Cross-origin or restricted media may disallow canvas extraction.
      }
      sampleIndex += 1;
      seekNext();
    };
    const start = () => {
      sampleIndex = 0;
      setPreviews({});
      seekNext();
    };

    video.muted = true;
    video.preload = 'auto';
    video.src = mediaUrl;
    video.addEventListener('loadedmetadata', start);
    video.addEventListener('seeked', capture);
    return () => {
      cancelled = true;
      video.removeEventListener('loadedmetadata', start);
      video.removeEventListener('seeked', capture);
      video.removeAttribute('src');
      video.load();
    };
  }, [frameCount, mediaUrl, samples]);

  return { samples, previews };
}
