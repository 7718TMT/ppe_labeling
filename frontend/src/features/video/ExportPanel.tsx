import { useState } from 'react';
import { CheckCircle2, Download, ShieldCheck } from 'lucide-react';
import { createVideoExport, validateVideoExport } from '../../api/client';

export function ExportPanel({ projectId }: { projectId: string }) {
  const [validation,setValidation]=useState<{errors:string[];warnings:string[]}|null>(null); const [message,setMessage]=useState('');
  async function validate(){setValidation(await validateVideoExport(projectId));}
  async function create(){const result=await createVideoExport(projectId);setMessage(result.queued?'Export queued in background.':'Resolve validation errors first.');setValidation(result.validation);}
  return <div className="p-3 space-y-3"><div className="flex gap-2"><button onClick={()=>void validate()} className="h-8 px-3 border border-outline-variant rounded flex items-center gap-2"><ShieldCheck size={14}/>Validate</button><button onClick={()=>void create()} className="h-8 px-3 bg-primary-container text-on-primary-container rounded flex items-center gap-2"><Download size={14}/>Create export</button></div>{message&&<p className="text-label-sm">{message}</p>}{validation&&<div className="space-y-2"><p className="flex gap-2 items-center text-label-sm"><CheckCircle2 size={14} className={validation.errors.length?'text-error':'text-emerald-400'}/>{validation.errors.length?'Blocked':'Ready for atomic export'}</p>{validation.errors.map((item)=><p key={item} className="text-label-sm text-error">{item}</p>)}{validation.warnings.map((item)=><p key={item} className="text-label-sm text-amber-300">{item}</p>)}</div>}<p className="text-[10px] text-on-surface-variant">Outputs: annotations.jsonl, windows.parquet, features.parquet, keypoint_windows.npz, suggestion audits, and manifest.json. No splits are created.</p></div>;
}
