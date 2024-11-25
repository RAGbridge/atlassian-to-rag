import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_cache_manager():
    mock = Mock()
    mock.get.return_value = None
    mock.cache_key.return_value = "test_key"
    return mock
