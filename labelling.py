import cv2
import numpy as np
import os
from pathlib import Path
from ultralytics import YOLO

import argparse

# --- CONFIGURATION ---
INPUT_FOLDER = Path("./images")
OUTPUT_FOLDER = Path("./labels")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# 1. Load the YOLOv8 model
model = YOLO("best.pt")

# ... (color range definitions) ...

# 2. COLOR RANGE DEFINITIONS (HSV)
LOWER_ORANGE = np.array([5, 120, 120])   
UPPER_ORANGE = np.array([22, 255, 255])  

LOWER_GREEN = np.array([25, 100, 120])   
UPPER_GREEN = np.array([45, 255, 255])  

# Minimum number of pixels required to count a color blob as a valid vest
MIN_VEST_PIXELS = 15

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--image", type=str, help="Specific image filename to process")
args = parser.parse_args()

# Gather all image files
image_extensions = ("*.png", "*.jpg", "*.jpeg", "*.JPG", "*.PNG")
image_paths = []

if args.image:
    target_path = INPUT_FOLDER / args.image
    if target_path.exists():
        image_paths = [target_path]
    else:
        print(f"Error: Specified image {args.image} not found.")
        exit(1)
else:
    for ext in image_extensions:
        image_paths.extend(INPUT_FOLDER.glob(ext))

print(f"Starting pipeline. Processing {len(image_paths)} images with helmet masking...")

for img_path in image_paths:
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"Skipping unreadable image: {img_path.name}")
        continue
    
    height, width, _ = img.shape
    
    # Run human and helmet detection
    results = model(img_path, verbose=False)
    
    final_labels = []
    helmets_pixel_boxes = [] # To temporarily store helmet pixel locations for masking
    humans_data = []         # To temporarily store human locations to process after helmets
    
    for result in results:
        boxes = result.boxes
        xywhn_list = boxes.xywhn.tolist()
        cls_list = boxes.cls.tolist()
        
        for i, cls_id in enumerate(cls_list):
            # --- HELMET PROCESSING (Class 1) ---
            if int(cls_id) == 1:
                hx_center, hy_center, hw, hh = xywhn_list[i]
                
                # Keep the original output formatting unchanged (Class 1)
                helmet_line = f"1 {hx_center:.6f} {hy_center:.6f} {hw:.6f} {hh:.6f}"
                final_labels.append(helmet_line)
                
                # Convert helmet to absolute pixel boundaries for masking later
                helm_xmin = int((hx_center - hw / 2.0) * width)
                helm_xmax = int((hx_center + hw / 2.0) * width)
                helm_ymin = int((hy_center - hh / 2.0) * height)
                helm_ymax = int((hy_center + hh / 2.0) * height)
                helmets_pixel_boxes.append((helm_xmin, helm_ymin, helm_xmax, helm_ymax))
                
            # --- HUMAN PROCESSING (Class 0) ---
            elif int(cls_id) == 0:
                # Store human details to handle in a separate pass once all helmets are collected
                humans_data.append(xywhn_list[i])

    # --- PROCESSING VESTS INSIDE HUMAN BOXES ---
    for human_box in humans_data:
        hx_center, hy_center, hw, hh = human_box
        
        # Add Human label (Class 0) to final labels
        human_line = f"0 {hx_center:.6f} {hy_center:.6f} {hw:.6f} {hh:.6f}"
        final_labels.append(human_line)
        
        # Convert human boundaries to pixel values
        hx_min = int((hx_center - hw / 2.0) * width)
        hx_max = int((hx_center + hw / 2.0) * width)
        hy_min = int((hy_center - hh / 2.0) * height)
        hy_max = int((hy_center + hh / 2.0) * height)
        
        hx_min, hx_max = max(0, hx_min), min(width - 1, hx_max)
        hy_min, hy_max = max(0, hy_min), min(height - 1, hy_max)
        
        if hx_max <= hx_min or hy_max <= hy_min:
            continue
        
        # Crop human region (ROI)
        roi = img[hy_min:hy_max, hx_min:hx_max].copy() # Using .copy() avoids corrupting the main image array
        
        # --- NEW HELMET MASKING STEP ---
        # Look for any helmets that fall within this human's box and black them out
        for (helm_xmin, helm_ymin, helm_xmax, helm_ymax) in helmets_pixel_boxes:
            # Check if the helmet box overlaps with this human box
            if not (helm_xmax < hx_min or helm_xmin > hx_max or helm_ymax < hy_min or helm_ymin > hy_max):
                # Calculate the relative position of the helmet inside this specific cropped ROI
                rel_xmin = max(0, helm_xmin - hx_min)
                rel_xmax = min(hx_max - hx_min, helm_xmax - hx_min)
                rel_ymin = max(0, helm_ymin - hy_min)
                rel_ymax = min(hy_max - hy_min, helm_ymax - hy_min)
                
                # Paint the helmet region solid black so color filters ignore it
                roi[rel_ymin:rel_ymax, rel_xmin:rel_xmax] = [0, 0, 0]
        
        # Convert the masked ROI to HSV
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        # FIRST TRY GREEN VEST DETECTION
        green_mask = cv2.inRange(hsv_roi, LOWER_GREEN, UPPER_GREEN)
        roi_y, roi_x = np.where(green_mask == 255)
        
        # IF NO GREEN, FALLBACK TO ORANGE VEST DETECTION
        if len(roi_x) < MIN_VEST_PIXELS or len(roi_y) < MIN_VEST_PIXELS:
            orange_mask = cv2.inRange(hsv_roi, LOWER_ORANGE, UPPER_ORANGE)
            roi_y, roi_x = np.where(orange_mask == 255)
        
        # If neither color is found, skip vest generation
        if len(roi_x) < MIN_VEST_PIXELS or len(roi_y) < MIN_VEST_PIXELS:
            continue
        
        # Find local bounds of the discovered vest
        roi_xmin, roi_xmax = np.min(roi_x), np.max(roi_x)
        roi_ymin, roi_ymax = np.min(roi_y), np.max(roi_y)
        
        # Map local coordinates back to full image coordinate space
        vest_xmin = hx_min + roi_xmin
        vest_xmax = hx_min + roi_xmax
        vest_ymin = hy_min + roi_ymin
        vest_ymax = hy_min + roi_ymax
        
        # Re-normalize for YOLO format
        vx_center = ((vest_xmin + vest_xmax) / 2.0) / width
        vy_center = ((vest_ymin + vest_ymax) / 2.0) / height
        vw = (vest_xmax - vest_xmin) / width
        vh = (vest_ymax - vest_ymin) / height
        
        # Add Vest label (Class 2)
        vest_line = f"2 {vx_center:.6f} {vy_center:.6f} {vw:.6f} {vh:.6f}"
        final_labels.append(vest_line)

    # --- STEP 8: WRITE ALL LABELS TO A SINGLE TXT FILE ---
    if final_labels:
        txt_path = OUTPUT_FOLDER / f"{img_path.stem}.txt"
        with open(txt_path, "w") as f:
            f.write("\n".join(final_labels) + "\n")
        print(f"-> Exported labels for: {img_path.name}")

print(f"\nFinished! Dual-color annotations with helmet masking saved to: {OUTPUT_FOLDER}")