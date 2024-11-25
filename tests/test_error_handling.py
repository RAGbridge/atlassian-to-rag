import pytest

from atlassian_to_rag.core.error_handling import BaseError, ErrorResponse, handle_errors


def test_base_error():
    error = BaseError("Test error", status_code=400, details={"test": "detail"})
    assert error.message == "Test error"
    assert error.status_code == 400
    assert error.details == {"test": "detail"}


@handle_errors
def function_that_raises():
    raise BaseError("Test error")


def test_error_handling():
    result = function_that_raises()
    assert isinstance(result, ErrorResponse)
    assert result.message == "Test error"
