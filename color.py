import cv2
import numpy as np

# Define the exact same range from the main script
LOWER_ORANGE = np.array([5, 120, 120])
UPPER_ORANGE = np.array([22, 255, 255])

# Create a 200x500 gradient block transitioning from lower to upper bounds
# We create a grid across Hue (X axis) and Saturation/Value (Y axis)
h_grid, s_grid = np.meshgrid(
    np.linspace(LOWER_ORANGE[0], UPPER_ORANGE[0], 500),
    np.linspace(LOWER_ORANGE[1], UPPER_ORANGE[1], 200)
)
v_grid = np.linspace(LOWER_ORANGE[2], UPPER_ORANGE[2], 200)[:, None] * np.ones((1, 500))

# Merge into a single 3-channel HSV image
hsv_gradient = cv2.merge([
    h_grid.astype(np.uint8), 
    s_grid.astype(np.uint8), 
    v_grid.astype(np.uint8)
])

# Convert to standard BGR color space so your computer can display it correctly
preview_img = cv2.cvtColor(hsv_gradient, cv2.COLOR_HSV2BGR)

# Save the preview color palette
cv2.imwrite("orange_range_preview.jpg", preview_img)
print("Saved color range preview as 'orange_range_preview.jpg'!")