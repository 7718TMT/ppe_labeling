from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
import subprocess
from pathlib import Path

app = FastAPI()

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGE_FOLDER = Path("./images")
LABEL_FOLDER = Path("./labels")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".JPG", ".PNG"}

# Ensure folders exist
IMAGE_FOLDER.mkdir(exist_ok=True)
LABEL_FOLDER.mkdir(exist_ok=True)

# Mount images for static serving
app.mount("/images", StaticFiles(directory="images"), name="images")

class BBox(BaseModel):
    class_id: int
    x_center: float
    y_center: float
    w: float
    h: float

class LabelData(BaseModel):
    filename: str
    boxes: List[BBox]

@app.post("/api/process")
async def process_images():
    try:
        # Run labelling.py
        process1 = subprocess.run(["python", "labelling.py"], capture_output=True, text=True)
        if process1.returncode != 0:
            raise HTTPException(status_code=500, detail=f"labelling.py failed: {process1.stderr}")
        
        # Run visualize_label.py
        process2 = subprocess.run(["python", "visualize_label.py"], capture_output=True, text=True)
        if process2.returncode != 0:
            raise HTTPException(status_code=500, detail=f"visualize_label.py failed: {process2.stderr}")
        
        return {"status": "success", "message": "Processing completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/images")
async def get_images():
    images = [f.name for f in IMAGE_FOLDER.iterdir() if f.suffix in IMAGE_EXTENSIONS]
    return images

@app.get("/api/labels/{filename}")
async def get_labels(filename: str):
    label_filename = Path(filename).with_suffix(".txt")
    label_path = LABEL_FOLDER / label_filename
    
    if not label_path.exists():
        return {"filename": filename, "boxes": []}
    
    boxes = []
    try:
        with open(label_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    boxes.append(BBox(
                        class_id=int(parts[0]),
                        x_center=float(parts[1]),
                        y_center=float(parts[2]),
                        w=float(parts[3]),
                        h=float(parts[4])
                    ))
        return {"filename": filename, "boxes": boxes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading labels: {str(e)}")

@app.put("/api/labels/{filename}")
async def update_labels(filename: str, label_data: LabelData):
    label_filename = Path(filename).with_suffix(".txt")
    label_path = LABEL_FOLDER / label_filename
    
    try:
        with open(label_path, "w") as f:
            for box in label_data.boxes:
                line = f"{box.class_id} {box.x_center:.6f} {box.y_center:.6f} {box.w:.6f} {box.h:.6f}\n"
                f.write(line)
        
        # Optional: update visualization for this image
        # For simplicity, we can just return success and let the user re-run process if they want full visualization update,
        # or we could trigger a partial visualization. Let's keep it simple for now.
        
        return {"status": "success", "message": f"Labels updated for {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing labels: {str(e)}")

@app.post("/api/reset")
async def reset_image(filename: str):
    try:
        # We need to run labelling.py but only for this image.
        process = subprocess.run(["python", "labelling.py", "--image", filename], capture_output=True, text=True)
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"labelling.py reset failed: {process.stderr}")
            
        return {"status": "success", "message": f"Reset completed for {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
