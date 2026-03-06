from typing import Any


class ApiValidationError(Exception):
    """Validation errors with structured error dict"""

    def __init__(self, errors: dict[str, Any], status_code: int = 400):
        super().__init__("Validation error")
        self.errors = errors
        self.status_code = status_code


class BadRequestError(Exception):
    """Generic bad request error"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(Exception):
    def __init__(self, message: str = "Not found."):
        super().__init__(message)
        self.message = message
        self.status_code = 404
