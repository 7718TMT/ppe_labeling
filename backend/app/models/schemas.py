from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    class_id: int = Field(ge=0, le=3)
    x_center: float = Field(ge=0, le=1)
    y_center: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class LabelPayload(BaseModel):
    boxes: list[BoundingBox]


class LabelResponse(BaseModel):
    filename: str
    boxes: list[BoundingBox]


class ImageItem(BaseModel):
    name: str
    has_label: bool
    image_url: str
    visualization_url: str | None = None


class OperationResponse(BaseModel):
    status: str = "success"
    message: str


class RenamePreviewItem(BaseModel):
    original_name: str
    suggested_name: str
    reason: str
    class_ids: list[int]
    label_count: int
    will_rename: bool


class RenamePreviewResponse(BaseModel):
    items: list[RenamePreviewItem]
    rename_count: int


class TaskInfo(BaseModel):
    id: str
    name: str
    class_names: dict[int, str]
    temporary_class_id: int | None = None
