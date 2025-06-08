"""
Tests for custom exception classes
"""
import pytest
from tooling.core.exceptions import (
    RuntimeToolsError, ConfigurationError, GitError, AIError,
    ValidationError, FileOperationError, ChangelogError,
    VersionError, DependencyError, NetworkError, format_error
)


class TestRuntimeToolsError:
    """Test base RuntimeToolsError class"""
    
    def test_basic_error(self):
        """Test basic error creation"""
        error = RuntimeToolsError("Test error message")
        assert str(error) == "RuntimeToolsError: Test error message"
        assert error.message == "Test error message"
        assert error.error_code == "RuntimeToolsError"
        assert error.details == {}
        assert error.suggestions == []
    
    def test_error_with_details(self):
        """Test error with details"""
        error = RuntimeToolsError(
            "Test error",
            error_code="TEST001",
            details={"key": "value", "number": 42}
        )
        
        error_str = str(error)
        assert "TEST001: Test error" in error_str
        assert "Details:" in error_str
        assert "key: value" in error_str
        assert "number: 42" in error_str
    
    def test_error_with_suggestions(self):
        """Test error with suggestions"""
        error = RuntimeToolsError(
            "Test error",
            suggestions=["Try this", "Or try that"]
        )
        
        error_str = str(error)
        assert "Suggestions:" in error_str
        assert "• Try this" in error_str
        assert "• Or try that" in error_str
    
    def test_error_with_all_fields(self):
        """Test error with all fields"""
        error = RuntimeToolsError(
            "Complex error",
            error_code="COMPLEX",
            details={"file": "test.py", "line": 10},
            suggestions=["Fix line 10", "Check syntax"]
        )
        
        error_str = str(error)
        assert "COMPLEX: Complex error" in error_str
        assert "Details:" in error_str
        assert "file: test.py" in error_str
        assert "line: 10" in error_str
        assert "Suggestions:" in error_str
        assert "• Fix line 10" in error_str


class TestSpecificErrors:
    """Test specific error classes"""
    
    def test_configuration_error(self):
        """Test ConfigurationError"""
        error = ConfigurationError("Config not found", config_key="api_key")
        
        assert error.error_code == "ConfigurationError"
        assert error.details["config_key"] == "api_key"
        assert len(error.suggestions) >= 3
        assert "Check your .runtime-tools.toml configuration file" in error.suggestions
    
    def test_git_error(self):
        """Test GitError"""
        error = GitError("Git operation failed", command="git push")
        
        assert error.error_code == "GitError"
        assert error.details["command"] == "git push"
        assert "Ensure you're in a Git repository" in error.suggestions
    
    def test_ai_error(self):
        """Test AIError"""
        error = AIError("API limit exceeded", model="gpt-4")
        
        assert error.error_code == "AIError"
        assert error.details["model"] == "gpt-4"
        assert "Check your AI API key is valid" in error.suggestions
    
    def test_validation_error(self):
        """Test ValidationError"""
        error = ValidationError("Invalid format", field="email")
        
        assert error.error_code == "ValidationError"
        assert error.details["field"] == "email"
        assert "Check the input format" in error.suggestions
    
    def test_file_operation_error(self):
        """Test FileOperationError"""
        error = FileOperationError(
            "Permission denied",
            file_path="/etc/passwd",
            operation="write"
        )
        
        assert error.error_code == "FileOperationError"
        assert error.details["file_path"] == "/etc/passwd"
        assert error.details["operation"] == "write"
        assert "Check file permissions" in error.suggestions
    
    def test_changelog_error(self):
        """Test ChangelogError"""
        error = ChangelogError("Invalid changelog format", package="my-package")
        
        assert error.error_code == "ChangelogError"
        assert error.details["package"] == "my-package"
        assert "Ensure changelog format is valid" in error.suggestions
    
    def test_version_error(self):
        """Test VersionError"""
        error = VersionError("Invalid version", version="1.2.3.4")
        
        assert error.error_code == "VersionError"
        assert error.details["version"] == "1.2.3.4"
        assert "Use semantic versioning (e.g., 1.2.3)" in error.suggestions
    
    def test_dependency_error(self):
        """Test DependencyError"""
        error = DependencyError("Module not found", dependency="requests")
        
        assert error.error_code == "DependencyError"
        assert error.details["dependency"] == "requests"
        assert "Install missing dependencies" in error.suggestions
    
    def test_network_error(self):
        """Test NetworkError"""
        error = NetworkError("Connection timeout", url="https://api.example.com")
        
        assert error.error_code == "NetworkError"
        assert error.details["url"] == "https://api.example.com"
        assert "Check your internet connection" in error.suggestions


class TestFormatError:
    """Test format_error function"""
    
    def test_format_runtime_tools_error(self):
        """Test formatting RuntimeToolsError"""
        error = ConfigurationError("Test error", config_key="test")
        formatted = format_error(error)
        
        assert "ConfigurationError: Test error" in formatted
        assert "config_key: test" in formatted
    
    def test_format_standard_error(self):
        """Test formatting standard Python error"""
        error = ValueError("Invalid value")
        formatted = format_error(error)
        
        assert formatted == "ValueError: Invalid value"
    
    def test_format_error_verbose(self):
        """Test verbose error formatting"""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            formatted = format_error(e, verbose=True)
            
            assert "ValueError: Test error" in formatted
            assert "Traceback:" in formatted
            assert "test_format_error_verbose" in formatted
    
    def test_custom_error_inheritance(self):
        """Test that custom errors inherit properly"""
        error = GitError("Test")
        
        assert isinstance(error, RuntimeToolsError)
        assert isinstance(error, Exception)
    
    def test_error_with_existing_suggestions(self):
        """Test error with pre-existing suggestions"""
        error = ConfigurationError(
            "Test",
            suggestions=["Custom suggestion"]
        )
        
        # Should have both custom and default suggestions
        assert "Custom suggestion" in error.suggestions
        assert "Check your .runtime-tools.toml configuration file" in error.suggestions
        assert len(error.suggestions) >= 4  # 1 custom + 3 defaults 