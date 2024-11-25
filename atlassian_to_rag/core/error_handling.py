import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class ErrorResponse:
    message: str
    error_type: str
    status_code: int
    details: Optional[Dict[str, Any]] = None


class BaseError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class ConfigurationError(BaseError):
    pass


class RateLimitError(BaseError):
    pass


class ConfluenceAPIError(BaseError):
    pass


class ProcessingError(BaseError):
    pass


def handle_errors(func: Any) -> Any:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except BaseError as e:
            logger.error(
                "Application error",
                error_type=e.__class__.__name__,
                message=str(e),
                details=e.details,
                status_code=e.status_code,
                traceback=traceback.format_exc(),
            )
            return ErrorResponse(
                message=str(e),
                error_type=e.__class__.__name__,
                status_code=e.status_code,
                details=e.details,
            )
        except Exception as e:
            logger.error(
                "Unexpected error",
                error_type=e.__class__.__name__,
                message=str(e),
                traceback=traceback.format_exc(),
            )
            return ErrorResponse(
                message="An unexpected error occurred",
                error_type="UnexpectedError",
                status_code=500,
                details={"original_error": str(e)},
            )

    return wrapper
