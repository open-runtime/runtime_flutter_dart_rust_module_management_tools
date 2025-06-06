"""
Unit tests for plugin system.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any

from tooling.core.plugin_system import (
    PluginMetadata, PluginHook, Plugin, CommandPlugin,
    PluginManager, load_plugins, trigger_hook, hook
)


class TestPluginMetadata:
    """Test plugin metadata dataclass"""
    
    def test_creation(self):
        """Test metadata creation"""
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            dependencies=["rich", "click"]
        )
        
        assert metadata.name == "test_plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.author == "Test Author"
        assert metadata.dependencies == ["rich", "click"]
    
    def test_optional_fields(self):
        """Test optional fields default to None"""
        metadata = PluginMetadata(
            name="test",
            version="1.0",
            description="Test"
        )
        
        assert metadata.author is None
        assert metadata.dependencies is None
        assert metadata.config_schema is None


class TestPluginHook:
    """Test plugin hook system"""
    
    def teardown_method(self):
        """Clear hooks after each test"""
        PluginHook.hooks.clear()
    
    def test_decorator(self):
        """Test hook decorator registration"""
        @hook('test_hook')
        def my_function(x):
            return x * 2
        
        assert 'test_hook' in PluginHook.hooks
        assert my_function in PluginHook.hooks['test_hook']
    
    def test_multiple_hooks(self):
        """Test multiple functions on same hook"""
        @hook('multi_hook')
        def func1():
            return 1
        
        @hook('multi_hook')
        def func2():
            return 2
        
        assert len(PluginHook.hooks['multi_hook']) == 2
    
    def test_trigger_hook(self):
        """Test triggering hooks"""
        results = []
        
        @hook('trigger_test')
        def handler1(value):
            results.append(f"handler1: {value}")
            return 1
        
        @hook('trigger_test')
        def handler2(value):
            results.append(f"handler2: {value}")
            return 2
        
        # Trigger hook
        hook_results = PluginHook.trigger('trigger_test', 'test')
        
        assert results == ["handler1: test", "handler2: test"]
        assert hook_results == [1, 2]
    
    def test_trigger_nonexistent_hook(self):
        """Test triggering non-existent hook"""
        results = PluginHook.trigger('nonexistent')
        assert results == []
    
    def test_hook_exception_handling(self):
        """Test exception handling in hooks"""
        @hook('error_hook')
        def error_handler():
            raise ValueError("Test error")
        
        @hook('error_hook')
        def good_handler():
            return "success"
        
        with patch('tooling.core.plugin_system.console.print') as mock_print:
            results = PluginHook.trigger('error_hook')
            
            # Should handle error and continue
            assert results == ["success"]
            mock_print.assert_called_once()
            assert "error_hook error" in mock_print.call_args[0][0]


class TestPlugin:
    """Test base Plugin class"""
    
    class ExamplePluginImpl(Plugin):
        """Test implementation"""
        
        @property
        def metadata(self):
            return PluginMetadata(
                name="test",
                version="1.0",
                description="Test plugin",
                dependencies=["rich"]
            )
        
        def register_commands(self, router):
            router.register("test", {"handler": lambda: "test"})
    
    def test_abstract_methods(self):
        """Test abstract methods must be implemented"""
        with pytest.raises(TypeError):
            Plugin()
    
    def test_validate_dependencies_success(self):
        """Test dependency validation success"""
        plugin = self.ExamplePluginImpl()
        
        # Rich should be available
        assert plugin.validate_dependencies() is True
    
    def test_validate_dependencies_missing(self):
        """Test dependency validation with missing dependency"""
        class TestPluginWithMissingDeps(Plugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test",
                    version="1.0",
                    description="Test",
                    dependencies=["nonexistent_module_xyz"]
                )
            
            def register_commands(self, router):
                pass
        
        plugin = TestPluginWithMissingDeps()
        
        with patch('tooling.core.plugin_system.console.print') as mock_print:
            assert plugin.validate_dependencies() is False
            mock_print.assert_called_once()
            assert "missing dependency" in mock_print.call_args[0][0]
    
    def test_initialize(self):
        """Test plugin initialization"""
        plugin = self.ExamplePluginImpl()
        config = {"test": "value"}
        
        # Should not raise
        plugin.initialize(config)
    
    def test_cleanup(self):
        """Test plugin cleanup"""
        plugin = self.ExamplePluginImpl()
        
        # Should not raise
        plugin.cleanup()


class TestCommandPlugin:
    """Test CommandPlugin class"""
    
    class ExampleCommandPluginImpl(CommandPlugin):
        """Test implementation"""
        
        @property
        def metadata(self):
            return PluginMetadata(
                name="test_commands",
                version="1.0",
                description="Test command plugin"
            )
        
        def get_commands(self):
            return {
                'hello': {
                    'description': 'Say hello',
                    'handler': self.hello_command
                },
                'goodbye': {
                    'description': 'Say goodbye',
                    'handler': self.goodbye_command
                }
            }
        
        def hello_command(self):
            return "Hello!"
        
        def goodbye_command(self):
            return "Goodbye!"
    
    def test_get_commands(self):
        """Test command retrieval"""
        plugin = self.ExampleCommandPluginImpl()
        commands = plugin.get_commands()
        
        assert 'hello' in commands
        assert 'goodbye' in commands
        assert commands['hello']['handler']() == "Hello!"
        assert commands['goodbye']['handler']() == "Goodbye!"
    
    def test_register_commands(self):
        """Test command registration"""
        plugin = self.ExampleCommandPluginImpl()
        router = Mock()
        
        plugin.register_commands(router)
        
        # Should register both commands
        assert router.register.call_count == 2
        router.register.assert_any_call('hello', plugin.get_commands()['hello'])
        router.register.assert_any_call('goodbye', plugin.get_commands()['goodbye'])


class TestPluginManager:
    """Test plugin manager"""
    
    def test_singleton(self):
        """Test singleton pattern"""
        # Reset singleton
        PluginManager._instance = None
        
        manager1 = PluginManager()
        manager2 = PluginManager()
        assert manager1 is manager2
    
    def test_default_paths(self):
        """Test default plugin paths"""
        manager = PluginManager()
        
        # Should have some default paths
        assert len(manager.plugin_paths) > 0
        
        # Check for expected paths
        path_strs = [str(p) for p in manager.plugin_paths]
        assert any('plugins' in p for p in path_strs)
    
    @patch.dict(os.environ, {'RT_PLUGIN_PATH': '/custom/plugins:/another/path'})
    def test_custom_plugin_paths(self):
        """Test custom plugin paths from environment"""
        # Need to create new instance to pick up env var
        PluginManager._instance = None
        manager = PluginManager()
        
        path_strs = [str(p) for p in manager.plugin_paths]
        assert '/custom/plugins' in path_strs
        assert '/another/path' in path_strs
    
    def test_is_valid_plugin(self):
        """Test plugin validation"""
        manager = PluginManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Valid plugin
            f.write("""
