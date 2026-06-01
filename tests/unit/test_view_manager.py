"""
Tests for ViewManager (Task Card 012)
"""
import pytest
import json
import os
import tempfile
from unittest.mock import Mock, MagicMock
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.view_manager import ViewManager


class TestViewManager:
    """Test suite for ViewManager"""
    
    @pytest.fixture
    def setup_view_manager(self):
        """Create a temporary directory and ViewManager instance"""
        with tempfile.TemporaryDirectory() as tmpdir:
            vm = ViewManager(config_dir=tmpdir)
            yield vm, tmpdir
    
    def test_initialization(self, setup_view_manager):
        """Test ViewManager initializes correctly"""
        vm, tmpdir = setup_view_manager
        assert vm.config_dir == tmpdir
        # views.json 在第一次 save_view 时才创建，初始化时不要求文件存在
    
    def test_save_view(self, setup_view_manager):
        """Test saving a view"""
        vm, tmpdir = setup_view_manager
        
        # Mock app state
        app_state = {
            'sort': {'column': '偏差率(%)', 'reverse': False},
            'columns': [
                {'column': '工厂', 'width': 80, 'hidden': False},
                {'column': '物料号', 'width': 100, 'hidden': False}
            ],
            'filters': {'工厂': ['工厂A']}
        }
        
        result = vm.save_view('test_view', app_state)
        
        assert result is True
        assert 'test_view' in vm.list_views()
        
        # Verify file was written
        views_file = os.path.join(tmpdir, 'views.json')
        with open(views_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'test_view' in data
    
    def test_load_view(self, setup_view_manager):
        """Test loading a saved view"""
        vm, tmpdir = setup_view_manager
        
        # Save a view first
        app_state = {
            'sort': {'column': '偏差率(%)', 'reverse': False},
            'columns': [{'column': '工厂', 'width': 80, 'hidden': False}],
            'filters': {}
        }
        vm.save_view('load_test', app_state)
        
        # Load it back
        loaded = vm.load_view('load_test')
        
        assert loaded is not None
        assert loaded['sort']['column'] == '偏差率(%)'
        assert len(loaded['columns']) == 1
    
    def test_delete_view(self, setup_view_manager):
        """Test deleting a view"""
        vm, tmpdir = setup_view_manager
        
        # Save a view
        app_state = {'sort': {}, 'columns': [], 'filters': {}}
        vm.save_view('to_delete', app_state)
        assert 'to_delete' in vm.list_views()
        
        # Delete it
        result = vm.delete_view('to_delete')
        assert result is True
        assert 'to_delete' not in vm.list_views()
    
    def test_list_views_empty(self, setup_view_manager):
        """Test listing views when none exist"""
        vm, tmpdir = setup_view_manager
        assert vm.list_views() == []
    
    def test_list_views_multiple(self, setup_view_manager):
        """Test listing multiple views"""
        vm, tmpdir = setup_view_manager
        
        app_state = {'sort': {}, 'columns': [], 'filters': {}}
        vm.save_view('view1', app_state)
        vm.save_view('view2', app_state)
        vm.save_view('view3', app_state)
        
        views = vm.list_views()
        assert len(views) == 3
        assert 'view1' in views
    
    def test_overwrite_view(self, setup_view_manager):
        """Test overwriting an existing view"""
        vm, tmpdir = setup_view_manager
        
        app_state1 = {'sort': {'column': 'A'}, 'columns': [], 'filters': {}}
        app_state2 = {'sort': {'column': 'B'}, 'columns': [], 'filters': {}}
        
        vm.save_view('overwrite_test', app_state1)
        vm.save_view('overwrite_test', app_state2)  # Overwrite
        
        loaded = vm.load_view('overwrite_test')
        assert loaded['sort']['column'] == 'B'  # Should be the new value
    
    def test_load_nonexistent_view(self, setup_view_manager):
        """Test loading a view that doesn't exist"""
        vm, tmpdir = setup_view_manager
        
        result = vm.load_view('nonexistent')
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
