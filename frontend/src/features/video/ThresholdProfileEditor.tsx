import { useEffect, useState } from 'react';
import { RotateCcw, Save } from 'lucide-react';
import { cloneThresholdProfile, getThresholdProfiles, restoreDefaultThresholdProfile, saveThresholdProfile } from '../../api/client';
import type { ThresholdProfile } from '../../types';

export function ThresholdProfileEditor({ projectId }: { projectId: string }) {
  const [profiles, setProfiles] = useState<ThresholdProfile[]>([]);
  const [selected, setSelected] = useState<ThresholdProfile | null>(null);
  const [status, setStatus] = useState('');
  const [advanced,setAdvanced]=useState('');
  useEffect(() => { getThresholdProfiles(projectId).then((rows) => { setProfiles(rows); setSelected(rows[0] ?? null); }); }, [projectId]);
  useEffect(()=>{if(selected)setAdvanced(JSON.stringify(selected.config,null,2));},[selected?.threshold_profile_id]);
  if (!selected) return <div className="p-4 text-on-surface-variant">No threshold profile.</div>;
  const transforms = selected.config.transforms as Record<string, [number, number]>;
  function update(name: string, index: number, value: number) { setSelected({ ...selected!, config: { ...selected!.config, transforms: { ...transforms, [name]: transforms[name].map((item, current) => current === index ? value : item) } } }); }
  return <div className="p-3 overflow-y-auto space-y-3">
    <div className="flex gap-2"><select value={selected.threshold_profile_id} onChange={(event) => setSelected(profiles.find((item) => item.threshold_profile_id === event.target.value) ?? selected)} className="h-8 flex-1 bg-surface-container-lowest border border-outline-variant rounded px-2">{profiles.map((profile) => <option key={profile.threshold_profile_id} value={profile.threshold_profile_id}>{profile.name} · {profile.version}</option>)}</select></div>
    <p className="font-label text-label-caps uppercase text-on-surface-variant">Raw-to-score ranges</p>
    {Object.entries(transforms).map(([name,bounds]) => <div key={name}><label className="font-label text-[10px] block mb-1">{name}</label><div className="grid grid-cols-2 gap-2"><input aria-label={`${name} low`} type="number" step="0.01" value={bounds[0]} onChange={(event) => update(name,0,Number(event.target.value))} className="h-8 bg-surface-container-lowest border border-outline-variant rounded px-2" /><input aria-label={`${name} high`} type="number" step="0.01" value={bounds[1]} onChange={(event) => update(name,1,Number(event.target.value))} className="h-8 bg-surface-container-lowest border border-outline-variant rounded px-2" /></div></div>)}
    <details><summary className="font-label text-label-sm cursor-pointer">Advanced weights, thresholds, counts, and quality gates</summary><textarea aria-label="Advanced threshold profile JSON" value={advanced} onChange={(event)=>setAdvanced(event.target.value)} onBlur={()=>{try{setSelected({...selected,config:JSON.parse(advanced)});setStatus('Advanced config ready to save');}catch{setStatus('Invalid JSON');}}} className="mt-2 w-full h-64 bg-surface-container-lowest border border-outline-variant rounded p-2 font-code text-[10px]"/></details>
    <div className="flex flex-wrap gap-2 sticky bottom-0 bg-surface-container py-2"><button onClick={() => { const original = profiles.find((item) => item.threshold_profile_id === selected.threshold_profile_id); if (original) setSelected(original); }} className="h-8 px-3 border border-outline-variant rounded flex items-center gap-1"><RotateCcw size={14} />Reset</button><button onClick={()=>void cloneThresholdProfile(projectId,selected).then((result)=>{setProfiles((rows)=>[result,...rows]);setSelected(result);})} className="h-8 px-3 border border-outline-variant rounded">Clone</button><button onClick={()=>void restoreDefaultThresholdProfile(projectId).then((result)=>{setProfiles((rows)=>[result,...rows]);setSelected(result);})} className="h-8 px-3 border border-outline-variant rounded">Restore defaults</button><button onClick={() => { setStatus('Saving…'); saveThresholdProfile(projectId, selected).then((result) => { setSelected(result); setStatus('Saved'); }); }} className="h-8 px-3 bg-primary-container text-on-primary-container rounded flex items-center gap-1"><Save size={14} />Save profile</button><span className="text-label-sm text-on-surface-variant self-center">{status}</span></div>
  </div>;
}