class MyPlugin(Plugin):
    pass
""")
            f.flush()
            assert manager._is_valid_plugin(Path(f.name)) is True
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Invalid - no Plugin class
            f.write("""
def some_function():
    pass
""")
            f.flush()
            assert manager._is_valid_plugin(Path(f.name)) is False
    
    def test_discover_plugins(self):
        """Test plugin discovery"""
        manager = PluginManager()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir)
            
            # Create test plugin file
            plugin_file = plugin_dir / "test_plugin.py"
            plugin_file.write_text("""
from tooling.core.plugin_system import Plugin

class TestPlugin(Plugin):
    pass
""")
            
            # Create non-plugin file
            other_file = plugin_dir / "not_plugin.py"
            other_file.write_text("# Just a regular file")
            
            # Create ignored file
            ignored_file = plugin_dir / "_ignored.py"
            ignored_file.write_text("class IgnoredPlugin(Plugin): pass")
            
            # Add to plugin paths
            manager.plugin_paths = [plugin_dir]
            
            # Discover
            discovered = manager.discover_plugins()
            
            assert "test_plugin" in discovered
            assert "not_plugin" not in discovered
            assert "_ignored" not in discovered
    
    def test_load_plugin_from_file(self):
        """Test loading plugin from file"""
        manager = PluginManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
from tooling.core.plugin_system import Plugin, PluginMetadata

class TestPlugin(Plugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_loaded",
            version="1.0",
            description="Test loaded plugin"
        )
    
    def register_commands(self, router):
        pass
""")
            f.flush()
            
            with patch('tooling.core.plugin_system.console.print') as mock_print:
                plugin = manager._load_plugin_from_file("test", Path(f.name))
                
                assert plugin is not None
                assert plugin.metadata.name == "test_loaded"
                mock_print.assert_called_with("[green]✓ Loaded plugin: test_loaded[/green]")
    
    def test_load_plugin_invalid_file(self):
        """Test loading invalid plugin file"""
        manager = PluginManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("# Not a valid plugin")
            f.flush()
            
            with patch('tooling.core.plugin_system.console.print') as mock_print:
                plugin = manager._load_plugin_from_file("test", Path(f.name))
                
                assert plugin is None
                mock_print.assert_called_with("[yellow]No valid Plugin class found in " + f.name + "[/yellow]")
    
    def test_load_plugin_with_error(self):
        """Test loading plugin that raises error"""
        manager = PluginManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("raise ValueError('Test error')")
            f.flush()
            
            with patch('tooling.core.plugin_system.console.print') as mock_print:
                plugin = manager._load_plugin_from_file("test", Path(f.name))
                
                assert plugin is None
                assert mock_print.call_count == 1
                assert "Failed to load plugin test" in mock_print.call_args[0][0]
    
    def test_load_all_plugins(self):
        """Test loading all discovered plugins"""
        manager = PluginManager()
        
        # Mock discover and load
        with patch.object(manager, 'discover_plugins', return_value=['plugin1', 'plugin2']):
            with patch.object(manager, 'load_plugin') as mock_load:
                mock_plugin = Mock()
                mock_load.return_value = mock_plugin
                
                config = {
                    'plugins': {
                        'plugin1': {'setting': 'value1'},
                        'plugin2': {'setting': 'value2'}
                    }
                }
                
                manager.load_all_plugins(config)
                
                # Should load both plugins
                assert mock_load.call_count == 2
                mock_load.assert_any_call('plugin1')
                mock_load.assert_any_call('plugin2')
                
                # Should initialize with config
                assert mock_plugin.initialize.call_count == 2
                mock_plugin.initialize.assert_any_call({'setting': 'value1'})
                mock_plugin.initialize.assert_any_call({'setting': 'value2'})
    
    def test_unload_plugin(self):
        """Test unloading plugin"""
        manager = PluginManager()
        
        # Add test plugin
        mock_plugin = Mock()
        manager.plugins['test'] = mock_plugin
        
        # Add to sys.modules
        import sys
        sys.modules['rt_plugin_test'] = Mock()
        
        with patch('tooling.core.plugin_system.console.print') as mock_print:
            result = manager.unload_plugin('test')
            
            assert result is True
            assert 'test' not in manager.plugins
            assert 'rt_plugin_test' not in sys.modules
            mock_plugin.cleanup.assert_called_once()
            mock_print.assert_called_with("[yellow]Unloaded plugin: test[/yellow]")
    
    def test_unload_nonexistent_plugin(self):
        """Test unloading non-existent plugin"""
        manager = PluginManager()
        
        result = manager.unload_plugin('nonexistent')
        assert result is False
    
    def test_reload_plugin(self):
        """Test reloading plugin"""
        manager = PluginManager()
        
        with patch.object(manager, 'unload_plugin') as mock_unload:
            with patch.object(manager, 'load_plugin') as mock_load:
                mock_plugin = Mock()
                mock_load.return_value = mock_plugin
                
                result = manager.reload_plugin('test')
                
                mock_unload.assert_called_once_with('test')
                mock_load.assert_called_once_with('test')
                assert result == mock_plugin


class TestGlobalFunctions:
    """Test global helper functions"""
    
    def test_load_plugins(self):
        """Test load_plugins function"""
        with patch('tooling.core.plugin_system.plugin_manager.load_all_plugins') as mock_load:
            config = {'test': 'config'}
            manager = load_plugins(config)
            
            mock_load.assert_called_once_with(config)
            assert manager is not None
    
    def test_trigger_hook_function(self):
        """Test trigger_hook function"""
        with patch.object(PluginHook, 'trigger', return_value=['result']) as mock_trigger:
            results = trigger_hook('test_hook', 'arg1', kwarg='value')
            
            mock_trigger.assert_called_once_with('test_hook', 'arg1', kwarg='value')
            assert results == ['result']


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 