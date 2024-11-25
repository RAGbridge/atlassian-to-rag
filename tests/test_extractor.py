# tests/test_extractor.py
import pytest
from unittest.mock import Mock, patch
from atlassian_to_rag.confluence import ConfluenceExtractor

def test_get_space_content(monkeypatch):
    # Create mock data
    mock_page_data = {
        'id': '123',
        'title': 'Test Page',
        'body': {'storage': {'value': 'test content'}},
        'version': {'number': 1, 'when': '2024-01-01'}
    }
    
    # Create mock Confluence instance
    mock_confluence = Mock()
    mock_confluence.get_all_pages_from_space.return_value = [mock_page_data]
    
    # Create mock cache manager
    mock_cache_manager = Mock()
    mock_cache_manager.get.return_value = None
    
    # Patch the Confluence class
    with patch('atlassian.Confluence', return_value=mock_confluence):
        extractor = ConfluenceExtractor(
            'http://test',
            'user',
            'token',
            cache_manager=mock_cache_manager
        )
        
        # Call the method
        result = extractor.get_space_content('TEST')
        
        # Verify the call
        mock_confluence.get_all_pages_from_space.assert_called_once_with(
            space='TEST',
            start=0,
            limit=100,
            expand='body.storage,version'
        )
        
        # Check results
        assert len(result) == 1
        assert result[0]['id'] == '123'
        assert result[0]['title'] == 'Test Page'
        assert 'content' in result[0]

def test_get_single_page(monkeypatch):
    # Create mock data
    mock_page_data = {
        'id': '123',
        'title': 'Test Page',
        'body': {'storage': {'value': 'test content'}},
        'version': {'number': 1, 'when': '2024-01-01'}
    }
    
    # Create mock Confluence instance
    mock_confluence = Mock()
    mock_confluence.get_page_by_id.return_value = mock_page_data
    
    # Create mock cache manager
    mock_cache_manager = Mock()
    mock_cache_manager.get.return_value = None
    
    # Patch the Confluence class
    with patch('atlassian.Confluence', return_value=mock_confluence):
        extractor = ConfluenceExtractor(
            'http://test',
            'user',
            'token',
            cache_manager=mock_cache_manager
        )
        
        # Call the method
        result = extractor.get_single_page('123')
        
        # Verify the call
        mock_confluence.get_page_by_id.assert_called_once_with(
            page_id='123',
            expand='body.storage,version'
        )
        
        # Check results
        assert result['id'] == '123'
        assert result['title'] == 'Test Page'
        assert 'content' in result
