from pydantic import BaseModel, Field

from backend.app.domain.models import BoundingBox as DomainBoundingBox
from backend.app.domain.models import ImageRecord, TaskDefinition


class BoundingBox(BaseModel):
    class_id: int = Field(ge=0)
    x_center: float = Field(ge=0, le=1)
    y_center: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    def to_domain(self) -> DomainBoundingBox:
        return DomainBoundingBox(**self.model_dump())

    @classmethod
    def from_domain(cls, box: DomainBoundingBox) -> "BoundingBox":
        return cls(**box.__dict__)


class LabelPayload(BaseModel):
    boxes: list[BoundingBox]


class LabelResponse(BaseModel):
    filename: str
    boxes: list[BoundingBox]


class ImageItem(BaseModel):
    name: str
    has_label: bool
    is_approved: bool = False
    image_url: str
    visualization_url: str | None = None

    @classmethod
    def from_domain(cls, image: ImageRecord) -> "ImageItem":
        return cls(**image.__dict__)


class OperationResponse(BaseModel):
    status: str = "success"
    message: str


class TaskInfo(BaseModel):
    id: str
    name: str
    class_names: dict[int, str]
    temporary_class_id: int | None = None

    @classmethod
    def from_domain(cls, task: TaskDefinition) -> "TaskInfo":
        return cls(**task.__dict__)


class ApprovePayload(BaseModel):
    is_approved: bool
