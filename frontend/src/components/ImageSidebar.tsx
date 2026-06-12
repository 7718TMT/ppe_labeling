import { Check, Loader2, Pencil, Play, Save, X } from 'lucide-react';

import type { ImageData, RenamePreviewItem } from '../types';

interface ImageSidebarProps {
  images: ImageData[];
  selectedImage: string | null;
  processing: boolean;
  renamePreview: RenamePreviewItem[];
  renameCount: number;
  renaming: boolean;
  canRename: boolean;
  onProcess: () => void;
  onVisualize: () => void;
  onPreviewRenames: () => void;
  onApplyRenames: () => void;
  onSelectImage: (filename: string) => void;
  onDeleteImage: (event: React.MouseEvent, filename: string) => void;
}

export function ImageSidebar({
  images,
  selectedImage,
  processing,
  renamePreview,
  renameCount,
  renaming,
  canRename,
  onProcess,
  onVisualize,
  onPreviewRenames,
  onApplyRenames,
  onSelectImage,
  onDeleteImage,
}: ImageSidebarProps) {
  const changedItems = renamePreview.filter((item) => item.will_rename);

  return (
    <div className="w-64 border-r border-gray-700 flex flex-col">
      <div className="p-4 border-b border-gray-700 flex flex-col gap-2">
        <button
          onClick={onProcess}
          disabled={processing}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 py-2 px-4 rounded transition text-sm font-medium"
        >
          {processing ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
          AI Auto-Label All
        </button>
        <button
          onClick={onVisualize}
          disabled={processing}
          className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 py-2 px-4 rounded transition text-sm font-medium"
        >
          {processing ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
          Generate Visuals
        </button>
        {canRename && (
          <div className="mt-2 border-t border-gray-700 pt-3 flex flex-col gap-2">
            <div className="flex gap-2">
              <button
                onClick={onPreviewRenames}
                disabled={processing || renaming}
                className="flex-1 flex items-center justify-center gap-1 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 py-2 px-2 rounded transition text-xs font-medium"
                title="Preview filename suggestions from labels"
              >
                {renaming ? <Loader2 className="animate-spin" size={14} /> : <Pencil size={14} />}
                Preview Names
              </button>
              <button
                onClick={onApplyRenames}
                disabled={processing || renaming || renameCount === 0}
                className="flex items-center justify-center bg-emerald-700 hover:bg-emerald-600 disabled:bg-emerald-950 disabled:text-gray-500 py-2 px-2 rounded transition"
                title="Apply suggested filename changes"
              >
                <Check size={15} />
              </button>
            </div>
            {renamePreview.length > 0 && (
              <div className="max-h-52 overflow-y-auto rounded border border-gray-700 bg-gray-950/60">
                <div className="px-2 py-1 text-[11px] text-gray-400 border-b border-gray-800">
                  {renameCount} rename{renameCount === 1 ? '' : 's'} suggested
                </div>
                {changedItems.length === 0 ? (
                  <div className="px-2 py-2 text-xs text-gray-400">All filenames already match their labels.</div>
                ) : (
                  changedItems.map((item) => (
                    <div key={item.original_name} className="px-2 py-2 border-b border-gray-800 last:border-b-0">
                      <div className="text-[11px] text-gray-500 truncate" title={item.original_name}>
                        {item.original_name}
                      </div>
                      <div className="text-xs text-emerald-300 truncate" title={item.suggested_name}>
                        {item.suggested_name}
                      </div>
                      <div className="text-[10px] text-gray-500 truncate" title={item.reason}>
                        {item.reason}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto cursor-default">
        {images.map((img) => (
          <div
            key={img.name}
            onClick={() => onSelectImage(img.name)}
            className={`p-3 cursor-pointer hover:bg-gray-800 transition flex items-center justify-between gap-2 ${
              selectedImage === img.name ? 'bg-gray-700 border-l-4 border-blue-500' : ''
            }`}
          >
            <span className="truncate flex-1 text-sm">{img.name}</span>
            <div className="flex items-center gap-2">
              {img.has_label && (
                <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" title="Has labels" />
              )}
              <button
                onClick={(event) => onDeleteImage(event, img.name)}
                className="p-1 hover:bg-red-900/50 rounded text-gray-500 hover:text-red-400 transition"
                title="Delete Image"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
