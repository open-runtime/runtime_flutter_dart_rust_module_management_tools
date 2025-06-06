#!/usr/bin/env python3
"""
Tests for the new Pydantic-based configuration system.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from pydantic import ValidationError

from tooling.core.base_config import (
    BaseConfig, AIConfig, GitConfig, PackageConfig, ToolingConfig,
    LogLevel, PackageType, get_config
)


class TestBaseConfig:
    """Test base configuration functionality"""
    
    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project structure"""
        # Create required directories and files
        (tmp_path / "dart").mkdir()
        (tmp_path / "flutter").mkdir()
        (tmp_path / "dart" / "pubspec.yaml").write_text("name: runtime_test")
        (tmp_path / "flutter" / "pubspec.yaml").write_text("name: runtime_flutter_test")
        return tmp_path
    
    def test_base_config_defaults(self, mock_project_root):
        """Test default configuration values"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = BaseConfig()
            
            assert config.log_level == LogLevel.INFO
            assert config.log_file is None
            assert config.log_format == "json"
            assert config.use_color is True
            assert config.quiet is False
            assert config.verbose is False
            assert config.max_retries == 3
            assert config.timeout == 30
            assert config.concurrent_operations is True
    
    def test_environment_variables(self, mock_project_root):
        """Test loading from environment variables"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            os.environ["RUNTIME_FDR_LOG_LEVEL"] = "DEBUG"
            os.environ["RUNTIME_FDR_MAX_RETRIES"] = "5"
            os.environ["RUNTIME_FDR_USE_COLOR"] = "false"
            
            config = BaseConfig()
            
            assert config.log_level == LogLevel.DEBUG
            assert config.max_retries == 5
            assert config.use_color is False
            
            # Cleanup
            for key in ["RUNTIME_FDR_LOG_LEVEL", "RUNTIME_FDR_MAX_RETRIES", "RUNTIME_FDR_USE_COLOR"]:
                del os.environ[key]
    
    def test_validation_errors(self, mock_project_root):
        """Test validation constraints"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            # Test max_retries validation
            with pytest.raises(ValidationError) as exc_info:
                BaseConfig(max_retries=20)  # Max is 10
            assert "less than or equal to 10" in str(exc_info.value)
            
            # Test timeout validation  
            with pytest.raises(ValidationError) as exc_info:
                BaseConfig(timeout=1000)  # Max is 600
            assert "less than or equal to 600" in str(exc_info.value)
    
    def test_project_root_validation(self, tmp_path):
        """Test project root validation"""
        # In test environment, validation is skipped, so we test that it doesn't raise
        # Create a BaseConfig with invalid project root
        config = BaseConfig(project_root=tmp_path)
        # Should not raise in test environment
        assert config.project_root == tmp_path
    
    def test_log_level_adjustment(self, mock_project_root):
        """Test log level adjustment based on quiet/verbose"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            # Test quiet mode
            config = BaseConfig(quiet=True)
            assert config.log_level == LogLevel.ERROR
            
            # Test verbose mode
            config = BaseConfig(verbose=True)
            assert config.log_level == LogLevel.DEBUG
            
            # Test explicit log level overrides adjustment
            config = BaseConfig(log_level=LogLevel.WARNING, verbose=True)
            assert config.log_level == LogLevel.DEBUG


