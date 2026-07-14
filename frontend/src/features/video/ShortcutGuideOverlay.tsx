interface ShortcutGuideOverlayProps {
  visible: boolean;
}

const SHORTCUTS = [
  ['Space', 'Play or pause'],
  ['← / →', 'Move one frame'],
  ['Shift + ← / →', 'Move 10 frames'],
  ['I / O', 'Set segment start / end'],
  ['1 / 2 / 3', 'Others / Running / Falling'],
  ['T / M / S', 'Threshold / AI / Off'],
  ['Esc', 'Return to full video'],
  ['Delete', 'Delete selected segment'],
  ['X', 'Exclude or restore segment'],
  ['Enter', 'Add or modify segment'],
  ['Ctrl + Z / Y', 'Undo / redo'],
];

/** Temporary, Alt-held reference for the video-labeling keyboard controls. */
export function ShortcutGuideOverlay({ visible }: ShortcutGuideOverlayProps) {
  if (!visible) return null;
  return (
    <section
      aria-label="Keyboard shortcut guide"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-[90] flex justify-center px-4"
    >
      <div className="w-full max-w-3xl rounded-lg border border-outline-variant bg-surface-container-high/95 p-3 shadow-2xl backdrop-blur">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 className="font-headline-sm text-primary">Keyboard shortcuts</h2>
          <span className="font-label text-[10px] text-on-surface-variant">Release Alt to close</span>
        </div>
        <div className="grid grid-cols-1 gap-x-5 gap-y-1 sm:grid-cols-2">
          {SHORTCUTS.map(([shortcut, action]) => (
            <div key={shortcut} className="flex items-center justify-between gap-3 text-label-sm">
              <kbd className="shrink-0 rounded border border-outline-variant bg-surface-container-lowest px-1.5 py-0.5 font-label text-[10px] text-on-surface">{shortcut}</kbd>
              <span className="text-right text-on-surface-variant">{action}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
