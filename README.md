# PPE Auto-Labeling with Interactive UI

This project is an automated and interactive labeling tool for object detection datasets, specifically focusing on Personal Protective Equipment (PPE). It detects three classes:
- **0: Human**
- **1: Helmet**
- **2: Vest**

The system combines automated deep learning detection (YOLOv8) with a hard-coded color thresholding method for vest detection, all managed through a modern, responsive web interface.

## Features
- **Automated Labeling**: One-click processing to detect humans, helmets, and vests using a hybrid AI/Color-logic approach.
- **Interactive Editor**: 
  - View labels overlaid on original images.
  - **Multi-Selection**: Use `Shift + Click` to toggle selections or **Marquee Select** (drag mouse) to select groups of boxes.
  - **Edit & Adjust**: Drag to move or resize bounding boxes with sub-pixel precision.
  - **Keyboard Shortcuts**: 
    - `Delete` / `Backspace`: Remove selected boxes.
    - `Ctrl + Z`: Undo any change (moving, resizing, deleting, etc.).
  - **Zoom & Pan**: Smooth mouse-wheel zoom for detailed labeling on high-resolution images.
- **Real-time Sync**: Manual adjustments in the UI are saved directly back to YOLO-formatted `.txt` files.

## Project Structure
- `app.py`: FastAPI backend that manages files and triggers labeling scripts.
- `labelling.py`: Core logic for AI detection and vest color thresholding.
- `visualize_label.py`: Utility to generate static images with drawn-on boxes.
- `ui/`: React frontend source code.
- `images/`: Put your raw images here.
- `labels/`: Output folder for YOLO `.txt` annotations.
- `labeled_images/`: Output folder for static visualization images.

## How to Use

### 1. Installation
Ensure you have Python 3.8+ and Node.js installed.
```bash
# Install Python dependencies
pip install fastapi uvicorn python-multipart ultralytics opencv-python numpy

# Install Frontend dependencies
cd ui
npm install
cd ..
```

### 2. Prepare Data
Put your images (JPG, PNG) into the `images/` folder.

### 3. Run the Application
You need to run two separate servers:

**Terminal 1: Backend**
```bash
python app.py
```

**Terminal 2: Frontend**
```bash
cd ui
npm run dev
```

### 4. Labeling Workflow
1. Open your browser to `http://localhost:5173`.
2. Click **"Process All"** to run the automatic labeling pipeline.
3. Select an image from the sidebar to review.
4. Use the mouse wheel to zoom.
5. Adjust boxes as needed:
   - Click to select.
   - Drag to move.
   - Use handles to resize.
   - `Shift + Click` or Drag-select for multiple boxes.
6. Click **"Save Changes"** to update the label files.

## Logic Overview
- **AI Detection**: Uses `best.pt` (YOLOv8) to identify Humans and Helmets.
- **Vest Logic**: Crops the human ROI, masks out helmet areas to avoid color interference, and applies HSV thresholding for Green and Orange. If sufficient pixels match, a Vest label is generated.
