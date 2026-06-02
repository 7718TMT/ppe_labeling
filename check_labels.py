import os
from pathlib import Path

# --- CONFIGURATION ---
LABEL_FOLDER = Path("./labels")

def check_label_boundaries():
    if not LABEL_FOLDER.exists():
        print(f"Error: Label folder '{LABEL_FOLDER}' not found.")
        return

    label_files = list(LABEL_FOLDER.glob("*.txt"))
    print(f"Auditing {len(label_files)} label files for boundary violations...\n")

    files_with_issues = 0
    total_issues = 0
    total_boxes = 0

    for label_path in label_files:
        issues_in_file = []
        
        with open(label_path, "r") as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            
            total_boxes += 1
            class_id = parts[0]
            x_center = float(parts[1])
            y_center = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])

            # Calculate edge coordinates
            x1 = x_center - w / 2
            y1 = y_center - h / 2
            x2 = x_center + w / 2
            y2 = y_center + h / 2

            # Check for violations
            violations = []
            if x1 < 0: violations.append(f"left ({x1:.6f})")
            if y1 < 0: violations.append(f"top ({y1:.6f})")
            if x2 > 1: violations.append(f"right ({x2:.6f})")
            if y2 > 1: violations.append(f"bottom ({y2:.6f})")

            if violations:
                issues_in_file.append({
                    "line": i + 1,
                    "class": class_id,
                    "violations": violations
                })

        if issues_in_file:
            files_with_issues += 1
            print(f"File: {label_path.name}")
            for issue in issues_in_file:
                total_issues += 1
                print(f"  - Line {issue['line']} (Class {issue['class']}): Exceeds " + ", ".join(issue['violations']))
            print("")

    print("--- Summary ---")
    print(f"Total boxes checked: {total_boxes}")
    print(f"Files with issues:   {files_with_issues}")
    print(f"Total violations:    {total_issues}")
    
    if total_issues == 0:
        print("\nResult: All labels are perfectly within boundaries. ✅")
    else:
        print(f"\nResult: Found {total_issues} out-of-bounds violations in {files_with_issues} files. ❌")
        print("You can use 'fix_boundaries.py' to automatically correct these.")

if __name__ == "__main__":
    check_label_boundaries()
