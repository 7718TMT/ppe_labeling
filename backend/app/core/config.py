from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


TaskId = Literal["ppe", "safety_signs"]


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
    temporary_class_id: int | None = None
    yolo_world_prompts: list[str] = []
    use_color_vest_fallback: bool = False
    agnostic_nms: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    active_task: TaskId = "safety_signs"
    cors_origins: str = "http://localhost:5173"

    ppe_model_path: Path = Path("weights/ppe.pt")
    ppe_image_dir: Path = Path("data/ppe/images")
    ppe_label_dir: Path = Path("data/ppe/labels")
    ppe_visualization_dir: Path = Path("data/ppe/labeled_images")
    ppe_yolo_img_size: int = 640
    ppe_yolo_conf: float = 0.25
    ppe_yolo_iou: float = 0.7
    ppe_use_color_vest_fallback: bool = False

    safety_sign_model_path: Path = Path("weights/sign.pt")
    safety_sign_image_dir: Path = Path("data/safety_signs/images")
    safety_sign_label_dir: Path = Path("data/safety_signs/labels")
    safety_sign_visualization_dir: Path = Path("data/safety_signs/labeled_images")
    safety_sign_conf: float = 0.15
    safety_sign_img_size: int = 640
    safety_sign_iou: float = 0.7
    safety_sign_agnostic_nms: bool = True
    safety_sign_prompts: str = (
        "safety sign|"
        "factory safety sign|"
        "warning sign|"
        "mandatory sign|"
        "prohibition sign|"
        "hazard sign|"
        "industrial safety sign"
    )

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
                class_names={0: "Person", 1: "Helmet", 2: "Vest"},
                detector_type="ppe",
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
                class_names={
                    0: "M014 Wear head protection",
                    1: "M015 Wear high-visibility clothing",
                    2: "P004 No thoroughfare",
                    3: "W011 Slippery surface",
                    4: "Unreviewed safety sign",
                },
                detector_type="safety_signs",
                temporary_class_id=4,
                yolo_world_prompts=[prompt.strip() for prompt in self.safety_sign_prompts.split("|") if prompt.strip()],
                agnostic_nms=self.safety_sign_agnostic_nms,
            ),
        }

    def task_profile(self, task: str) -> TaskProfile:
        profiles = self.task_profiles
        if task not in profiles:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"Unknown task: {task}")
        return profiles[task]  # type: ignore[index]

    def ensure_directories(self) -> None:
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
