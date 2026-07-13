class ApplicationError(Exception):
    """Base error for expected application failures."""


class UnknownTaskError(ApplicationError):
    pass


class InvalidFilenameError(ApplicationError):
    pass


class UnsupportedImageTypeError(ApplicationError):
    pass


class ImageNotFoundError(ApplicationError):
    pass


class InvalidLabelError(ApplicationError):
    pass


class InvalidClassError(ApplicationError):
    pass


class UnreadableImageError(ApplicationError):
    pass


class ModelUnavailableError(ApplicationError):
    pass


class VideoResourceNotFoundError(ApplicationError):
    """A requested video-labeling resource does not exist."""


class VideoValidationError(ApplicationError):
    """A video-labeling request violates a domain rule."""


class RevisionConflictError(ApplicationError):
    """An optimistic annotation write used a stale revision."""


class DuplicateVideoError(ApplicationError):
    """An imported video already exists in the project."""


class ModelCompatibilityError(ApplicationError):
    """An external inference package is not compatible with the project."""


class VideoProcessingConflictError(ApplicationError):
    """A video already has an incompatible active processing request."""


class DatasetCollisionError(ApplicationError):
    pass


class ApprovalPersistenceError(ApplicationError):
    pass


class FilesystemOperationError(ApplicationError):
    """A filesystem operation made partial progress and needs inspection."""

    def __init__(self, message: str, result: object) -> None:
        super().__init__(message)
        self.result = result


class PartialOperationError(ApplicationError):
    """An operation completed partially and needs reconciliation."""

    def __init__(self, message: str, result: object) -> None:
        super().__init__(message)
        self.result = result
