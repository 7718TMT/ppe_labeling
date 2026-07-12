from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.domain.errors import UnknownTaskError


TaskId = Literal["ppe", "safety_signs"]


def parse_class_names(raw_value: str) -> dict[int, str]:
    class_names: dict[int, str] = {}
    for item in raw_value.split("|"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid class mapping '{item}'. Use ID=Name entries separated by '|'.")
        class_id_text, class_name = item.split("=", 1)
        class_id = int(class_id_text.strip())
        if class_id < 0:
            raise ValueError("Class IDs must be non-negative integers.")
        class_name = class_name.strip()
        if not class_name:
            raise ValueError(f"Class {class_id} must have a non-empty name.")
        class_names[class_id] = class_name
    if not class_names:
        raise ValueError("At least one class mapping is required.")
    return dict(sorted(class_names.items()))


class TaskProfile(BaseModel):
    id: TaskId
    name: str
    image_dir: Path
    label_dir: Path
    visualization_dir: Path
    model_path: Path
    yolo_img_size: int
    yolo_conf: float
    yolo_iou: float
    class_names: dict[int, str]
    detector_type: Literal["ppe", "safety_signs"]
    inference_device: str = "auto"
    temporary_class_id: int | None = None
    use_color_vest_fallback: bool = False
    agnostic_nms: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    cors_origins: str = "http://localhost:5173"
    inference_device: str = "auto"
    database_path: Path = Path("data/labeling_db.sqlite3")

    ppe_model_path: Path = Path("weights/ppe.pt")
    ppe_image_dir: Path = Path("data/ppe/images")
    ppe_label_dir: Path = Path("data/ppe/labels")
    ppe_visualization_dir: Path = Path("data/ppe/labeled_images")
    ppe_yolo_img_size: int = 640
    ppe_yolo_conf: float = 0.25
    ppe_yolo_iou: float = 0.7
    ppe_class_names: str = "0=Person|1=Helmet|2=Vest|3=Cleaning Coverall"
    ppe_use_color_vest_fallback: bool = False

    safety_sign_model_path: Path = Path("weights/sign.pt")
    safety_sign_image_dir: Path = Path("data/safety_signs/images")
    safety_sign_label_dir: Path = Path("data/safety_signs/labels")
    safety_sign_visualization_dir: Path = Path("data/safety_signs/labeled_images")
    safety_sign_conf: float = 0.15
    safety_sign_img_size: int = 640
    safety_sign_iou: float = 0.7
    safety_sign_class_names: str = (
        "0=M014 Wear head protection|"
        "1=M015 Wear high-visibility clothing|"
        "2=P004 No thoroughfare|"
        "3=W011 Slippery surface"
    )
    safety_sign_agnostic_nms: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def task_profiles(self) -> dict[TaskId, TaskProfile]:
        return {
            "ppe": TaskProfile(
                id="ppe",
                name="PPE",
                image_dir=self.ppe_image_dir,
                label_dir=self.ppe_label_dir,
                visualization_dir=self.ppe_visualization_dir,
                model_path=self.ppe_model_path,
                yolo_img_size=self.ppe_yolo_img_size,
                yolo_conf=self.ppe_yolo_conf,
                yolo_iou=self.ppe_yolo_iou,
                class_names=parse_class_names(self.ppe_class_names),
                detector_type="ppe",
                inference_device=self.inference_device,
                use_color_vest_fallback=self.ppe_use_color_vest_fallback,
            ),
            "safety_signs": TaskProfile(
                id="safety_signs",
                name="Safety Signs",
                image_dir=self.safety_sign_image_dir,
                label_dir=self.safety_sign_label_dir,
                visualization_dir=self.safety_sign_visualization_dir,
                model_path=self.safety_sign_model_path,
                yolo_img_size=self.safety_sign_img_size,
                yolo_conf=self.safety_sign_conf,
                yolo_iou=self.safety_sign_iou,
                class_names=parse_class_names(self.safety_sign_class_names),
                detector_type="safety_signs",
                inference_device=self.inference_device,
                agnostic_nms=self.safety_sign_agnostic_nms,
            ),
        }

    def task_profile(self, task: str) -> TaskProfile:
        profiles = self.task_profiles
        if task not in profiles:
            raise UnknownTaskError(f"Unknown task: {task}")
        return profiles[task]  # type: ignore[index]

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        for profile in self.task_profiles.values():
            profile.image_dir.mkdir(parents=True, exist_ok=True)
            profile.label_dir.mkdir(parents=True, exist_ok=True)
            profile.visualization_dir.mkdir(parents=True, exist_ok=True)
            profile.model_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
