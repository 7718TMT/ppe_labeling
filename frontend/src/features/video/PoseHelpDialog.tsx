import { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';

interface HelpSection {
  title: string;
  content: string[];
}

const HELP_SECTIONS: HelpSection[] = [
  {
    title: 'Workspace zones',
    content: [
      'Top bar: open Help, see save state, undo or redo annotation changes, move to the previous or next video, and open or close the sidebars.',
      'Left sidebar: import, export, find, filter, sort, rename, select, and delete videos. Its Processing queue gives one progress bar for the current batch.',
      'Centre: play the selected video, view pose overlays, trim media, generate suggestions, and edit labels on the timeline.',
      'Right sidebar: select workers, manage their segments, fill gaps, inspect video details, and approve or unapprove the current video.',
    ],
  },
  {
    title: 'Video browser and dataset actions',
    content: [
      'Import adds one or more video files and immediately queues keypoint processing and the selected automatic suggestion method.',
      'Export opens the dataset-export dialog. Validate first, create the export, then the ZIP download starts when it is ready.',
      'The number chip shows the visible video count. The more menu contains Rename all; provide a prefix to rename the dataset sequentially.',
      'Search filters by video name. Filters opens System processing and User labelling filters; active filters appear as removable chips. Sort changes the order, and its arrow reverses it.',
      'Tick video cards or Ctrl/Cmd-click them for bulk selection. Delete selected opens a confirmation and removes only project-owned media, labels, jobs, and derived data.',
    ],
  },
  {
    title: 'Basic labeling workflow',
    content: [
      '1. Import or select a video and wait until processing is ready.',
      '2. Select a worker. Use Suggestions if you want automatic editable labels.',
      '3. Review segment cards and timeline bars, then create, modify, split, expand, merge, or delete segments as needed.',
      '4. Use only Others, Running, and Falling. Saved suggestions are ground-truth labels unless you edit them.',
      '5. Approve the video when its labels are complete; export the dataset when the project is ready.',
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
    title: 'Playback, timeline, and video toolbar',
    content: [
      'Back and Forward move ten frames. Play controls playback. The frame box and timeline seek to an exact frame; the speed menu changes playback speed.',
      'Loop repeats the selected segment, or the full video when no segment is selected. Overlay shows or hides worker boxes and pose skeletons. Fullscreen enters or exits the player view.',
      'Timeline rows belong to workers. Drag a segment body to move it; drag its left or right edge to resize it. A segment stops at neighbouring segment boundaries.',
      'Trim opens the non-destructive trim view. Its two heads choose the inclusive kept range; the range must contain at least 60 frames. Preview loops the proposed range, Reset restores the full range, Save copy creates a named copy, and Replace video edits the current managed video.',
    ],
  },
  {
    title: 'Suggestions and labels',
    content: [
      'The wand next to Trim generates suggestions for the current video. Its chevron switches Threshold, AI, or Off. Threshold uses motion rules; AI requires a configured compatible model.',
      'Generating new suggestions asks for confirmation when the video already has labels because the new result replaces them.',
      'Suggestions become normal editable segments. The timeline has no separate legacy suggestion overlay.',
      'Existing segment edits autosave after a short pause; watch Unsaved changes, Saving, and Saved in the top bar.',
    ],
  },
  {
    title: 'Workers and segments',
    content: [
      'Choose a worker card to show its segments. Split divides a worker at the current frame. Exclude or Restore controls whether a worker is included in export. Delete removes that worker and all of its segments.',
      'Select a segment card to edit its start, end, and label. Split divides it at the current frame. Expand fills surrounding unlabelled space. Delete removes only the segment and keeps the worker timeline row.',
      'Tick segment cards or Ctrl/Cmd-click them to select several. Merge appears only for adjacent segments with the same label on one worker. Delete selected removes the checked segments.',
      'Create Segment opens the same editor for a new range. Fill gaps adds the chosen label to all uncovered parts of the selected worker.',
      'Use the Details tab to inspect video metadata and toggle pose overlays or selected-worker-only display.',
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
    title: 'Approval, export, and recovery',
    content: [
      'Approve video finalizes the current label state for export. Unapprove makes it editable again. Approval requires valid saved segments.',
      'Processing errors are shown in the status bar and on the video card. The unified queue shows batch progress; deleting a processing video immediately removes it from the queue.',
      'Use Export in the left sidebar to validate and create a training-sample ZIP. The export contains annotations.jsonl, keypoint_windows.npz, and manifest.json.',
      'The status bar explains successful actions and failures. Dismiss it with its close button; retry an action after resolving the stated issue.',
    ],
  },
  {
    title: 'Keyboard shortcuts',
    content: [
      'Hold Alt to show the temporary shortcut overlay. Release Alt to close it. Shortcuts do not run while typing in a form field.',
      'Space plays or pauses; Left and Right move one frame; Shift with Left or Right moves ten frames. I and O set segment start and end.',
      '1, 2, and 3 select Others, Running, and Falling. T, M, and S select Threshold, AI, and Off. Enter saves a segment; X includes or excludes the selected segment.',
      'Escape exits browser fullscreen when active, or clears the selected segment and returns to full-video mode. Ctrl/Cmd+Z undoes, Ctrl/Cmd+Y redoes, and Delete/Backspace acts on the selected group.',
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
        className="decorative-dialog w-full max-w-2xl max-h-[85vh] bg-surface-container-high border border-outline-variant rounded-lg flex flex-col"
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
