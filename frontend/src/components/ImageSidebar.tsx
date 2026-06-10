import { Loader2, Play, Save, X } from 'lucide-react';

import type { ImageData } from '../types';

interface ImageSidebarProps {
  images: ImageData[];
  selectedImage: string | null;
  processing: boolean;
  onProcess: () => void;
  onVisualize: () => void;
  onSelectImage: (filename: string) => void;
  onDeleteImage: (event: React.MouseEvent, filename: string) => void;
}

export function ImageSidebar({
  images,
  selectedImage,
  processing,
  onProcess,
  onVisualize,
  onSelectImage,
  onDeleteImage,
}: ImageSidebarProps) {
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
