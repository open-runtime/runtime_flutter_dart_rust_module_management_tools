"""
Unit tests for configuration manager.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml

from tooling.core.config_manager import (
    UIConfig, AIConfig, GitConfig, RuntimeConfig,
    ConfigManager, get_config, reload_config
)


class TestUIConfig:
    """Test UI configuration"""
    
    def test_defaults(self):
        """Test default values"""
        config = UIConfig()
        assert config.theme == "dark"
        assert config.use_emoji is True
        assert config.progress_style == "rainbow"
        assert config.table_style == "rounded"
        assert config.use_color is True
        assert config.interactive_by_default is False
    
    def test_validation(self):
        """Test field validation"""
        # Valid values
        config = UIConfig(theme="light", progress_style="blue", table_style="double")
        assert config.theme == "light"
        
        # Invalid values should raise error
        with pytest.raises(ValueError):
            UIConfig(theme="invalid")
        
        with pytest.raises(ValueError):
            UIConfig(progress_style="invalid")
        
        with pytest.raises(ValueError):
            UIConfig(table_style="invalid")


class TestAIConfig:
    """Test AI configuration"""
    
    def test_defaults(self):
        """Test default values"""
        config = AIConfig()
        assert config.provider == "gemini"
        assert config.model == "gemini-2.0-flash"
        assert config.pro_model == "gemini-2.0-flash"
        assert config.timeout == 60
        assert config.max_retries == 3
        assert config.cache_responses is True
        assert config.cache_ttl == 3600
    
    def test_validation(self):
        """Test field validation"""
        # Valid provider
        config = AIConfig(provider="openai")
        assert config.provider == "openai"
        
        # Invalid provider
        with pytest.raises(ValueError):
            AIConfig(provider="invalid")
        
        # Timeout validation
        with pytest.raises(ValueError):
            AIConfig(timeout=5)  # Too low
        
        with pytest.raises(ValueError):
            AIConfig(timeout=400)  # Too high
    
    def test_model_validation(self):
        """Test model name validation"""
        # Valid Gemini models
        config = AIConfig(provider="gemini", model="gemini-1.5-pro")
        assert config.model == "gemini-1.5-pro"
        
        config = AIConfig(provider="gemini", model="models/gemini-pro")
        assert config.model == "models/gemini-pro"
        
        # Invalid Gemini model
        with pytest.raises(ValueError):
            AIConfig(provider="gemini", model="gpt-4")
        
        # Valid OpenAI models
        config = AIConfig(provider="openai", model="gpt-4")
        assert config.model == "gpt-4"
        
        config = AIConfig(provider="openai", model="text-davinci-003")
        assert config.model == "text-davinci-003"
        
        # Invalid OpenAI model
        with pytest.raises(ValueError):
            AIConfig(provider="openai", model="gemini-pro")


class TestRuntimeConfig:
    """Test main runtime configuration"""
    
    def test_defaults(self):
        """Test default configuration"""
        config = RuntimeConfig()
        
        # Check sub-configs
        assert isinstance(config.ui, UIConfig)
        assert isinstance(config.ai, AIConfig)
        assert isinstance(config.git, GitConfig)
        
        # Check default values
        assert config.ui.theme == "dark"
        assert config.ai.provider == "gemini"
        assert config.git.default_branch == "main"
    
    def test_load_from_file(self):
        """Test loading from YAML file"""
        # Create temp config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'ui': {'theme': 'light', 'use_emoji': False},
                'ai': {'provider': 'openai', 'model': 'gpt-4'},
                'git': {'default_branch': 'develop'},
                'custom_commands': {
                    'test': {
                        'description': 'Test command',
                        'command': 'echo test'
                    }
                }
            }, f)
            temp_path = Path(f.name)
        
        try:
            # Load config
            config = RuntimeConfig.load_from_file(temp_path)
            
            # Verify loaded values
            assert config.ui.theme == "light"
            assert config.ui.use_emoji is False
            assert config.ai.provider == "openai"
            assert config.ai.model == "gpt-4"
            assert config.git.default_branch == "develop"
            assert 'test' in config.custom_commands
            assert config.custom_commands['test']['command'] == 'echo test'
        finally:
            temp_path.unlink()
    
    def test_load_from_nonexistent_file(self):
        """Test loading from non-existent file returns defaults"""
        config = RuntimeConfig.load_from_file(Path("/nonexistent/file.yaml"))
        assert config.ui.theme == "dark"  # Should use defaults
    
    def test_project_config(self):
        """Test project-specific configuration"""
        config = RuntimeConfig(
            projects={
                'myproject': {
                    'git': {'default_branch': 'develop'},
                    'ui': {'theme': 'light'}
                }
            }
        )
        
        # Get project config
        project_config = config.get_project_config('myproject')
        assert project_config['git']['default_branch'] == 'develop'
        assert project_config['ui']['theme'] == 'light'
        
        # Non-existent project
        assert config.get_project_config('unknown') == {}
    
    def test_merge_with_project(self):
        """Test merging with project overrides"""
        config = RuntimeConfig(
            ui=UIConfig(theme="dark"),
            git=GitConfig(default_branch="main"),
            projects={
                'myproject': {
                    'ui': {'theme': 'light'},
                    'git': {'default_branch': 'develop'}
                }
            }
        )
        
        # Merge with project
        merged = config.merge_with_project('myproject')
        
        # Check overrides applied
        assert merged.ui.theme == "light"
        assert merged.git.default_branch == "develop"
        
        # Original unchanged
        assert config.ui.theme == "dark"
        assert config.git.default_branch == "main"
    
    def test_save_to_file(self):
        """Test saving configuration to file"""
        config = RuntimeConfig(
            ui=UIConfig(theme="light"),
            ai=AIConfig(provider="openai", model="gpt-4")
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Save config
            config.save_to_file(temp_path)
            
            # Load and verify
            with open(temp_path, 'r') as f:
                data = yaml.safe_load(f)
            
            assert data['ui']['theme'] == "light"
            assert data['ai']['provider'] == "openai"
            assert data['ai']['model'] == "gpt-4"
        finally:
            temp_path.unlink()
    
    def test_is_interactive_property(self):
        """Test interactive mode detection"""
        # Default
        config = RuntimeConfig()
        assert config.is_interactive is False
        
        # From config
        config = RuntimeConfig(ui=UIConfig(interactive_by_default=True))
        assert config.is_interactive is True
        
        # From environment
        config = RuntimeConfig()
        with patch.dict(os.environ, {'RT_INTERACTIVE': 'true'}):
            assert config.is_interactive is True
    
    def test_api_key_property(self):
        """Test API key retrieval"""
        # Gemini
        config = RuntimeConfig(ai=AIConfig(provider="gemini"))
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            assert config.api_key == "test-key"
        
        # OpenAI
        config = RuntimeConfig(ai=AIConfig(provider="openai"))
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-2'}):
            assert config.api_key == "test-key-2"
    
    def test_should_use_color_property(self):
        """Test color output detection"""
        # Clear any NO_COLOR env vars for this test
        import os
        old_no_color = os.environ.get('NO_COLOR')
        old_rt_no_color = os.environ.get('RT_NO_COLOR')
        
        try:
            if 'NO_COLOR' in os.environ:
                del os.environ['NO_COLOR']
            if 'RT_NO_COLOR' in os.environ:
                del os.environ['RT_NO_COLOR']
            
            # Default
            config = RuntimeConfig()
            assert config.should_use_color == True
        finally:
            # Restore env vars
            if old_no_color is not None:
                os.environ['NO_COLOR'] = old_no_color
            if old_rt_no_color is not None:
                os.environ['RT_NO_COLOR'] = old_rt_no_color
        
        # Disabled in config
        config = RuntimeConfig(ui=UIConfig(use_color=False))
        assert config.should_use_color is False
        
        # NO_COLOR environment
        config = RuntimeConfig()
        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            assert config.should_use_color is False
        
        # RT_NO_COLOR environment
        with patch.dict(os.environ, {'RT_NO_COLOR': '1'}):
            assert config.should_use_color is False
    
    def test_get_table_style(self):
        """Test table style retrieval"""
        from rich import box
        
        config = RuntimeConfig(ui=UIConfig(table_style="rounded"))
        assert config.get_table_style() == box.ROUNDED
        
        config = RuntimeConfig(ui=UIConfig(table_style="double"))
        assert config.get_table_style() == box.DOUBLE
        
        config = RuntimeConfig(ui=UIConfig(table_style="ascii"))
        assert config.get_table_style() == box.ASCII


class TestConfigManager:
    """Test configuration manager"""
    
    def test_singleton(self):
        """Test singleton pattern"""
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        assert manager1 is manager2
    
    def test_config_paths(self):
        """Test configuration search paths"""
        manager = ConfigManager()
        paths = manager.config_paths
        
        # Should include multiple paths
        assert len(paths) > 0
        
        # Check some expected paths
        assert any('.rtconfig.yaml' in str(p) for p in paths)
        assert any('.rtconfig.yml' in str(p) for p in paths)
        assert any('.config/runtime-tools' in str(p) for p in paths)
    
    @patch.dict(os.environ, {'RT_CONFIG': '/custom/config.yaml'})
    def test_custom_config_path(self):
        """Test custom config path from environment"""
        manager = ConfigManager()
        paths = manager.config_paths
        
        # Custom path should be first
        assert str(paths[0]) == '/custom/config.yaml'
    
    def test_load_config(self):
        """Test loading configuration"""
        # Create temp config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'ui': {'theme': 'light'}}, f)
            temp_path = Path(f.name)
        
        try:
            # Create a new manager instance with mocked paths
            with patch.object(ConfigManager, 'config_paths', new=property(lambda self: [temp_path])):
                # Reset singleton to force new instance
                ConfigManager._instance = None
                manager = ConfigManager()
                
                # Clear any cached config
                if hasattr(manager, '_config'):
                    manager._config = None
                if hasattr(manager.load, 'cache_clear'):
                    manager.load.cache_clear()
                
                config = manager.load()
                assert config.ui.theme == "light"
        finally:
            temp_path.unlink()
            # Reset singleton
            ConfigManager._instance = None
    
    def test_reload_config(self):
        """Test reloading configuration"""
        manager = ConfigManager()
        manager._config = Mock()
        
        with patch.object(manager, 'load') as mock_load:
            mock_load.return_value = RuntimeConfig()
            
            manager.reload()
            
            # Should clear cached config
            assert manager._config is None
            mock_load.assert_called_once()
    
    def test_create_default_config(self):
        """Test creating default configuration file"""
        manager = ConfigManager()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / '.rtconfig.yaml'
            
            from tooling.core.config_manager import console
            with patch.object(console, 'print') as mock_print:
                result = manager.create_default_config(config_path)
                
                assert result == config_path
                assert config_path.exists()
                mock_print.assert_called_once()
                
                # Verify it's valid YAML
                with open(config_path, 'r') as f:
                    data = yaml.safe_load(f)
                assert isinstance(data, dict)


class TestConfigBackwardCompatibility:
    """Test backward compatibility with simple_config.Config"""
    
    def test_get_api_key(self):
        """Test API key retrieval"""
        from tooling.core.config_manager import Config
        
        with patch('tooling.core.config_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.api_key = "test-key"
            mock_get_config.return_value = mock_config
            
            assert Config.get_api_key() == "test-key"
    
    def test_get_model(self):
        """Test model retrieval"""
        from tooling.core.config_manager import Config
        
        with patch('tooling.core.config_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.ai.model = "standard-model"
            mock_config.ai.pro_model = "pro-model"
            mock_get_config.return_value = mock_config
            
            assert Config.get_model(use_pro=False) == "standard-model"
            assert Config.get_model(use_pro=True) == "pro-model"
    
    def test_is_debug(self):
        """Test debug mode check"""
        from tooling.core.config_manager import Config
        
        with patch('tooling.core.config_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.development.debug = True
            mock_get_config.return_value = mock_config
            
            assert Config.is_debug() is True
    
    def test_is_dry_run(self):
        """Test dry run mode check"""
        from tooling.core.config_manager import Config
        
        with patch('tooling.core.config_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.development.dry_run = True
            mock_get_config.return_value = mock_config
            
            assert Config.is_dry_run() is True
    
    def test_should_use_color(self):
        """Test color output check"""
        from tooling.core.config_manager import Config
        
        with patch('tooling.core.config_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.should_use_color = True
            mock_get_config.return_value = mock_config
            
            assert Config.should_use_color() is True
    
    def test_get_log_level(self):
        """Test log level retrieval"""
        from tooling.core.config_manager import Config
        
        with patch('tooling.core.config_manager.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.development.log_level = "DEBUG"
            mock_get_config.return_value = mock_config
            
            assert Config.get_log_level() == "DEBUG"


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 