import { CheckCircle2, Loader2, RotateCcw, Trash2, Wand2, X } from 'lucide-react';

import { getClassAccent } from '../constants';
import type { BBox } from '../types';

interface PropertiesPanelProps {
  classNames: Record<number, string>;
  addClassIds: number[];
  assignClassIds: number[];
  labels: BBox[];
  selectedIndices: number[];
  drawingClass: number | null;
  selectedImage: string | null;
  isApproved: boolean;
  onToggleAddMode: (classId: number) => void;
  onSelectedClassChange: (classId: number) => void;
  onDelete: () => void;
  onReset: () => void;
  onAutoLabelCurrent: () => void;
  onApprovalChange: (isApproved: boolean) => void;
  processingAction: string | null;
}

export function PropertiesPanel({
  classNames,
  addClassIds,
  assignClassIds,
  labels,
  selectedIndices,
  drawingClass,
  selectedImage,
  isApproved,
  processingAction,
  onToggleAddMode,
  onSelectedClassChange,
  onDelete,
  onReset,
  onAutoLabelCurrent,
  onApprovalChange,
}: PropertiesPanelProps) {
  const selectedCount = selectedIndices.length;
  const selectedClassIds = [...new Set(selectedIndices.map((index) => labels[index]?.class_id).filter((classId) => classId !== undefined))];
  const selectedClassId = selectedClassIds.length === 1 ? selectedClassIds[0] : null;

  return (
    <aside className="w-[300px] flex-shrink-0 bg-surface-container border-l border-outline-variant flex flex-col h-full z-10">
      {/* Class Palette */}
      <div className="p-4 border-b border-outline-variant flex flex-col gap-3">
        <span className="font-headline-sm text-headline-sm text-on-surface">Class Palette</span>
        <div className="space-y-2">
          {addClassIds.map((id) => {
            const isActive = drawingClass === id;
            const accent = getClassAccent(id, 0.2);
            return (
              <button
                key={id}
                onClick={() => onToggleAddMode(id)}
                className={`w-full text-left px-3 py-2 rounded font-label-sm text-label-sm transition-colors flex items-center gap-2 ${
                  isActive
                    ? 'bg-primary-container text-on-primary-container border border-primary-container font-bold shadow-[0_0_8px_rgba(45,212,191,0.2)]'
                    : 'border hover:opacity-80'
                }`}
                style={
                  isActive
                    ? undefined
                    : {
                        borderColor: accent.border,
                        color: accent.text,
                        backgroundColor: accent.bg,
                      }
                }
              >
                <span
                  className="w-3 h-3 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: isActive ? '#2dd4bf' : accent.border }}
                />
                {isActive ? 'Drawing...' : `${id}: ${classNames[id]}`}
              </button>
            );
          })}
        </div>
      </div>

      {/* Selection Properties */}
      <div className="p-4 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <span className="font-headline-sm text-headline-sm text-on-surface">Selection</span>
          {selectedCount > 0 && (
            <span className="font-code-md text-label-caps text-on-surface-variant bg-surface px-2 py-1 rounded border border-outline-variant">
              {selectedCount} selected
            </span>
          )}
        </div>

        {selectedCount > 0 ? (
          <div className="space-y-4">
            {/* Class Assignment */}
            <div>
              <label className="block font-label-caps text-label-caps text-on-surface-variant mb-2">
                Assign Class
              </label>
              <select
                value={selectedClassId ?? ''}
                onChange={(event) => onSelectedClassChange(Number(event.target.value))}
                className="w-full bg-surface border border-outline-variant text-on-surface rounded font-code-md text-code-md py-1.5 px-2 focus:border-primary-container focus:ring-1 focus:ring-primary-container focus:outline-none"
              >
                <option value="" disabled>
                  Select class...
                </option>
                {assignClassIds.map((id) => (
                  <option key={id} value={id}>
                    {id}: {classNames[id]}
                  </option>
                ))}
              </select>
            </div>

            <div className="h-px bg-outline-variant w-full" />

            {/* Delete */}
            <button
              onClick={onDelete}
              className="w-full py-2 bg-error-container/10 border border-error text-error font-label-sm text-label-sm rounded hover:bg-error-container/20 transition-colors flex items-center justify-center gap-2"
            >
              <Trash2 size={16} />
              Delete Selected ({selectedCount})
            </button>
          </div>
        ) : (
          <p className="text-on-surface-variant font-body-md text-body-md mb-4">
            Select a bounding box on the canvas to view and edit its properties.
          </p>
        )}

        {/* AI Current */}
        <button
          onClick={onAutoLabelCurrent}
          disabled={processingAction !== null || !selectedImage}
          className="w-full mt-4 py-2 bg-surface border border-outline-variant text-on-surface-variant font-label-sm text-label-sm rounded hover:bg-surface-container-high hover:text-on-surface transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {processingAction === 'autoLabelCurrent' ? <Loader2 className="animate-spin" size={16} /> : <Wand2 size={16} />}
          AI Current
        </button>

        {/* Reset */}
        <button
          onClick={onReset}
          disabled={processingAction !== null || !selectedImage}
          className="w-full mt-2 py-2 bg-surface border border-outline-variant text-on-surface-variant font-label-sm text-label-sm rounded hover:bg-surface-container-high hover:text-on-surface disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
        >
          <RotateCcw size={16} />
          Return to Origin
        </button>
      </div>

      {/* Bottom Action */}
      <div className="p-4 border-t border-outline-variant bg-surface-container-highest">
        <button
          onClick={() => onApprovalChange(!isApproved)}
          disabled={processingAction !== null || !selectedImage}
          className={`w-full py-2 font-label-sm text-label-sm rounded transition-colors active:scale-95 duration-100 font-bold flex items-center justify-center gap-2 disabled:opacity-50 ${
            isApproved
              ? 'border hover:opacity-80'
              : 'bg-primary-container text-on-primary-container hover:bg-primary-fixed'
          }`}
          style={
            isApproved
              ? {
                  borderColor: getClassAccent(3, 0.2).border,
                  color: getClassAccent(3, 0.2).text,
                  backgroundColor: getClassAccent(3, 0.2).bg,
                }
              : undefined
          }
        >
          {processingAction === 'approve' ? <Loader2 className="animate-spin" size={16} /> : isApproved ? <X size={16} /> : <CheckCircle2 size={16} />}
          {isApproved ? 'Unapprove Current Image' : 'Approve Current Image'}
        </button>
      </div>
    </aside>
  );
}