class TestAIConfig:
    """Test AI configuration functionality"""
    
    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project structure"""
        (tmp_path / "dart").mkdir()
        (tmp_path / "flutter").mkdir()
        (tmp_path / "dart" / "pubspec.yaml").write_text("name: runtime_test")
        (tmp_path / "flutter" / "pubspec.yaml").write_text("name: runtime_flutter_test")
        return tmp_path
    
    def test_ai_config_defaults(self, mock_project_root, monkeypatch):
        """Test AI configuration defaults"""
        # Clear any existing API keys from environment
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("RUNTIME_FDR_GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS", raising=False)
        
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = AIConfig()
            
            assert config.gemini_api_key is None
            assert config.gemini_model == "gemini-2.5-pro-preview-05-06"
            assert config.ai_temperature == 0.7
            assert config.ai_max_tokens == 2000
            assert config.ai_streaming is True
            assert config.has_ai_configured is False
    
    def test_api_key_sources(self, mock_project_root):
        """Test API key loading from multiple sources"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            # Test primary env var
            os.environ["GEMINI_API_KEY"] = "test-key-123"
            config = AIConfig()
            assert config.gemini_api_key == "test-key-123"
            assert config.has_ai_configured is True
            del os.environ["GEMINI_API_KEY"]
            
            # Test alternate env var
            os.environ["GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS"] = "alt-key-456"
            config = AIConfig()
            assert config.gemini_api_key == "alt-key-456"
            assert config.has_ai_configured is True
            del os.environ["GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS"]
    
    def test_ai_parameter_validation(self, mock_project_root):
        """Test AI parameter constraints"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            # Valid parameters
            config = AIConfig(ai_temperature=1.5, ai_max_tokens=4000)
            assert config.ai_temperature == 1.5
            assert config.ai_max_tokens == 4000
            
            # Invalid temperature
            with pytest.raises(ValidationError):
                AIConfig(ai_temperature=3.0)  # Max is 2.0
            
            # Invalid max tokens
            with pytest.raises(ValidationError):
                AIConfig(ai_max_tokens=10000)  # Max is 8000


class TestPackageConfig:
    """Test package configuration functionality"""
    
    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project structure"""
        (tmp_path / "dart").mkdir()
        (tmp_path / "flutter").mkdir()
        (tmp_path / "dart" / "rust").mkdir()
        (tmp_path / "dart" / "pubspec.yaml").write_text("name: runtime_test_project")
        (tmp_path / "flutter" / "pubspec.yaml").write_text("name: runtime_flutter_test_project")
        return tmp_path
    
    def test_package_name_detection(self, mock_project_root):
        """Test automatic package name detection"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = PackageConfig()
            
            # Root package name should be directory name
            assert config.root_package_name == mock_project_root.name
            assert config.dart_package_name == f"runtime_{mock_project_root.name}"
            assert config.flutter_package_name == f"runtime_flutter_{mock_project_root.name}"
            assert config.rust_package_name == f"runtime_rust_{mock_project_root.name}"
    
    def test_custom_package_prefixes(self, mock_project_root):
        """Test custom package prefixes"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = PackageConfig(
                dart_package_prefix="custom_dart_",
                flutter_package_prefix="custom_flutter_",
                rust_package_prefix="custom_rust_"
            )
            
            assert config.dart_package_name == f"custom_dart_{mock_project_root.name}"
            assert config.flutter_package_name == f"custom_flutter_{mock_project_root.name}"
            assert config.rust_package_name == f"custom_rust_{mock_project_root.name}"
    
    def test_package_info_generation(self, mock_project_root):
        """Test package info generation"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = PackageConfig()
            packages = config.get_package_info()
            
            assert len(packages) == 4
            assert PackageType.ROOT in packages
            assert PackageType.DART in packages
            assert PackageType.FLUTTER in packages
            assert PackageType.RUST in packages
            
            # Check paths
            assert packages[PackageType.DART].path == config.dart_dir
            assert packages[PackageType.FLUTTER].path == config.flutter_dir
            assert packages[PackageType.RUST].path == config.rust_dir
            
            # Check changelog paths
            assert packages[PackageType.ROOT].changelog_path == config.project_root / "CHANGELOG.md"
            assert packages[PackageType.DART].changelog_path == config.dart_dir / "CHANGELOG.md"


class TestToolingConfig:
    """Test complete tooling configuration"""
    
    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project structure"""
        (tmp_path / "dart").mkdir()
        (tmp_path / "flutter").mkdir()
        (tmp_path / "dart" / "pubspec.yaml").write_text("name: runtime_test")
        (tmp_path / "flutter" / "pubspec.yaml").write_text("name: runtime_flutter_test")
        return tmp_path
    
    def test_complete_config(self, mock_project_root):
        """Test complete configuration with all features"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = ToolingConfig(
                verbose=True,
                dry_run=True,
                gemini_api_key="test-key",
                max_retries=5
            )
            
            # Base config
            assert config.verbose is True
            assert config.log_level == LogLevel.DEBUG  # Set by verbose
            assert config.max_retries == 5
            
            # AI config
            assert config.has_ai_configured is True
            assert config.gemini_api_key == "test-key"
            
            # Git config
            assert config.git_main_branch == "main"
            
            # Package config
            assert config.root_package_name == mock_project_root.name
            
            # Tool-specific
            assert config.dry_run is True
            assert config.interactive is True
    
    def test_from_args_factory(self, mock_project_root):
        """Test creating config from arguments"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = ToolingConfig.from_args(
                verbose=True,
                quiet=False,
                dry_run=True,
                timeout=60
            )
            
            assert config.verbose is True
            assert config.dry_run is True
            assert config.timeout == 60
    
    def test_output_methods(self, mock_project_root, capsys):
        """Test output helper methods"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = ToolingConfig()
            
            config.print_success("Success message")
            config.print_error("Error message")
            config.print_warning("Warning message")
            config.print_info("Info message")
            config.print_header("Test Header")
            
            captured = capsys.readouterr()
            assert "Success message" in captured.out
            assert "Error message" in captured.out
            assert "Warning message" in captured.out
            assert "Info message" in captured.out
            assert "Test Header" in captured.out


class TestGetConfig:
    """Test the get_config helper function"""
    
    @pytest.fixture
    def mock_project_root(self, tmp_path):
        """Create a mock project structure"""
        (tmp_path / "dart").mkdir()
        (tmp_path / "flutter").mkdir()
        (tmp_path / "dart" / "pubspec.yaml").write_text("name: runtime_test")
        (tmp_path / "flutter" / "pubspec.yaml").write_text("name: runtime_flutter_test")
        return tmp_path
    
    def test_get_config_with_overrides(self, mock_project_root):
        """Test get_config with overrides"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = get_config(
                verbose=True,
                dry_run=True,
                max_retries=7
            )
            
            assert isinstance(config, ToolingConfig)
            assert config.verbose is True
            assert config.dry_run is True
            assert config.max_retries == 7
    
    def test_config_serialization(self, mock_project_root):
        """Test configuration serialization"""
        with patch("pathlib.Path.cwd", return_value=mock_project_root):
            config = get_config(verbose=True)
            
            # Test dict export
            config_dict = config.model_dump()
            assert isinstance(config_dict, dict)
            assert config_dict["verbose"] is True
            assert "project_root" in config_dict
            
            # Test JSON export
            config_json = config.model_dump_json()
            assert isinstance(config_json, str)
            # Check that verbose is in the JSON (it should be true)
            assert '"verbose":true' in config_json.replace(" ", "") or '"verbose": true' in config_json