import { useState } from 'react';
import type { GeneratedWindow, SuggestionSource, VideoSegment, VideoSuggestion } from '../../types';

const COLORS = { others: '#64748b', running: '#3b82f6', falling: '#ef4444' };
interface Props { frameCount: number; currentFrame: number; segments: VideoSegment[]; suggestions: VideoSuggestion[]; windows: GeneratedWindow[]; source: SuggestionSource; selectedSegment?: string; onFrame: (frame: number) => void; onSegment: (segment: VideoSegment) => void; onSuggestion: (suggestion: VideoSuggestion) => void; }

export function VideoTimeline({ frameCount, currentFrame, segments, suggestions, windows, source, selectedSegment, onFrame, onSegment, onSuggestion }: Props) {
  const [zoom,setZoom]=useState(1);
  const percent = (frame: number) => `${(frame / Math.max(1, frameCount - 1)) * 100}%`;
  const block = (start: number, end: number) => ({ left: percent(start), width: `${Math.max(.25, ((end-start+1) / frameCount) * 100)}%` });
  return <section className="bg-surface-container border-t border-outline-variant p-3" aria-label="Multi-layer timeline">
    <div className="flex justify-end items-center gap-2 mb-2 font-label text-[10px] text-on-surface-variant"><span>Timeline zoom</span><input aria-label="Timeline zoom" type="range" min="1" max="8" step="0.5" value={zoom} onChange={(event)=>setZoom(Number(event.target.value))}/><span>{zoom.toFixed(1)}×</span></div>
    <div className="overflow-x-auto">
    <div className="relative pl-20 space-y-1 cursor-crosshair min-w-full" style={{width:`${zoom*100}%`}} onClick={(event) => { const rect = event.currentTarget.getBoundingClientRect(); onFrame(Math.max(0, Math.min(frameCount - 1, Math.round(((event.clientX - rect.left - 80) / Math.max(1, rect.width - 80)) * frameCount)))); }}>
      <div className="absolute left-0 top-0 bottom-0 w-16 font-label text-[10px] text-on-surface-variant flex flex-col justify-around"><span>HUMAN</span><span>{source.toUpperCase()}</span><span>WINDOWS</span><span>QUALITY</span></div>
      <div className="relative h-7 bg-surface-container-lowest border border-outline-variant">{segments.map((segment) => <button key={segment.segment_id} title={`${segment.label} ${segment.start_frame}-${segment.end_frame}`} onClick={(event) => { event.stopPropagation(); onSegment(segment); }} className={`absolute top-1 bottom-1 rounded-sm ${selectedSegment === segment.segment_id ? 'ring-1 ring-primary' : ''}`} style={{ ...block(segment.start_frame, segment.end_frame), background: COLORS[segment.label] }} />)}</div>
      <div className="relative h-7 bg-surface-container-lowest border border-outline-variant">{suggestions.filter((item) => item.review_status === 'pending').map((suggestion) => <button key={suggestion.suggestion_id} onClick={(event) => { event.stopPropagation(); onSuggestion(suggestion); }} className={`absolute top-1 bottom-1 border-2 ${source === 'AI' ? 'border-dashed' : 'border-solid'} bg-opacity-20`} style={{ ...block(suggestion.start_frame, suggestion.end_frame), borderColor: COLORS[suggestion.suggested_label], backgroundColor: `${COLORS[suggestion.suggested_label]}40` }} title={`${source} ${suggestion.suggested_label} ${Math.round(suggestion.confidence*100)}%`} />)}</div>
      <div className="relative h-5 bg-surface-container-lowest border border-outline-variant">{windows.map((window) => <span key={window.window_id} className={`absolute top-1 bottom-1 border ${window.include_in_export ? 'border-emerald-500/60 bg-emerald-500/20' : 'border-amber-500/40 bg-amber-500/10'}`} style={block(window.start_frame, window.end_frame)} title={window.label ?? 'unresolved'} />)}</div>
      <div className="relative h-2 bg-gradient-to-r from-error/60 via-amber-400/40 to-emerald-400/60" />
      <span className="absolute top-0 bottom-0 w-px bg-primary pointer-events-none z-20" style={{ left: `calc(80px + (100% - 80px) * ${currentFrame / Math.max(1, frameCount - 1)})` }} />
    </div>
    </div>
    <div className="font-label text-label-sm text-on-surface-variant flex justify-between mt-2"><span>Frame 0</span><span>Current {currentFrame}</span><span>Frame {frameCount-1}</span></div>
  </section>;
}
