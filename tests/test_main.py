import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from atlassian_to_rag.main import app
import json

runner = CliRunner()

@pytest.fixture
def mock_application(mock_confluence):
    mock = MagicMock()
    mock.extractor.get_space_content.return_value = [{
        'id': '123',
        'title': 'Test Page',
        'content': 'test content',
        'version': {'number': 1, 'when': '2024-01-01'}
    }]
    mock.extractor.get_single_page.return_value = {
        'id': '123',
        'title': 'Test Page',
        'content': 'test content',
        'version': {'number': 1, 'when': '2024-01-01'}
    }
    mock.extractor.get_attachments.return_value = []
    mock.extractor.get_comments.return_value = []
    return mock

def test_extract_space(tmp_path, monkeypatch, mock_application, mock_session):
    monkeypatch.setenv('CONFLUENCE_URL', 'http://test')
    monkeypatch.setenv('CONFLUENCE_USERNAME', 'user')
    monkeypatch.setenv('CONFLUENCE_API_TOKEN', 'token')
    
    with patch('atlassian_to_rag.main.Application', return_value=mock_application):
        result = runner.invoke(
            app, 
            ['extract-space', 'TEST', '--output-dir', str(tmp_path)]
        )
        assert result.exit_code == 0
        mock_application.extractor.get_space_content.assert_called_once_with('TEST')

def test_extract_page(tmp_path, monkeypatch, mock_application, mock_session):
    monkeypatch.setenv('CONFLUENCE_URL', 'http://test')
    monkeypatch.setenv('CONFLUENCE_USERNAME', 'user')
    monkeypatch.setenv('CONFLUENCE_API_TOKEN', 'token')
    
    with patch('atlassian_to_rag.main.Application', return_value=mock_application):
        result = runner.invoke(
            app, 
            ['extract-page', '123', '--output-dir', str(tmp_path)]
        )
        assert result.exit_code == 0
        mock_application.extractor.get_single_page.assert_called_once_with('123')
