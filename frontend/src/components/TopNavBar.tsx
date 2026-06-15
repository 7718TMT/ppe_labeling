import { ChevronLeft, ChevronRight, Eye, EyeOff, Hand, Loader2, MousePointer2, PanelLeft, PanelRight, Save, Undo2, Download, Wand2 } from 'lucide-react';
import { Link } from 'react-router-dom';

import type { ImageData, InteractionMode, TaskInfo } from '../types';

interface TopNavBarProps {
  tasks: TaskInfo[];
  selectedTaskId: string;
  interactionMode: InteractionMode;
  overlayVisible: boolean;
  isSaving: boolean;
  processingAction: string | null;
  selectedImage: string | null;
  images: ImageData[];
  leftSidebarOpen: boolean;
  rightSidebarOpen: boolean;
  onTaskChange: (taskId: string) => void;
  onOverlayVisibleChange: (visible: boolean) => void;
  onInteractionModeChange: (mode: InteractionMode) => void;
  onUndo: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onProcess: () => void;
  onExportAll: () => void;
  onToggleLeftSidebar: () => void;
  onToggleRightSidebar: () => void;
}

export function TopNavBar({
  tasks,
  selectedTaskId,
  interactionMode,
  overlayVisible,
  isSaving,
  processingAction,
  images,
  leftSidebarOpen,
  rightSidebarOpen,
  onOverlayVisibleChange,
  onInteractionModeChange,
  onUndo,
  onPrevious,
  onNext,
  onProcess,
  onExportAll,
  onToggleLeftSidebar,
  onToggleRightSidebar,
}: TopNavBarProps) {
  const selectedTask = tasks.find((t) => t.id === selectedTaskId);
  
  const handleExportClick = () => {
    const unapprovedCount = images.filter((img) => !img.is_approved).length;
    if (unapprovedCount > 0) {
      if (!window.confirm(`There are ${unapprovedCount} unapproved images. Are you sure you want to export?`)) {
        return;
      }
    }
    onExportAll();
  };

  return (
    <header className="bg-surface-container border-b border-outline-variant h-toolbar-height flex justify-between items-center px-gutter z-50 flex-shrink-0 select-none">
      {/* Left: Brand & Task Selector & Toggle */}
      <div className="flex items-center gap-4 h-full">
        <button
          onClick={onToggleLeftSidebar}
          className={`w-8 h-8 flex items-center justify-center rounded transition-colors ${
            leftSidebarOpen ? 'bg-surface-container-high text-on-surface' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
          }`}
          title="Toggle Left Sidebar"
        >
          <PanelLeft size={18} />
        </button>
        <div className="text-headline-sm font-headline-sm font-bold text-primary flex items-center gap-2">
          <Link to="/" className="hover:underline">Home</Link>
          <span className="text-on-surface-variant text-sm font-normal">&gt;</span>
          <span className="text-on-surface">{selectedTask?.name || 'Loading...'}</span>
        </div>
      </div>

      {/* Center: Tools & Navigation */}
      <div className="flex items-center gap-1">
        {/* Undo */}
        <button
          onClick={onUndo}
          className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high rounded transition-colors"
          title="Undo (Ctrl+Z)"
        >
          <Undo2 size={18} />
        </button>

        {/* Overlay Toggle */}
        <button
          onClick={() => onOverlayVisibleChange(!overlayVisible)}
          className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high rounded transition-colors"
          title={overlayVisible ? 'Hide boxes' : 'Show boxes'}
        >
          {overlayVisible ? <Eye size={18} /> : <EyeOff size={18} />}
        </button>

        <div className="h-6 w-px bg-outline-variant mx-1" />

        {/* Mode Toggle */}
        <div className="flex bg-surface rounded p-0.5 border border-outline-variant">
          <button
            onClick={() => onInteractionModeChange('select')}
            className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${
              interactionMode === 'select'
                ? 'bg-primary-container text-on-primary-container'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
            title="Selection Mode (V)"
          >
            <MousePointer2 size={16} />
          </button>
          <button
            onClick={() => onInteractionModeChange('pan')}
            className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${
              interactionMode === 'pan'
                ? 'bg-primary-container text-on-primary-container'
                : 'text-on-surface-variant hover:text-on-surface'
            }`}
            title="Pan Mode (H)"
          >
            <Hand size={16} />
          </button>
        </div>

        <div className="h-6 w-px bg-outline-variant mx-1" />

        {/* Prev / Next */}
        <button
          onClick={onPrevious}
          className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high rounded transition-colors"
          title="Previous (A)"
        >
          <ChevronLeft size={18} />
        </button>
        <button
          onClick={onNext}
          className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high rounded transition-colors"
          title="Next (D)"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Right: Actions & Save Status */}
      <div className="flex items-center gap-3">
        {/* Save status */}
        <div className="flex items-center gap-1.5 text-label-sm font-label-sm text-on-surface-variant mr-2">
          {isSaving ? (
            <>
              <Loader2 className="animate-spin" size={12} />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <Save size={12} />
              <span>Saved</span>
            </>
          )}
        </div>

        <div className="h-6 w-px bg-outline-variant" />

        {/* Export All */}
        <button
          onClick={handleExportClick}
          disabled={processingAction !== null || images.length === 0}
          className="px-4 h-8 bg-surface border border-outline-variant text-on-surface font-label-sm text-label-sm rounded hover:bg-surface-container-high transition-colors active:scale-95 duration-100 flex items-center gap-2 disabled:opacity-50"
        >
          {processingAction === 'exportAll' ? <Loader2 className="animate-spin" size={16} /> : <Download size={16} />}
          Export Dataset
        </button>

        {/* AI Batch Label */}
        <button
          onClick={onProcess}
          disabled={processingAction !== null || images.length === 0}
          className="px-4 h-8 bg-primary-container text-on-primary-container font-label-sm text-label-sm rounded hover:bg-primary-fixed transition-colors active:scale-95 duration-100 font-bold flex items-center gap-2 disabled:opacity-50"
        >
          {processingAction === 'autoLabelAll' ? <Loader2 className="animate-spin" size={16} /> : <Wand2 size={16} />}
          AI Batch Label
        </button>
        
        {/* Right Toggle */}
        <button
          onClick={onToggleRightSidebar}
          className={`ml-2 w-8 h-8 flex items-center justify-center rounded transition-colors ${
            rightSidebarOpen ? 'bg-surface-container-high text-on-surface' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
          }`}
          title="Toggle Right Sidebar"
        >
          <PanelRight size={18} />
        </button>
      </div>
    </header>
  );
}
