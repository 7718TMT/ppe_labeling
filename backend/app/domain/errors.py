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
