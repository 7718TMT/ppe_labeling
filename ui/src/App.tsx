import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Stage, Layer, Image as KonvaImage, Rect, Transformer } from 'react-konva';
import { Play, Save, Plus, Trash2, Loader2, RotateCcw, Hand, MousePointer2, X } from 'lucide-react';

interface BBox {
  class_id: number;
  x_center: number;
  y_center: number;
  w: number;
  h: number;
}

interface ImageData {
  name: string;
  has_label: boolean;
}

const CLASS_COLORS = [
  'rgba(255, 0, 0, 0.5)',   // Class 0: Human (Red)
  'rgba(0, 0, 255, 0.5)',   // Class 1: Helmet (Blue)
  'rgba(0, 255, 0, 0.5)'    // Class 2: Vest (Green)
];

const CLASS_NAMES = ['Human', 'Helmet', 'Vest'];

type InteractionMode = 'pan' | 'select';

const App: React.FC = () => {
  const [images, setImages] = useState<ImageData[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [labels, setLabels] = useState<BBox[]>([]);
  const [history, setHistory] = useState<BBox[][]>([]);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [containerSize, setContainerSize] = useState({ width: 800, height: 600 });
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [imageObj, setImageObj] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);
  const [initialScale, setInitialScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [isSpacePressed, setIsSpacePressed] = useState(false);
  const isSpacePressedRef = useRef(false);
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('select');

  const clampPosition = (x: number, y: number, currentScale: number) => {
    const stageWidth = containerSize.width;
    const stageHeight = containerSize.height;
    const imgWidth = imageSize.width * currentScale;
    const imgHeight = imageSize.height * currentScale;

    let newX = x;
    let newY = y;

    // Horizontal clamping
    if (imgWidth <= stageWidth) {
      // If smaller than screen, keep it centered or at least within bounds
      // To strictly follow "relocate to center", we can force it if scale is initialScale
      if (Math.abs(currentScale - initialScale) < 0.001) {
        newX = (stageWidth - imgWidth) / 2;
      } else {
        newX = Math.max(0, Math.min(stageWidth - imgWidth, x));
      }
    } else {
      // If larger than screen, don't allow edges to move inside
      newX = Math.max(stageWidth - imgWidth, Math.min(0, x));
    }

    // Vertical clamping
    if (imgHeight <= stageHeight) {
      if (Math.abs(currentScale - initialScale) < 0.001) {
        newY = (stageHeight - imgHeight) / 2;
      } else {
        newY = Math.max(0, Math.min(stageHeight - imgHeight, y));
      }
    } else {
      newY = Math.max(stageHeight - imgHeight, Math.min(0, y));
    }

    return { x: newX, y: newY };
  };

  // Selection/Drawing state
  const [selectionRect, setSelectionRect] = useState<{ x1: number, y1: number, x2: number, y2: number } | null>(null);
  const [drawingClass, setDrawingClass] = useState<number | null>(null);

  const stageRef = useRef<any>(null);
  const transformerRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchImages();
    updateContainerSize();
    window.addEventListener('resize', updateContainerSize);
    return () => window.removeEventListener('resize', updateContainerSize);
  }, []);

  // Auto-save logic
  useEffect(() => {
    if (selectedImage && labels.length > 0) {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      
      saveTimeoutRef.current = setTimeout(() => {
        autoSaveLabels();
      }, 1000); // Save 1 second after last change
    }
    return () => {
        if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [labels]);

  const autoSaveLabels = async () => {
    if (!selectedImage) return;
    setIsSaving(true);
    try {
      await axios.put(`/api/labels/${selectedImage}`, {
        filename: selectedImage,
        boxes: labels
      });
      fetchImages(); // Refresh status indicators
    } catch (error) {
      console.error('Error auto-saving labels:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    if (!selectedImage) return;
    if (!confirm("Are you sure? This will remove all your manual changes for this image and re-run the AI detection.")) return;
    
    setIsResetting(true);
    try {
      await axios.post(`/api/reset?filename=${selectedImage}`);
      fetchLabels(selectedImage);
    } catch (error) {
      console.error('Reset failed:', error);
      alert('Reset failed. Check console.');
    } finally {
      setIsResetting(false);
    }
  };

  const updateContainerSize = () => {
    if (containerRef.current) {
      setContainerSize({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight
      });
    }
  };

  useEffect(() => {
    if (selectedIndices.length > 0 && transformerRef.current) {
      const nodes = selectedIndices.map(index => stageRef.current.findOne('.box-' + index)).filter(Boolean);
      transformerRef.current.nodes(nodes);
      transformerRef.current.getLayer().batchDraw();
    } else if (transformerRef.current) {
      transformerRef.current.nodes([]);
    }
  }, [selectedIndices, labels]);

  useEffect(() => {
    if (selectedImage) {
      fetchLabels(selectedImage);
      const img = new Image();
      img.src = `/images/${selectedImage}`;
      img.onload = () => {
        setImageObj(img);
        setImageSize({ width: img.width, height: img.height });
        
        const padding = 40;
        const availableW = containerSize.width - padding;
        const availableH = containerSize.height - padding;
        const scaleW = availableW / img.width;
        const scaleH = availableH / img.height;
        const fitScale = Math.min(scaleW, scaleH, 1);
        
        setScale(fitScale);
        setInitialScale(fitScale);
        setPosition({
          x: (containerSize.width - img.width * fitScale) / 2,
          y: (containerSize.height - img.height * fitScale) / 2
        });
        setHistory([]);
        setSelectedIndices([]);
        setDrawingClass(null);
      };
    }
  }, [selectedImage, containerSize.width, containerSize.height]);

  const pushToHistory = (newLabels: BBox[]) => {
    setHistory(prev => [...prev, labels]);
    setLabels(newLabels);
  };

  const undo = () => {
    if (history.length > 0) {
      const prev = history[history.length - 1];
      setHistory(prevHistory => prevHistory.slice(0, -1));
      setLabels(prev);
      setSelectedIndices([]);
    }
  };

  const handleWheel = (e: any) => {
    e.evt.preventDefault();
    const stage = stageRef.current;
    if (!stage) return;

    const oldScale = stage.scaleX();
    const pointer = stage.getPointerPosition();

    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    };

    const speed = 1.1;
    let newScale = e.evt.deltaY > 0 ? oldScale / speed : oldScale * speed;

    // Limit zoom: don't allow zooming out smaller than initial "fit" scale
    const MAX_SCALE = 15;
    newScale = Math.max(initialScale, Math.min(MAX_SCALE, newScale));

    const newPos = clampPosition(
      pointer.x - mousePointTo.x * newScale,
      pointer.y - mousePointTo.y * newScale,
      newScale
    );

    setScale(newScale);
    setPosition(newPos);
  };

  const fetchImages = async () => {
    try {
      const response = await axios.get('/api/images');
      setImages(response.data);
      if (response.data.length > 0 && !selectedImage) {
        setSelectedImage(response.data[0].name);
      }
    } catch (error) {
      console.error('Error fetching images:', error);
    }
  };

  const handleVisualize = async () => {
    setProcessing(true);
    try {
      await axios.post('/api/visualize');
      alert('Visualization completed! Check labeled_images folder.');
    } catch (error) {
      console.error('Visualization failed:', error);
      alert('Visualization failed.');
    } finally {
      setProcessing(false);
    }
  };

  const goToNext = () => {
    if (!selectedImage || images.length === 0) return;
    const currentIndex = images.findIndex(img => img.name === selectedImage);
    if (currentIndex < images.length - 1) {
      setSelectedImage(images[currentIndex + 1].name);
    }
  };

  const goToPrev = () => {
    if (!selectedImage || images.length === 0) return;
    const currentIndex = images.findIndex(img => img.name === selectedImage);
    if (currentIndex > 0) {
      setSelectedImage(images[currentIndex - 1].name);
    }
  };

  const fetchLabels = async (filename: string) => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/labels/${filename}`);
      setLabels(response.data.boxes);
      setHistory([]);
    } catch (error) {
      console.error('Error fetching labels:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleProcess = async () => {
    setProcessing(true);
    try {
      await axios.post('/api/process');
      fetchImages();
      if (selectedImage) fetchLabels(selectedImage);
      alert('Processing completed!');
    } catch (error) {
      console.error('Processing failed:', error);
      alert('Processing failed. Check console for details.');
    } finally {
      setProcessing(false);
    }
  };

  const saveLabels = async () => {
    if (!selectedImage) return;
    try {
      await axios.put(`/api/labels/${selectedImage}`, {
        filename: selectedImage,
        boxes: labels
      });
      alert('Labels saved successfully!');
    } catch (error) {
      console.error('Error saving labels:', error);
    }
  };

  const handleDeleteImage = async (e: React.MouseEvent, filename: string) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete ${filename}? This cannot be undone.`)) return;
    
    try {
      await axios.delete(`/api/images/${filename}`);
      if (selectedImage === filename) {
        setSelectedImage(null);
        setLabels([]);
        setImageObj(null);
      }
      fetchImages();
    } catch (error) {
      console.error('Error deleting image:', error);
      alert('Failed to delete image.');
    }
  };

  const handleBoxChange = (index: number, newAttrs: any) => {
    const newLabels = [...labels];
    const x_center = (newAttrs.x + newAttrs.width / 2) / imageSize.width;
    const y_center = (newAttrs.y + newAttrs.height / 2) / imageSize.height;
    const w = newAttrs.width / imageSize.width;
    const h = newAttrs.height / imageSize.height;

    newLabels[index] = {
      ...newLabels[index],
      x_center: Math.max(0, Math.min(1, x_center)),
      y_center: Math.max(0, Math.min(1, y_center)),
      w: Math.max(0.001, Math.min(1, w)),
      h: Math.max(0.001, Math.min(1, h))
    };
    pushToHistory(newLabels);
  };

  const handleMultiBoxChange = (changes: {index: number, newAttrs: any}[]) => {
    const newLabels = [...labels];
    changes.forEach(({index, newAttrs}) => {
      const x_center = (newAttrs.x + newAttrs.width / 2) / imageSize.width;
      const y_center = (newAttrs.y + newAttrs.height / 2) / imageSize.height;
      const w = newAttrs.width / imageSize.width;
      const h = newAttrs.height / imageSize.height;
      newLabels[index] = {
        ...newLabels[index],
        x_center: Math.max(0, Math.min(1, x_center)),
        y_center: Math.max(0, Math.min(1, y_center)),
        w: Math.max(0.001, Math.min(1, w)),
        h: Math.max(0.001, Math.min(1, h))
      };
    });
    pushToHistory(newLabels);
  };

  const handleDelete = () => {
    if (selectedIndices.length > 0) {
      const newLabels = labels.filter((_, i) => !selectedIndices.includes(i));
      pushToHistory(newLabels);
      setSelectedIndices([]);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === ' ') {
        if (document.activeElement?.tagName === 'INPUT') return;
        e.preventDefault();
        if (!e.repeat) {
          isSpacePressedRef.current = true;
          setIsSpacePressed(true);
        }
        return;
      }

      if (e.ctrlKey && e.key === 'z') {
        e.preventDefault();
        undo();
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (document.activeElement?.tagName === 'INPUT') return;
        handleDelete();
      } else if (e.key === 'Escape') {
        setDrawingClass(null);
        setSelectionRect(null);
      } else if (e.key === 'ArrowRight') {
        setPosition(pos => clampPosition(pos.x - 50, pos.y, scale));
      } else if (e.key === 'ArrowLeft') {
        setPosition(pos => clampPosition(pos.x + 50, pos.y, scale));
      } else if (e.key === 'ArrowUp') {
        setPosition(pos => clampPosition(pos.x, pos.y + 50, scale));
      } else if (e.key === 'ArrowDown') {
        setPosition(pos => clampPosition(pos.x, pos.y - 50, scale));
      } else if (e.key.toLowerCase() === 'd') {
        if (document.activeElement?.tagName === 'INPUT') return;
        goToNext();
      } else if (e.key.toLowerCase() === 'a') {
        if (document.activeElement?.tagName === 'INPUT') return;
        goToPrev();
      } else if (e.key.toLowerCase() === 'h') {
        if (document.activeElement?.tagName === 'INPUT') return;
        setInteractionMode('pan');
      } else if (e.key.toLowerCase() === 'v') {
        if (document.activeElement?.tagName === 'INPUT') return;
        setInteractionMode('select');
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === ' ') {
        isSpacePressedRef.current = false;
        setIsSpacePressed(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [selectedIndices, labels, history, isSpacePressed]);

  const toggleAddMode = (classId: number) => {
    if (drawingClass === classId) {
      setDrawingClass(null);
    } else {
      setDrawingClass(classId);
      setSelectedIndices([]);
    }
  };

  const handleMouseDown = (e: any) => {
    // Right click (2) or Middle click (1) or Space + Left click (0) or Pan Mode + Left Click for panning
    if (e.evt.button === 2 || e.evt.button === 1 || (e.evt.button === 0 && (isSpacePressedRef.current || interactionMode === 'pan'))) {
      e.evt.preventDefault();
      setIsPanning(true);
      return;
    }

    const isStage = e.target === e.target.getStage();
    const isImage = e.target.className === 'Image';
    
    if (!isStage && !isImage) return;
    
    const pos = stageRef.current.getPointerPosition();
    const stageScale = stageRef.current.scaleX();
    const stageX = stageRef.current.x();
    const stageY = stageRef.current.y();
    
    const x = (pos.x - stageX) / stageScale;
    const y = (pos.y - stageY) / stageScale;
    
    setSelectionRect({ x1: x, y1: y, x2: x, y2: y });
    if (drawingClass === null) {
      setSelectedIndices([]);
    }
  };

  const handleMouseMove = (e: any) => {
    if (isPanning) {
      const dx = e.evt.movementX;
      const dy = e.evt.movementY;
      setPosition(pos => clampPosition(pos.x + dx, pos.y + dy, scale));
      return;
    }
    if (!selectionRect) return;
    const pos = stageRef.current.getPointerPosition();
    const stageScale = stageRef.current.scaleX();
    const stageX = stageRef.current.x();
    const stageY = stageRef.current.y();
    
    const x = (pos.x - stageX) / stageScale;
    const y = (pos.y - stageY) / stageScale;
    
    setSelectionRect({ ...selectionRect, x2: x, y2: y });
  };

  const handleMouseUp = () => {
    if (isPanning) {
      setIsPanning(false);
      return;
    }
    if (!selectionRect) return;
    
    const x1 = Math.min(selectionRect.x1, selectionRect.x2);
    const y1 = Math.min(selectionRect.y1, selectionRect.y2);
    const x2 = Math.max(selectionRect.x1, selectionRect.x2);
    const y2 = Math.max(selectionRect.y1, selectionRect.y2);

    if (drawingClass !== null) {
      // Finalize drawing new box
      const width = x2 - x1;
      const height = y2 - y1;
      
      // Only add if it has some size
      if (width > 2 && height > 2) {
        const x_center = (x1 + width / 2) / imageSize.width;
        const y_center = (y1 + height / 2) / imageSize.height;
        const w = width / imageSize.width;
        const h = height / imageSize.height;

        const newBox: BBox = {
          class_id: drawingClass,
          x_center: Math.max(0, Math.min(1, x_center)),
          y_center: Math.max(0, Math.min(1, y_center)),
          w: Math.max(0.001, Math.min(1, w)),
          h: Math.max(0.001, Math.min(1, h))
        };
        pushToHistory([...labels, newBox]);
        setDrawingClass(null); // Exit drawing mode after one box
      }
      setSelectionRect(null);
    } else {
      // Finalize marquee selection
      const newSelectedIndices: number[] = [];
      labels.forEach((box, i) => {
        const width = box.w * imageSize.width;
        const height = box.h * imageSize.height;
        const bx = (box.x_center * imageSize.width) - width / 2;
        const by = (box.y_center * imageSize.height) - height / 2;
        
        if (bx >= x1 && by >= y1 && (bx + width) <= x2 && (by + height) <= y2) {
          newSelectedIndices.push(i);
        }
      });
      
      setSelectedIndices(newSelectedIndices);
      setSelectionRect(null);
    }
  };

  return (
    <div className={`flex h-screen bg-gray-900 text-white ${drawingClass !== null ? 'cursor-crosshair' : ''}`}>
      <div className="w-64 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700 flex flex-col gap-2">
          <button
            onClick={handleProcess}
            disabled={processing}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 py-2 px-4 rounded transition text-sm font-medium"
          >
            {processing ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
            AI Auto-Label All
          </button>
          <button
            onClick={handleVisualize}
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
              onClick={() => setSelectedImage(img.name)}
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
                  onClick={(e) => handleDeleteImage(e, img.name)}
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

      <div className="flex-1 flex flex-col">
        <div className="h-14 border-b border-gray-700 flex items-center px-4 gap-4 bg-gray-800 cursor-default">
          <div className="flex gap-2">
            {[0, 1, 2].map((id) => {
              const colors = [
                { active: 'bg-red-600 text-white shadow-lg shadow-red-500/50', hover: 'bg-gray-700 hover:bg-red-900/40 text-red-200' }, // Human
                { active: 'bg-blue-600 text-white shadow-lg shadow-blue-500/50', hover: 'bg-gray-700 hover:bg-blue-900/40 text-blue-200' }, // Helmet
                { active: 'bg-green-600 text-white shadow-lg shadow-green-500/50', hover: 'bg-gray-700 hover:bg-green-900/40 text-green-200' } // Vest
              ];
              return (
                <button
                  key={id}
                  onClick={() => toggleAddMode(id)}
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
              onClick={() => setInteractionMode('select')}
              className={`p-1 rounded transition ${interactionMode === 'select' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
              title="Selection Mode (V)"
            >
              <MousePointer2 size={18} />
            </button>
            <button
              onClick={() => setInteractionMode('pan')}
              className={`p-1 rounded transition ${interactionMode === 'pan' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
              title="Pan Mode (H)"
            >
              <Hand size={18} />
            </button>
          </div>
          <div className="h-6 w-px bg-gray-600 mx-2" />
          <button
            onClick={handleDelete}
            disabled={selectedIndices.length === 0}
            className="flex items-center gap-1 bg-red-900/50 hover:bg-red-800/50 disabled:opacity-50 px-3 py-1 rounded text-sm text-red-400 transition"
          >
            <Trash2 size={14} /> Delete Selected
          </button>
          <div className="h-6 w-px bg-gray-600 mx-2" />
          <button
            onClick={handleReset}
            disabled={isResetting || !selectedImage}
            className="flex items-center gap-1 bg-orange-900/50 hover:bg-orange-800/50 disabled:opacity-50 px-3 py-1 rounded text-sm text-orange-400 transition"
          >
            {isResetting ? <Loader2 className="animate-spin" size={14} /> : <RotateCcw size={14} />} 
            Return to Origin
          </button>
          <div className="h-6 w-px bg-gray-600 mx-2" />
          <div className="flex gap-1">
            <button
              onClick={goToPrev}
              className="p-1 hover:bg-gray-700 rounded transition"
              title="Previous (A)"
            >
              <Play size={18} className="rotate-180" />
            </button>
            <button
              onClick={goToNext}
              className="p-1 hover:bg-gray-700 rounded transition"
              title="Next (D)"
            >
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
              <span className="flex items-center gap-1"><Save size={12} /> All changes saved</span>
            )}
          </div>
        </div>

        <div ref={containerRef} className="flex-1 overflow-hidden bg-black flex items-center justify-center relative">
          {loading ? (
            <Loader2 className="animate-spin text-blue-500" size={48} />
          ) : imageObj ? (
            <Stage
              ref={stageRef}
              width={containerSize.width}
              height={containerSize.height}
              scaleX={scale}
              scaleY={scale}
              x={position.x}
              y={position.y}
              onWheel={handleWheel}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onContextMenu={(e) => e.evt.preventDefault()}
              style={{ cursor: (isPanning || isSpacePressed || interactionMode === 'pan') ? (isPanning ? 'grabbing' : 'grab') : drawingClass !== null ? 'crosshair' : 'default' }}
            >
              <Layer>
                <KonvaImage image={imageObj} />
                {labels
                  .map((box, index) => ({ box, index }))
                  .sort((a, b) => {
                    const order: Record<number, number> = { 0: 0, 2: 1, 1: 2 }; // Human (back) -> Vest -> Helmet (front)
                    return (order[a.box.class_id] ?? 0) - (order[b.box.class_id] ?? 0);
                  })
                  .map(({ box, index: i }) => {
                    const width = box.w * imageSize.width;
                    const height = box.h * imageSize.height;
                    const x = (box.x_center * imageSize.width) - width / 2;
                    const y = (box.y_center * imageSize.height) - height / 2;

                    return (
                      <Rect
                        key={i}
                        name={'box-' + i}
                        x={x}
                        y={y}
                        width={width}
                        height={height}
                        fill={CLASS_COLORS[box.class_id]}
                        stroke={selectedIndices.includes(i) ? 'white' : 'transparent'}
                        strokeWidth={2 / scale}
                        draggable={drawingClass === null && !isSpacePressed && interactionMode === 'select'}
                        listening={drawingClass === null && !isSpacePressed && interactionMode === 'select'}
                        onClick={(e) => {
                          if (drawingClass !== null) return;
                          e.cancelBubble = true;
                          if (e.evt.shiftKey) {
                            setSelectedIndices(prev => 
                              prev.includes(i) ? prev.filter(idx => idx !== i) : [...prev, i]
                            );
                          } else {
                            setSelectedIndices([i]);
                          }
                        }}
                        onDragStart={(e) => {
                          e.cancelBubble = true;
                        }}
                        onDragMove={(e) => {
                          e.cancelBubble = true;
                        }}
                        onDragEnd={(e) => {
                          e.cancelBubble = true;
                          if (selectedIndices.length > 1 && selectedIndices.includes(i)) {
                            // Handle multi-drag
                            const changes = selectedIndices.map(idx => {
                              const node = stageRef.current.findOne('.box-' + idx);
                              return {
                                index: idx,
                                newAttrs: {
                                  x: node.x(),
                                  y: node.y(),
                                  width: node.width() * node.scaleX(),
                                  height: node.height() * node.scaleY()
                                }
                              };
                            });
                            handleMultiBoxChange(changes);
                          } else {
                            handleBoxChange(i, {
                              x: e.target.x(),
                              y: e.target.y(),
                              width: e.target.width() * e.target.scaleX(),
                              height: e.target.height() * e.target.scaleY()
                            });
                          }
                          e.target.scaleX(1);
                          e.target.scaleY(1);
                        }}
                        onTransformStart={(e) => {
                          e.cancelBubble = true;
                        }}
                        onTransform={(e) => {
                          e.cancelBubble = true;
                        }}
                        onTransformEnd={(e) => {
                          e.cancelBubble = true;
                          if (selectedIndices.length > 1) {
                              const changes = selectedIndices.map(idx => {
                                  const node = stageRef.current.findOne('.box-' + idx);
                                  return {
                                      index: idx,
                                      newAttrs: {
                                          x: node.x(),
                                          y: node.y(),
                                          width: node.width() * node.scaleX(),
                                          height: node.height() * node.scaleY()
                                      }
                                  };
                              });
                              handleMultiBoxChange(changes);
                          } else {
                              const node = e.target;
                              handleBoxChange(i, {
                                  x: node.x(),
                                  y: node.y(),
                                  width: node.width() * node.scaleX(),
                                  height: node.height() * node.scaleY()
                              });
                          }
                          e.target.scaleX(1);
                          e.target.scaleY(1);
                        }}
                      />
                    );
                  })}
                {selectionRect && (
                  <Rect
                    x={Math.min(selectionRect.x1, selectionRect.x2)}
                    y={Math.min(selectionRect.y1, selectionRect.y2)}
                    width={Math.abs(selectionRect.x2 - selectionRect.x1)}
                    height={Math.abs(selectionRect.y2 - selectionRect.y1)}
                    fill={drawingClass !== null ? CLASS_COLORS[drawingClass] : "rgba(0, 161, 255, 0.3)"}
                    stroke={drawingClass !== null ? "white" : "#00a1ff"}
                    strokeWidth={1 / scale}
                    listening={false}
                  />
                )}
                {selectedIndices.length > 0 && (
                  <Transformer
                    ref={transformerRef}
                    rotateEnabled={false}
                    keepRatio={false}
                    borderStrokeWidth={1 / scale}
                    anchorSize={8 / scale}
                    listening={!isSpacePressed && interactionMode === 'select'}
                    onDragStart={(e) => { e.cancelBubble = true; }}
                    onDragMove={(e) => { e.cancelBubble = true; }}
                    onDragEnd={(e) => { e.cancelBubble = true; }}
                    onTransformStart={(e) => { e.cancelBubble = true; }}
                    onTransform={(e) => { e.cancelBubble = true; }}
                    onTransformEnd={(e) => { e.cancelBubble = true; }}
                    boundBoxFunc={(oldBox, newBox) => {
                      if (newBox.width < 2 || newBox.height < 2) return oldBox;
                      return newBox;
                    }}
                  />
                )}
              </Layer>
            </Stage>
          ) : (
            <div className="text-gray-500">Select an image to start</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
