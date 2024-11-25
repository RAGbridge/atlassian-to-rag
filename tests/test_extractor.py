# tests/test_extractor.py
from unittest.mock import Mock, patch

import pytest

from atlassian_to_rag.confluence import ConfluenceExtractor


@pytest.fixture
def mock_confluence():
    with patch("atlassian.Confluence") as mock:
        mock_instance = mock.return_value
        mock_instance.get_all_pages_from_space.return_value = [{"id": "123", "title": "Test Page", "body": {"storage": {"value": "test content"}}, "version": {"number": 1, "when": "2024-01-01"}}]
        mock_instance.get_page_by_id.return_value = {"id": "123", "title": "Test Page", "body": {"storage": {"value": "test content"}}, "version": {"number": 1, "when": "2024-01-01"}}
        yield mock_instance


def test_get_space_content(mock_confluence, mock_cache_manager):
    # Create and use extractor
    extractor = ConfluenceExtractor("http://test", "user", "token", cache_manager=mock_cache_manager)

    result = extractor.get_space_content("TEST")
    assert len(result) == 1
    assert result[0]["id"] == "123"
    assert result[0]["title"] == "Test Page"


def test_get_single_page(mock_confluence, mock_cache_manager):
    extractor = ConfluenceExtractor("http://test", "user", "token", cache_manager=mock_cache_manager)

    result = extractor.get_single_page("123")
    assert result["id"] == "123"
    assert result["title"] == "Test Page"
