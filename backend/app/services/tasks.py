from backend.app.core.config import Settings
from backend.app.domain.models import TaskDefinition


class TaskService:
    """Application access to configured annotation task definitions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_tasks(self) -> list[TaskDefinition]:
        return [
            TaskDefinition(
                id=profile.id,
                name=profile.name,
                class_names=profile.class_names,
                temporary_class_id=profile.temporary_class_id,
            )
            for profile in self.settings.task_profiles.values()
        ]
