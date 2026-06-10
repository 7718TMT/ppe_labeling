import cv2
import numpy as np

from backend.app.models.schemas import BoundingBox


LOWER_ORANGE = np.array([5, 120, 120])
UPPER_ORANGE = np.array([22, 255, 255])
LOWER_GREEN = np.array([25, 100, 120])
UPPER_GREEN = np.array([45, 255, 255])
MIN_VEST_PIXELS = 15


def detect_vests(
    image: np.ndarray,
    humans: list[BoundingBox],
    helmets: list[BoundingBox],
) -> list[BoundingBox]:
    height, width, _ = image.shape
    helmet_pixels = [_to_pixels(box, width, height) for box in helmets]
    vests: list[BoundingBox] = []

    for human in humans:
        hx_min, hy_min, hx_max, hy_max = _to_pixels(human, width, height)
        hx_min, hx_max = max(0, hx_min), min(width - 1, hx_max)
        hy_min, hy_max = max(0, hy_min), min(height - 1, hy_max)

        if hx_max <= hx_min or hy_max <= hy_min:
            continue

        roi = image[hy_min:hy_max, hx_min:hx_max].copy()
        for helmet_box in helmet_pixels:
            _mask_overlapping_helmet(roi, (hx_min, hy_min, hx_max, hy_max), helmet_box)

        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        roi_y, roi_x = _color_pixels(hsv_roi, LOWER_GREEN, UPPER_GREEN)
        if len(roi_x) < MIN_VEST_PIXELS or len(roi_y) < MIN_VEST_PIXELS:
            roi_y, roi_x = _color_pixels(hsv_roi, LOWER_ORANGE, UPPER_ORANGE)
        if len(roi_x) < MIN_VEST_PIXELS or len(roi_y) < MIN_VEST_PIXELS:
            continue

        vest_xmin = hx_min + int(np.min(roi_x))
        vest_xmax = hx_min + int(np.max(roi_x))
        vest_ymin = hy_min + int(np.min(roi_y))
        vest_ymax = hy_min + int(np.max(roi_y))

        vests.append(
            BoundingBox(
                class_id=2,
                x_center=((vest_xmin + vest_xmax) / 2.0) / width,
                y_center=((vest_ymin + vest_ymax) / 2.0) / height,
                w=max(0.000001, (vest_xmax - vest_xmin) / width),
                h=max(0.000001, (vest_ymax - vest_ymin) / height),
            )
        )

    return vests


def _color_pixels(hsv_roi: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = cv2.inRange(hsv_roi, lower, upper)
    return np.where(mask == 255)


def _to_pixels(box: BoundingBox, width: int, height: int) -> tuple[int, int, int, int]:
    x_min = int((box.x_center - box.w / 2.0) * width)
    x_max = int((box.x_center + box.w / 2.0) * width)
    y_min = int((box.y_center - box.h / 2.0) * height)
    y_max = int((box.y_center + box.h / 2.0) * height)
    return x_min, y_min, x_max, y_max


def _mask_overlapping_helmet(
    roi: np.ndarray,
    human_box: tuple[int, int, int, int],
    helmet_box: tuple[int, int, int, int],
) -> None:
    hx_min, hy_min, hx_max, hy_max = human_box
    helmet_xmin, helmet_ymin, helmet_xmax, helmet_ymax = helmet_box
    if helmet_xmax < hx_min or helmet_xmin > hx_max or helmet_ymax < hy_min or helmet_ymin > hy_max:
        return

    rel_xmin = max(0, helmet_xmin - hx_min)
    rel_xmax = min(hx_max - hx_min, helmet_xmax - hx_min)
    rel_ymin = max(0, helmet_ymin - hy_min)
    rel_ymax = min(hy_max - hy_min, helmet_ymax - hy_min)
    roi[rel_ymin:rel_ymax, rel_xmin:rel_xmax] = [0, 0, 0]
