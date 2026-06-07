import { Hand, Loader2, MousePointer2, Play, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';

import { CLASS_NAMES } from '../constants';
import type { InteractionMode } from '../types';

interface ToolbarProps {
  drawingClass: number | null;
  interactionMode: InteractionMode;
  selectedCount: number;
  isResetting: boolean;
  isSaving: boolean;
  selectedImage: string | null;
  onToggleAddMode: (classId: number) => void;
  onInteractionModeChange: (mode: InteractionMode) => void;
  onDeleteSelected: () => void;
  onReset: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

export function Toolbar({
  drawingClass,
  interactionMode,
  selectedCount,
  isResetting,
  isSaving,
  selectedImage,
  onToggleAddMode,
  onInteractionModeChange,
  onDeleteSelected,
  onReset,
  onPrevious,
  onNext,
}: ToolbarProps) {
  return (
    <div className="h-14 border-b border-gray-700 flex items-center px-4 gap-4 bg-gray-800 cursor-default">
      <div className="flex gap-2">
        {[0, 1, 2].map((id) => {
          const colors = [
            { active: 'bg-red-600 text-white shadow-lg shadow-red-500/50', hover: 'bg-gray-700 hover:bg-red-900/40 text-red-200' },
            { active: 'bg-blue-600 text-white shadow-lg shadow-blue-500/50', hover: 'bg-gray-700 hover:bg-blue-900/40 text-blue-200' },
            { active: 'bg-green-600 text-white shadow-lg shadow-green-500/50', hover: 'bg-gray-700 hover:bg-green-900/40 text-green-200' },
          ];
          return (
            <button
              key={id}
              onClick={() => onToggleAddMode(id)}
              className={`flex items-center gap-1 px-3 py-1 rounded text-sm transition font-medium ${
                drawingClass === id ? colors[id].active : colors[id].hover
              }`}
            >
              <Plus size={14} /> {drawingClass === id ? `Drawing ${CLASS_NAMES[id]}...` : `Add ${CLASS_NAMES[id]}`}
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
