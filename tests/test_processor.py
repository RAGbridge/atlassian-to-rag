# tests/test_processor.py
from unittest.mock import Mock

import pytest

from atlassian_to_rag.processor import ConfluenceProcessor


def test_clean_html_content():
    metrics_mock = Mock()
    processor = ConfluenceProcessor(metrics=metrics_mock)
    html_content = "<p>Test content</p><div>More content</div>"
    result = processor._process_text({"content": html_content})
    assert result == "Test content More content"


def test_process_page():
    metrics_mock = Mock()
    processor = ConfluenceProcessor(metrics=metrics_mock)
    page = {"id": "123", "title": "Test", "content": "<p>Test content</p>", "url": "http://test", "version": "1", "last_modified": "2024-01-01"}
    result = processor.process_page(page)
    assert "content" in result
    assert "metadata" in result
    assert result["metadata"]["id"] == "123"
