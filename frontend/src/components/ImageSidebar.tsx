import { useRef } from 'react';

import { Download, Loader2, Play, Save, Upload, Wand2, X } from 'lucide-react';

import type { ImageData } from '../types';

interface ImageSidebarProps {
  images: ImageData[];
  selectedImage: string | null;
  processing: boolean;
  onUploadImages: (files: File[]) => void;
  onAutoLabelCurrent: () => void;
  onProcess: () => void;
  onVisualize: () => void;
  onExportCurrent: () => void;
  onExportAll: () => void;
  onRenameSequential: () => void;
  onSelectImage: (filename: string) => void;
  onDeleteImage: (event: React.MouseEvent, filename: string) => void;
}

export function ImageSidebar({
  images,
  selectedImage,
  processing,
  onUploadImages,
  onAutoLabelCurrent,
  onProcess,
  onVisualize,
  onExportCurrent,
  onExportAll,
  onRenameSequential,
  onSelectImage,
  onDeleteImage,
}: ImageSidebarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="w-64 border-r border-gray-700 flex flex-col">
      <div className="p-4 border-b border-gray-700 flex flex-col gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png,image/jpeg,image/png"
          multiple
          className="hidden"
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            if (files.length > 0) onUploadImages(files);
            event.target.value = '';
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={processing}
          className="w-full flex items-center justify-center gap-2 bg-emerald-700 hover:bg-emerald-600 disabled:bg-emerald-900 py-2 px-4 rounded transition text-sm font-medium"
        >
          {processing ? <Loader2 className="animate-spin" size={18} /> : <Upload size={18} />}
          Upload Images
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onAutoLabelCurrent}
            disabled={processing || !selectedImage}
            className="flex items-center justify-center gap-1 bg-blue-900/70 hover:bg-blue-800 disabled:bg-gray-800 disabled:opacity-50 py-2 px-2 rounded transition text-xs font-medium"
          >
            {processing ? <Loader2 className="animate-spin" size={14} /> : <Wand2 size={14} />}
            AI Current
          </button>
          <button
            onClick={onProcess}
            disabled={processing || images.length === 0}
            className="flex items-center justify-center gap-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 disabled:opacity-50 py-2 px-2 rounded transition text-xs font-medium"
          >
            {processing ? <Loader2 className="animate-spin" size={14} /> : <Play size={14} />}
            AI All
          </button>
        </div>
        <button
          onClick={onVisualize}
          disabled={processing || images.length === 0}
          className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:opacity-50 py-2 px-4 rounded transition text-sm font-medium"
        >
          {processing ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
          Generate Visuals
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onExportCurrent}
            disabled={processing || !selectedImage}
            className="flex items-center justify-center gap-1 bg-slate-700 hover:bg-slate-600 disabled:bg-gray-800 disabled:opacity-50 py-2 px-2 rounded transition text-xs font-medium"
          >
            <Download size={14} />
            Export Current
          </button>
          <button
            onClick={onExportAll}
            disabled={processing || images.length === 0}
            className="flex items-center justify-center gap-1 bg-slate-700 hover:bg-slate-600 disabled:bg-gray-800 disabled:opacity-50 py-2 px-2 rounded transition text-xs font-medium"
          >
            <Download size={14} />
            Export All
          </button>
        </div>
        <button
          onClick={onRenameSequential}
          disabled={processing || images.length === 0}
          className="w-full flex items-center justify-center gap-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:opacity-50 py-2 px-4 rounded transition text-sm font-medium"
        >
          <Save size={18} />
          Rename Sequential
        </button>
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
