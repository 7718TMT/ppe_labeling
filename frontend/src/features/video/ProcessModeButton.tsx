import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Loader2, Wand2 } from 'lucide-react';

export type ProcessMode = 'Threshold' | 'Model';
export type SuggestionMode = 'Off' | 'Threshold' | 'AI';

interface SuggestionModeButtonProps {
  source: SuggestionMode;
  disabled?: boolean;
  generating?: boolean;
  modelAvailable: boolean;
  modelUnavailableReason?: string;
  compact?: boolean;
  onSourceChange: (source: SuggestionMode) => void;
  onGenerate: () => void;
}

/** Select, show, and generate one suggestion source from a single control. */
export function SuggestionModeButton({
  source,
  disabled = false,
  generating = false,
  modelAvailable,
  modelUnavailableReason = 'Model suggestions are not available for this project.',
  compact = false,
  onSourceChange,
  onGenerate,
}: SuggestionModeButtonProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const sourceBlocked = source === 'AI' && !modelAvailable;
  const generationUnavailable = source === 'Off' || sourceBlocked;

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
        aria-label={compact ? 'Suggestion' : undefined}
        disabled={disabled || generating || generationUnavailable}
        title={sourceBlocked ? modelUnavailableReason : source === 'Off' ? 'Suggestions are off. Choose Threshold or AI.' : `Suggestions: ${source}. Generate suggestions for the selected video.`}
        onClick={onGenerate}
        className={compact
          ? 'h-8 w-8 rounded-l bg-primary-container text-on-primary-container flex items-center justify-center disabled:opacity-40'
          : 'h-8 px-3 rounded-l bg-primary-container text-on-primary-container font-label text-label-sm font-bold flex items-center gap-2 disabled:opacity-40'}
      >
        {generating ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />}
        {!compact && 'Suggestion'}
      </button>
      <button
        type="button"
        aria-label="Choose suggestion source"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={generating}
        onClick={() => setOpen((current) => !current)}
        title={`Suggestion mode: ${source}`}
        className="h-8 w-6 rounded-r border-l border-on-primary-container/30 bg-primary-container text-on-primary-container flex items-center justify-center disabled:opacity-40"
      >
        <ChevronDown size={15} />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Suggestion source"
          className="absolute right-0 top-9 z-50 min-w-44 rounded border border-outline-variant bg-surface-container-high p-1 shadow-xl"
        >
          <button
            type="button"
            role="menuitemradio"
            aria-checked={source === 'Threshold'}
            onClick={() => { onSourceChange('Threshold'); setOpen(false); }}
            className={`w-full rounded px-3 py-2 text-left text-label-sm ${source === 'Threshold' ? 'bg-primary/10 text-primary' : 'hover:bg-surface-container-highest'}`}
          >
            Threshold
          </button>
          <button
            type="button"
            role="menuitemradio"
            aria-checked={source === 'AI'}
            disabled={!modelAvailable}
            title={!modelAvailable ? modelUnavailableReason : undefined}
            onClick={() => { onSourceChange('AI'); setOpen(false); }}
            className={`w-full rounded px-3 py-2 text-left text-label-sm disabled:opacity-40 ${source === 'AI' ? 'bg-primary/10 text-primary' : 'hover:bg-surface-container-highest'}`}
          >
            AI
            {!modelAvailable && <span className="block text-[10px] text-on-surface-variant">Unavailable</span>}
          </button>
          <button
            type="button"
            role="menuitemradio"
            aria-checked={source === 'Off'}
            onClick={() => { onSourceChange('Off'); setOpen(false); }}
            className={`w-full rounded px-3 py-2 text-left text-label-sm ${source === 'Off' ? 'bg-primary/10 text-primary' : 'hover:bg-surface-container-highest'}`}
          >
            Off
          </button>
        </div>
      )}
    </div>
  );
}
