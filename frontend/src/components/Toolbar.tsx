import { Eye, EyeOff, Hand, Loader2, MousePointer2, Play, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';

import type { InteractionMode, TaskInfo } from '../types';

interface ToolbarProps {
  tasks: TaskInfo[];
  selectedTaskId: string;
  classNames: Record<number, string>;
  addClassIds: number[];
  assignClassIds: number[];
  drawingClass: number | null;
  interactionMode: InteractionMode;
  selectedCount: number;
  selectedClassId: number | null;
  overlayVisible: boolean;
  isResetting: boolean;
  isSaving: boolean;
  selectedImage: string | null;
  onTaskChange: (taskId: string) => void;
  onToggleAddMode: (classId: number) => void;
  onSelectedClassChange: (classId: number) => void;
  onOverlayVisibleChange: (visible: boolean) => void;
  onInteractionModeChange: (mode: InteractionMode) => void;
  onDeleteSelected: () => void;
  onReset: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

export function Toolbar({
  tasks,
  selectedTaskId,
  classNames,
  addClassIds,
  assignClassIds,
  drawingClass,
  interactionMode,
  selectedCount,
  selectedClassId,
  overlayVisible,
  isResetting,
  isSaving,
  selectedImage,
  onTaskChange,
  onToggleAddMode,
  onSelectedClassChange,
  onOverlayVisibleChange,
  onInteractionModeChange,
  onDeleteSelected,
  onReset,
  onPrevious,
  onNext,
}: ToolbarProps) {
  return (
    <div className="h-14 border-b border-gray-700 flex items-center px-4 gap-4 bg-gray-800 cursor-default">
      <select
        value={selectedTaskId}
        onChange={(event) => onTaskChange(event.target.value)}
        className="bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm text-white"
        title="Annotation task"
      >
        {tasks.map((task) => (
          <option key={task.id} value={task.id}>
            {task.name}
          </option>
        ))}
      </select>
      <div className="h-6 w-px bg-gray-600 mx-2" />
      <div className="flex gap-2">
        {addClassIds.map((id) => {
          return (
            <button
              key={id}
              onClick={() => onToggleAddMode(id)}
              className={`flex items-center gap-1 px-3 py-1 rounded text-sm transition font-medium ${
                drawingClass === id ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/50' : 'bg-gray-700 hover:bg-blue-900/40 text-blue-200'
              }`}
            >
              <Plus size={14} /> {drawingClass === id ? 'Drawing...' : selectedTaskId === 'safety_signs' ? 'Add Sign' : `Add ${classNames[id]}`}
            </button>
          );
        })}
      </div>
      <div className="h-6 w-px bg-gray-600 mx-2" />
      <div className="flex bg-gray-700 rounded p-1">
        <button
          onClick={() => onInteractionModeChange('select')}
          className={`p-1 rounded transition ${interactionMode === 'select' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
          title="Selection Mode (V)"
        >
          <MousePointer2 size={18} />
        </button>
        <button
          onClick={() => onInteractionModeChange('pan')}
          className={`p-1 rounded transition ${interactionMode === 'pan' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
          title="Pan Mode (H)"
        >
          <Hand size={18} />
        </button>
      </div>
      <div className="h-6 w-px bg-gray-600 mx-2" />
      <button
        onClick={() => onOverlayVisibleChange(!overlayVisible)}
        className="p-1 hover:bg-gray-700 rounded transition text-gray-300"
        title={overlayVisible ? 'Hide boxes' : 'Show boxes'}
      >
        {overlayVisible ? <Eye size={18} /> : <EyeOff size={18} />}
      </button>
      <div className="h-6 w-px bg-gray-600 mx-2" />
      <select
        value={selectedClassId ?? ''}
        onChange={(event) => onSelectedClassChange(Number(event.target.value))}
        disabled={selectedCount === 0}
        className="max-w-72 bg-gray-900 border border-gray-600 rounded px-2 py-1 text-sm text-white disabled:opacity-50"
        title="Assign selected box class"
      >
        <option value="" disabled>
          Assign class
        </option>
        {assignClassIds.map((id) => (
          <option key={id} value={id}>
            {id}: {classNames[id]}
          </option>
        ))}
      </select>
      <div className="h-6 w-px bg-gray-600 mx-2" />
      <button
        onClick={onDeleteSelected}
        disabled={selectedCount === 0}
        className="flex items-center gap-1 bg-red-900/50 hover:bg-red-800/50 disabled:opacity-50 px-3 py-1 rounded text-sm text-red-400 transition"
      >
        <Trash2 size={14} /> Delete Selected
      </button>
      <div className="h-6 w-px bg-gray-600 mx-2" />
      <button
        onClick={onReset}
        disabled={isResetting || !selectedImage}
        className="flex items-center gap-1 bg-orange-900/50 hover:bg-orange-800/50 disabled:opacity-50 px-3 py-1 rounded text-sm text-orange-400 transition"
      >
        {isResetting ? <Loader2 className="animate-spin" size={14} /> : <RotateCcw size={14} />}
        Return to Origin
      </button>
      <div className="h-6 w-px bg-gray-600 mx-2" />
      <div className="flex gap-1">
        <button onClick={onPrevious} className="p-1 hover:bg-gray-700 rounded transition" title="Previous (A)">
          <Play size={18} className="rotate-180" />
        </button>
        <button onClick={onNext} className="p-1 hover:bg-gray-700 rounded transition" title="Next (D)">
          <Play size={18} />
        </button>
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-2 text-xs text-gray-400">
        {isSaving ? (
          <>
            <Loader2 className="animate-spin" size={12} /> Saving...
          </>
        ) : (
          <span className="flex items-center gap-1">
            <Save size={12} /> All changes saved
          </span>
        )}
      </div>
    </div>
  );
}
