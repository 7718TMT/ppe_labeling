import cv2
import os
import glob

# --- CONFIGURATION ---
IMAGE_FOLDER = "./images"      # Folder containing original images
LABEL_FOLDER = "./labels"      # Folder containing the generated .txt files
VERIFY_FOLDER = "./labeled_images"                # Folder where annotated copies will be saved
IMAGE_EXTENSIONS = ["*.jpg", "*.jpeg", "*.png"]

# Create verification directory if it doesn't exist
os.makedirs(VERIFY_FOLDER, exist_ok=True)

# Find all images
image_paths = []
for ext in IMAGE_EXTENSIONS:
    image_paths.extend(glob.glob(os.path.join(IMAGE_FOLDER, ext)))

print(f"Verifying labels for {len(image_paths)} images...")

for img_path in image_paths:
    # 1. Determine corresponding label file path
    base_name = os.path.splitext(os.path.basename(img_path))[0]
    label_path = os.path.join(LABEL_FOLDER, f"{base_name}.txt")
    
    # Skip if no corresponding label file exists
    if not os.path.exists(label_path):
        print(f"No label file found for: {os.path.basename(img_path)}. Skipping.")
        continue
        
    # 2. Read the image
    img = cv2.imread(img_path)
    if img is None:
        continue
    
    height, width, _ = img.shape
    
    # 3. Read and parse the YOLO coordinates from the .txt file
    with open(label_path, "r") as f:
        lines = f.readlines()
        
    for line in lines:
        parts = line.strip().split()
        if len(parts) != 5:
            continue
            
        class_id = parts[0]
        x_center = float(parts[1])
        y_center = float(parts[2])
        w = float(parts[3])
        h = float(parts[4])
        
        # 4. Convert normalized YOLO coordinates back to pixel coordinates
        # Reverse formulas:
        # x_min = (x_center - w/2) * width
        # x_max = (x_center + w/2) * width
        x1 = int((x_center - w / 2) * width)
        y1 = int((y_center - h / 2) * height)
        x2 = int((x_center + w / 2) * width)
        y2 = int((y_center + h / 2) * height)
        
        # Guardrail: Clamp coordinates to ensure they stay within image boundaries
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width - 1, x2), min(height - 1, y2)
        
        # 5. Draw the bounding box
        # cv2.rectangle syntax: (image, top_left_point, bottom_right_point, color_bgr, thickness)
        class_color = [(255, 0, 0), (0, 0, 255), (0, 255, 0)]
        # Using Bright Green (0, 255, 0) for maximum contrast against the orange vest
        cv2.rectangle(img, (x1, y1), (x2, y2), class_color[int(class_id)], 3)
        
        # Optional: Draw the class label text right above the box
        cv2.putText(img, f"Class: {class_id}", (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, class_color[int(class_id)], 2)

    # 6. Save the marked image into the test_img folder
    output_path = os.path.join(VERIFY_FOLDER, f"verified_{base_name}.jpg")
    cv2.imwrite(output_path, img)

print(f"Done! Check the '{VERIFY_FOLDER}' folder to review your annotations.")