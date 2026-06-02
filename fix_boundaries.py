import os
from pathlib import Path

# --- CONFIGURATION ---
LABEL_FOLDER = Path("./labels")
EPSILON = 1e-6  # Safety margin to prevent floating point "bleeding"

def fix_boundaries():
    if not LABEL_FOLDER.exists():
        print(f"Error: Label folder '{LABEL_FOLDER}' not found.")
        return

    label_files = list(LABEL_FOLDER.glob("*.txt"))
    print(f"Scanning {len(label_files)} label files with EPSILON={EPSILON}...")

    fixed_count = 0
    total_boxes = 0

    for label_path in label_files:
        with open(label_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        file_changed = False

        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            
            total_boxes += 1
            class_id = parts[0]
            x_center = float(parts[1])
            y_center = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])

            # 1. Calculate min/max normalized coordinates
            x1 = x_center - w / 2
            y1 = y_center - h / 2
            x2 = x_center + w / 2
            y2 = y_center + h / 2

            # 2. Check for ANY boundary violation
            if x1 < 0 or y1 < 0 or x2 > 1 or y2 > 1:
                # Clamp with safety margin
                x1_c = max(EPSILON, min(1.0 - EPSILON, x1))
                y1_c = max(EPSILON, min(1.0 - EPSILON, y1))
                x2_c = max(EPSILON, min(1.0 - EPSILON, x2))
                y2_c = max(EPSILON, min(1.0 - EPSILON, y2))

                # Ensure x2 is actually greater than x1 after clamping
                if x2_c <= x1_c: x2_c = x1_c + EPSILON
                if y2_c <= y1_c: y2_c = y1_c + EPSILON

                # 3. Recalculate center and dimensions
                new_w = x2_c - x1_c
                new_h = y2_c - y1_c
                new_xc = x1_c + new_w / 2
                new_yc = y1_c + new_h / 2

                # 4. FINAL SAFETY CLAMP: Ensure the center + half-width doesn't bleed over 1.0
                # because of the addition in (x1_c + new_w / 2)
                if (new_xc + new_w / 2) > 1.0: new_xc -= (new_xc + new_w / 2 - 1.0)
                if (new_xc - new_w / 2) < 0.0: new_xc += (0.0 - (new_xc - new_w / 2))
                if (new_yc + new_h / 2) > 1.0: new_yc -= (new_yc + new_h / 2 - 1.0)
                if (new_yc - new_h / 2) < 0.0: new_yc += (0.0 - (new_yc - new_h / 2))

                new_line = f"{class_id} {new_xc:.6f} {new_yc:.6f} {new_w:.6f} {new_h:.6f}\n"
                new_lines.append(new_line)
                file_changed = True
                fixed_count += 1
            else:
                new_lines.append(line if line.endswith('\n') else line + '\n')

        if file_changed:
            with open(label_path, "w") as f:
                f.writelines(new_lines)
            # print(f"  Fixed boxes in: {label_path.name}")

    print("\nProcessing Complete!")
    print(f"Total boxes checked: {total_boxes}")
    print(f"Total boxes adjusted: {fixed_count}")
    if fixed_count > 0:
        print("All labels are now strictly within [0, 1] boundaries.")
    else:
        print("No boundary issues found.")

if __name__ == "__main__":
    fix_boundaries()
