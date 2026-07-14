import { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';

interface HelpSection {
  title: string;
  content: string[];
}

const HELP_SECTIONS: HelpSection[] = [
  {
    title: 'Basic workflow',
    content: [
      '1. Select or import a video.',
      '2. Process it using Threshold or Model suggestions.',
      '3. Select a worker track.',
      '4. Review the generated segment labels in the video.',
      '5. Set segment start and end frames.',
      '6. Assign Falling, Running, or Others.',
      '7. Edit or add segments as needed.',
      '8. Save and continue to the next video.',
    ],
  },
  {
    title: 'Falling',
    content: [
      'Start Falling when a clear uncontrolled loss of balance begins.',
      'Lying after a fall remains Falling.',
      'Recovery remains Falling until the worker returns to a stable normal posture.',
      'Running changes to Falling at the first clear loss-of-balance frame.',
    ],
  },
  {
    title: 'Running',
    content: [
      'Use Running for active running, sprinting, or a clearly running gait.',
      'End it when the worker returns to walking or standing, leaves the track, or begins falling.',
    ],
  },
  {
    title: 'Others',
    content: [
      'Use Others for all normal work behavior, including standing, walking, bending, crouching, kneeling, sitting, and stable recovery.',
    ],
  },
  {
    title: 'Playback and frames',
    content: [
      'Space plays or pauses. Left and Right move one frame; hold Shift to move ten frames.',
      'Use the frame box or timeline to jump exactly. Playback, tracks, and the timeline stay synchronized.',
      'I sets the segment start and O sets the segment end.',
    ],
  },
  {
    title: 'Suggestions and labels',
    content: [
      'Threshold uses motion rules; Model uses a compatible externally configured model.',
      'Processing generates editable segment labels using the selected method. The timeline shows only those saved segments; it has no suggestion overlay.',
      'Review and edit the generated segments directly. 1, 2, and 3 select Others, Running, and Falling.',
      'Existing segment edits autosave after a short pause; watch Unsaved changes, Saving, and Saved in the toolbar.',
      'Ctrl+Z and Ctrl+Y undo and redo. Enter saves. N approves and opens the next video.',
      'Hold Alt to display a temporary shortcut guide over the workspace.',
    ],
  },
  {
    title: 'Video status filters',
    content: [
      'System processing shows background work: Unprocessed has not started, Processing is queued or running, Ready can be annotated, and Failed needs retrying.',
      'User labelling shows annotation progress: Unlabeled has no segments, Labeled segments are ground truth and editable, and Approved has been finalized for export.',
      'The two filters work together. Leave either one on All to ignore it, or choose both to find videos matching both states.',
      'Order sorts the filtered list by recent updates, name, duration, frame count, processing, or labelling status. Use its arrow to reverse the order.',
    ],
  },
  {
    title: 'Select and delete items',
    content: [
      'Use a checkbox or Ctrl/Cmd-click to select multiple video, worker, or segment cards. Checked segment cards remain visually unchanged; the border indicates only the segment currently open for editing.',
      'Use Delete selected, or press Delete/Backspace, to remove the most recently selected group. Deleting workers also removes their segments.',
      'Use the trash button on a video card for one video. Video deletion always asks for confirmation before removing its project-owned copy, annotations, jobs, and derived data.',
    ],
  },
];

export function PoseHelpDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const sections = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return HELP_SECTIONS;
    return HELP_SECTIONS.filter((section) =>
      `${section.title} ${section.content.join(' ')}`.toLowerCase().includes(needle),
    );
  }, [query]);

  useEffect(() => {
    if (!open) return undefined;
    function escape(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] bg-black/60 flex items-center justify-center p-4" onMouseDown={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="pose-help-title"
        onMouseDown={(event) => event.stopPropagation()}
        className="w-full max-w-2xl max-h-[85vh] bg-surface-container-high border border-outline-variant rounded-lg shadow-2xl flex flex-col"
      >
        <header className="h-12 px-4 border-b border-outline-variant flex items-center justify-between shrink-0">
          <h2 id="pose-help-title" className="font-headline-sm text-headline-sm">Pose labeling help</h2>
          <button type="button" aria-label="Close help" onClick={onClose} className="toolbar-icon"><X size={18} /></button>
        </header>
        <div className="p-4 border-b border-outline-variant shrink-0">
          <label className="relative block">
            <Search size={15} className="absolute left-3 top-2.5 text-on-surface-variant" />
            <span className="sr-only">Search help</span>
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search workflow, labels, or controls"
              className="editor-input mt-0 pl-9"
            />
          </label>
        </div>
        <div className="overflow-y-auto p-4 space-y-5">
          {sections.map((section) => (
            <section key={section.title}>
              <h3 className="font-headline-sm font-semibold text-primary mb-2">{section.title}</h3>
              <div className="space-y-1 text-body-md text-on-surface-variant">
                {section.content.map((line) => <p key={line}>{line}</p>)}
              </div>
            </section>
          ))}
          {sections.length === 0 && <p className="text-on-surface-variant">No help topics match that search.</p>}
        </div>
      </section>
    </div>
  );
}
