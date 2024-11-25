from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_confluence():
    with patch("atlassian.Confluence") as mock:
        instance = mock.return_value
        instance.get_all_pages_from_space.return_value = [{"id": "123", "title": "Test Page", "body": {"storage": {"value": "test content"}}, "version": {"number": 1, "when": "2024-01-01"}}]
        instance.get_page_by_id.return_value = {"id": "123", "title": "Test Page", "body": {"storage": {"value": "test content"}}, "version": {"number": 1, "when": "2024-01-01"}}
        yield instance


@pytest.fixture
def mock_cache_manager():
    cache_manager = Mock()
    cache_manager.get.return_value = None
    cache_manager.cache_key.return_value = "test_key"
    return cache_manager


@pytest.fixture
def mock_metrics():
    return Mock()


@pytest.fixture
def mock_rate_limiter():
    return Mock()
