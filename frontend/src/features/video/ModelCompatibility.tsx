import { useEffect, useRef, useState } from 'react';
import { BrainCircuit, ShieldAlert, Upload } from 'lucide-react';
import { getExternalModels, importExternalModel, runExternalModel, unloadExternalModel } from '../../api/client';
import type { ExternalModel } from '../../types';

export function ModelCompatibility({ projectId, videoId }: { projectId: string; videoId?: string }) {
  const [models, setModels] = useState<ExternalModel[]>([]);
  const artifact = useRef<HTMLInputElement>(null); const manifest = useRef<HTMLInputElement>(null);
  const [trusted, setTrusted] = useState(false); const [message, setMessage] = useState('');
  const refresh = () => getExternalModels(projectId).then(setModels);
  useEffect(() => { void refresh(); }, [projectId]);
  async function upload() { const a=artifact.current?.files?.[0], m=manifest.current?.files?.[0]; if(!a||!m) return; try { await importExternalModel(projectId,a,m,trusted); setMessage('Package inspected.'); await refresh(); } catch(reason){ setMessage(String(reason)); } }
  return <div className="p-3 overflow-y-auto space-y-3">
    <div className="border border-amber-500/30 bg-amber-500/10 rounded p-2 text-label-sm flex gap-2"><ShieldAlert size={16} className="text-amber-400 shrink-0" />Pickle/joblib can execute code. Only confirm packages you trust locally.</div>
    <input ref={artifact} type="file" accept=".joblib,.pkl,.pickle,.onnx" className="block w-full text-label-sm" /><input ref={manifest} type="file" accept=".json" className="block w-full text-label-sm" />
    <label className="flex items-center gap-2 text-label-sm"><input type="checkbox" checked={trusted} onChange={(event)=>setTrusted(event.target.checked)} />I trust this local package</label>
    <button onClick={() => void upload()} className="h-8 px-3 bg-primary-container text-on-primary-container rounded flex gap-2 items-center"><Upload size={14}/>Inspect package</button>{message && <p className="text-label-sm text-on-surface-variant">{message}</p>}
    {models.map((model)=><div key={model.external_model_id} className="border-t border-outline-variant pt-3"><div className="flex gap-2 items-center"><BrainCircuit size={16} className={model.compatibility_status==='compatible'?'text-primary':'text-error'}/><span className="font-medium">{model.name} {model.version}</span></div><p className="text-label-sm text-on-surface-variant mt-1">{model.adapter_type} · {model.compatibility_status}{model.is_active?' · active':''}</p>{model.compatibility_errors?.map((error)=><p key={error} className="text-[10px] text-error mt-1">{error}</p>)}<div className="flex gap-2">{videoId && model.compatibility_status==='compatible' && <button onClick={()=>void runExternalModel(projectId,videoId,model.external_model_id)} className="mt-2 h-7 px-2 border border-outline-variant rounded text-label-sm">Generate AI suggestions</button>}{model.is_active?<button onClick={()=>void unloadExternalModel(projectId,model.external_model_id).then(refresh)} className="mt-2 h-7 px-2 border border-outline-variant rounded text-label-sm">Unload</button>:null}</div></div>)}
  </div>;
}
