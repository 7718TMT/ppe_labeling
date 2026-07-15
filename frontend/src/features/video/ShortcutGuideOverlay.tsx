interface Shortcut {
  keys: string[];
  action: string;
}

const PLAYBACK_SHORTCUTS: Shortcut[] = [
  { keys: ['Space'], action: 'Play or pause' },
  { keys: ['←'], action: 'Move one frame back' },
  { keys: ['→'], action: 'Move one frame forward' },
  { keys: ['Shift', '←'], action: 'Move 10 frames back' },
  { keys: ['Shift', '→'], action: 'Move 10 frames forward' },
  { keys: ['I'], action: 'Set segment start' },
  { keys: ['O'], action: 'Set segment end' },
  { keys: ['Esc'], action: 'Exit fullscreen or return to full video' },
];

const EDITING_SHORTCUTS: Shortcut[] = [
  { keys: ['1'], action: 'Select Others' },
  { keys: ['2'], action: 'Select Running' },
  { keys: ['3'], action: 'Select Falling' },
  { keys: ['T'], action: 'Use Threshold suggestions' },
  { keys: ['M'], action: 'Use AI suggestions' },
  { keys: ['S'], action: 'Turn suggestions off' },
  { keys: ['Enter'], action: 'Add or modify segment' },
  { keys: ['X'], action: 'Include or exclude segment' },
  { keys: ['Delete'], action: 'Delete selected group' },
  { keys: ['Backspace'], action: 'Delete selected group' },
  { keys: ['Ctrl', 'Z'], action: 'Undo (Cmd on macOS)' },
  { keys: ['Ctrl', 'Y'], action: 'Redo (Cmd on macOS)' },
  { keys: ['Ctrl', 'Click'], action: 'Multi-select (Cmd on macOS)' },
];

function ShortcutRow({ keys, action }: Shortcut) {
  return (
    <div className="flex items-center justify-between gap-3 text-label-sm">
      <span className="flex shrink-0 items-center gap-1">
        {keys.map((key, index) => (
          <span key={`${key}-${index}`} className="flex items-center gap-1">
            {index > 0 && <span className="text-on-surface-variant">+</span>}
            <kbd className="min-w-6 rounded border border-outline-variant bg-surface-container-lowest px-1.5 py-0.5 text-center font-label text-[10px] text-on-surface">{key}</kbd>
          </span>
        ))}
      </span>
      <span className="text-right text-on-surface-variant">{action}</span>
    </div>
  );
}

/** Temporary Alt-held reference for the current video-labeling shortcuts. */
export function ShortcutGuideOverlay({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <section aria-label="Keyboard shortcut guide" className="pointer-events-none fixed inset-x-0 bottom-4 z-[90] flex justify-center px-4">
      <div className="w-full max-w-4xl rounded-lg border border-outline-variant bg-surface-container-high/95 p-3 shadow-2xl backdrop-blur">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="font-headline-sm text-primary">Keyboard shortcuts</h2>
          <span className="font-label text-[10px] text-on-surface-variant">Hold Alt · release to close</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2">
          <section className="space-y-1 sm:pr-5">
            <h3 className="mb-2 font-label text-[10px] uppercase text-on-surface-variant">Playback and navigation</h3>
            {PLAYBACK_SHORTCUTS.map((shortcut) => <ShortcutRow key={`${shortcut.keys.join('-')}-${shortcut.action}`} {...shortcut} />)}
          </section>
          <section className="mt-3 border-t border-outline-variant pt-3 sm:mt-0 sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0">
            <h3 className="mb-2 font-label text-[10px] uppercase text-on-surface-variant">Labels and editing</h3>
            <div className="space-y-1">
              {EDITING_SHORTCUTS.map((shortcut) => <ShortcutRow key={`${shortcut.keys.join('-')}-${shortcut.action}`} {...shortcut} />)}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
