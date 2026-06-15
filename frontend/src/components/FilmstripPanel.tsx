import { useRef } from 'react';
import { Loader2, Pencil, Upload, X } from 'lucide-react';

import type { ImageData } from '../types';

interface FilmstripPanelProps {
  images: ImageData[];
  selectedImage: string | null;
  processingAction: string | null;
  onUploadImages: (files: File[]) => void;
  onRenameSequential: () => void;
  onSelectImage: (filename: string) => void;
  onDeleteImage: (event: React.MouseEvent, filename: string) => void;
}

export function FilmstripPanel({
  images,
  selectedImage,
  processingAction,
  onUploadImages,
  onRenameSequential,
  onSelectImage,
  onDeleteImage,
}: FilmstripPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const approvedCount = images.filter((img) => img.is_approved).length;

  return (
    <aside className="w-[300px] flex-shrink-0 bg-surface-container-low border-r border-outline-variant flex flex-col h-full z-10">
      {/* Panel Header */}
      <div className="p-4 border-b border-outline-variant flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="font-headline-sm text-headline-sm text-on-surface">Process</span>
          <span className="font-code-md text-code-md text-on-surface-variant">
            <span className="text-primary font-bold">{approvedCount}</span>/{images.length} Approved
          </span>
        </div>

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
          disabled={processingAction !== null}
          className="w-full py-2 bg-surface border border-outline-variant text-on-surface font-label-sm text-label-sm rounded hover:bg-surface-container-high transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {processingAction === 'upload' ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
          Upload Images
        </button>

        <button
          onClick={onRenameSequential}
          disabled={processingAction !== null || images.length === 0}
          className="w-full py-1.5 text-on-surface-variant hover:text-on-surface font-label-sm text-label-sm rounded transition-colors flex items-center justify-center gap-1 border border-transparent hover:border-outline-variant disabled:opacity-50"
        >
          {processingAction === 'renameSequential' ? <Loader2 className="animate-spin" size={14} /> : <Pencil size={14} />}
          Rename All Sequential
        </button>
      </div>

      {/* Thumbnail List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {images.map((img) => {
          const isActive = selectedImage === img.name;
          const isApproved = img.is_approved;
          return (
            <div
              key={img.name}
              onClick={() => onSelectImage(img.name)}
              className={`group relative rounded p-2 cursor-pointer transition-colors ${
                isActive
                  ? isApproved
                    ? 'border-2 border-primary-container bg-surface'
                    : 'border-2 border-primary bg-surface'
                  : isApproved
                  ? 'border border-primary-container bg-surface-container-lowest'
                  : 'border border-outline-variant bg-surface-container-lowest hover:border-on-surface-variant'
              }`}
            >
              <div className="flex gap-3">
                {/* Image Preview */}
                <div className="w-16 h-12 bg-black rounded flex-shrink-0 overflow-hidden relative">
                  <img
                    src={img.image_url}
                    alt={img.name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  {img.has_label && (
                    <div className="absolute inset-0 border border-primary/50 pointer-events-none" />
                  )}
                </div>

                <div className="flex flex-col justify-center flex-1 min-w-0">
                  <span
                    className={`font-code-md text-label-caps truncate ${
                      isActive
                        ? 'text-on-surface'
                        : 'text-on-surface-variant group-hover:text-on-surface'
                    }`}
                  >
                    {img.name}
                  </span>
                </div>
                
                <div className="flex flex-col justify-between items-end flex-shrink-0">
                  <button
                    onClick={(event) => onDeleteImage(event, img.name)}
                    className="p-0.5 rounded text-on-surface-variant/0 group-hover:text-on-surface-variant hover:!text-error hover:bg-error-container/20 transition-colors"
                    title="Delete Image"
                  >
                    <X size={14} />
                  </button>
                  <div
                    className={`w-2.5 h-2.5 rounded-full ${isApproved ? 'bg-primary-container' : 'bg-error'}`}
                    title={isApproved ? "Approved" : "Pending"}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
