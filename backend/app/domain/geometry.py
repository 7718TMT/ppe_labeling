from backend.app.domain.models import BoundingBox


def clamp_box(box: BoundingBox) -> BoundingBox:
    """Clamp a normalized bounding box to the unit image coordinate space."""
    x1 = max(0.0, box.x_center - box.w / 2)
    y1 = max(0.0, box.y_center - box.h / 2)
    x2 = min(1.0, box.x_center + box.w / 2)
    y2 = min(1.0, box.y_center + box.h / 2)

    width = max(0.000001, x2 - x1)
    height = max(0.000001, y2 - y1)
    return BoundingBox(
        class_id=box.class_id,
        x_center=round(x1 + width / 2, 6),
        y_center=round(y1 + height / 2, 6),
        w=round(width, 6),
        h=round(height, 6),
    )
