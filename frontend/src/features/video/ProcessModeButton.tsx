import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Loader2, Wand2 } from 'lucide-react';

export type ProcessMode = 'Threshold' | 'Model';

interface ProcessModeButtonProps {
  mode: ProcessMode;
  disabled?: boolean;
  processing?: boolean;
  modelAvailable: boolean;
  modelUnavailableReason?: string;
  onModeChange: (mode: ProcessMode) => void;
  onProcess: () => void;
}

/** Run the selected suggestion workflow without making users reopen a menu. */
export function ProcessModeButton({
  mode,
  disabled = false,
  processing = false,
  modelAvailable,
  modelUnavailableReason = 'Model suggestions are not available for this project.',
  onModeChange,
  onProcess,
}: ProcessModeButtonProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const modeBlocked = mode === 'Model' && !modelAvailable;

  useEffect(() => {
    function close(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', escape);
    };
  }, []);

  return (
    <div ref={root} className="relative flex">
      <button
        type="button"
        disabled={disabled || processing || modeBlocked}
        title={modeBlocked ? modelUnavailableReason : `Process with ${mode} suggestions`}
        onClick={onProcess}
        className="h-8 px-3 rounded-l bg-primary-container text-on-primary-container font-label text-label-sm font-bold flex items-center gap-2 disabled:opacity-40"
      >
        {processing ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />}
        {processing ? `Processing: ${mode}` : `Process: ${mode}`}
      </button>
      <button
        type="button"
        aria-label="Choose processing mode"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled || processing}
        onClick={() => setOpen((current) => !current)}
        className="h-8 w-8 rounded-r border-l border-on-primary-container/30 bg-primary-container text-on-primary-container flex items-center justify-center disabled:opacity-40"
      >
        <ChevronDown size={15} />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Processing mode"
          className="absolute right-0 top-9 z-50 min-w-44 rounded border border-outline-variant bg-surface-container-high p-1 shadow-xl"
        >
          <button
            type="button"
            role="menuitemradio"
            aria-checked={mode === 'Threshold'}
            onClick={() => { onModeChange('Threshold'); setOpen(false); }}
            className={`w-full rounded px-3 py-2 text-left text-label-sm ${mode === 'Threshold' ? 'bg-primary/10 text-primary' : 'hover:bg-surface-container-highest'}`}
          >
            Threshold
          </button>
          <button
            type="button"
            role="menuitemradio"
            aria-checked={mode === 'Model'}
            disabled={!modelAvailable}
            title={!modelAvailable ? modelUnavailableReason : undefined}
            onClick={() => { onModeChange('Model'); setOpen(false); }}
            className={`w-full rounded px-3 py-2 text-left text-label-sm disabled:opacity-40 ${mode === 'Model' ? 'bg-primary/10 text-primary' : 'hover:bg-surface-container-highest'}`}
          >
            Model
            {!modelAvailable && <span className="block text-[10px] text-on-surface-variant">Unavailable</span>}
          </button>
        </div>
      )}
    </div>
  );
}
