import type { FeatureWindow } from '../../types';

export function FeatureInspector({ features, frame }: { features: FeatureWindow[]; frame: number }) {
  const active = features.find((item) => item.start_frame <= frame && item.end_frame >= frame);
  if (!active) return <div className="p-4 text-body-md text-on-surface-variant">Feature data is not available for this frame.</div>;
  const scores = ['fall_transition_score','fall_state_score','running_score','torso_horizontal_score','spread_score','combined_locomotion_score'];
  return <div className="p-3 space-y-4 overflow-y-auto">
    <div><p className="font-label text-label-caps uppercase text-on-surface-variant">Feature window</p><p className="font-label text-label-sm mt-1">{active.start_frame}–{active.end_frame} · {active.quality.status}</p></div>
    <div className="space-y-2">{scores.map((name) => <div key={name}><div className="flex justify-between font-label text-[10px]"><span>{name}</span><span>{(active.transformed[name] ?? 0).toFixed(3)}</span></div><div className="h-1.5 bg-surface-container-lowest"><div className="h-full bg-primary" style={{ width: `${(active.transformed[name] ?? 0)*100}%` }} /></div></div>)}</div>
    <div><p className="font-label text-label-caps uppercase text-on-surface-variant mb-2">15-step heatmap</p><div className="grid grid-cols-15 gap-px">{Array.from({length:15}, (_, index) => <span key={index} title={`step ${index}`} className="h-8" style={{ background: `rgba(87,241,219,${Math.min(1, (active.raw[`step_combined_speed_t${index}`] ?? 0)/2)})` }} />)}</div></div>
    <details><summary className="font-label text-label-sm cursor-pointer">Raw Group A–E values</summary><div className="mt-2 max-h-52 overflow-auto font-label text-[10px]">{Object.entries(active.raw).map(([name,value]) => <div key={name} className="flex justify-between border-b border-outline-variant/40 py-1 gap-3"><span className="truncate">{name}</span><span>{value.toFixed(4)}</span></div>)}</div></details>
    <p className="text-[10px] text-on-surface-variant">Feature values are generated and read-only. Provenance is retained per decimated step.</p>
  </div>;
}
