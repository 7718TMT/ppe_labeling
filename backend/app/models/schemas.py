from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    class_id: int = Field(ge=0, le=2)
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
