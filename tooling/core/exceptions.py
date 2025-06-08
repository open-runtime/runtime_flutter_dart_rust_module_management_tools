"""
Custom exception classes for Runtime Tools

Provides structured error handling with helpful messages and recovery suggestions.
"""
from typing import Optional, Dict, Any, List


class RuntimeToolsError(Exception):
    """Base exception for all Runtime Tools errors"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.suggestions = suggestions or []
    
    def __str__(self) -> str:
        """Format error message with details"""
        parts = [f"{self.error_code}: {self.message}"]
        
        if self.details:
            parts.append("\nDetails:")
            for key, value in self.details.items():
                parts.append(f"  {key}: {value}")
        
        if self.suggestions:
            parts.append("\nSuggestions:")
            for suggestion in self.suggestions:
                parts.append(f"  • {suggestion}")
        
        return "\n".join(parts)


class ConfigurationError(RuntimeToolsError):
    """Raised when configuration is invalid or missing"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        if config_key:
            kwargs.setdefault('details', {})['config_key'] = config_key
        
        kwargs.setdefault('suggestions', []).extend([
            "Check your .runtime-tools.toml configuration file",
            "Run 'runtime_fdr_management_tools setup' to create a default configuration",
            "Set required environment variables"
        ])
        
        super().__init__(message, **kwargs)


class GitError(RuntimeToolsError):
    """Raised when Git operations fail"""
    
    def __init__(self, message: str, command: Optional[str] = None, **kwargs):
        if command:
            kwargs.setdefault('details', {})['command'] = command
        
        kwargs.setdefault('suggestions', []).extend([
            "Ensure you're in a Git repository",
            "Check your Git configuration",
            "Verify you have the necessary permissions"
        ])
        
        super().__init__(message, **kwargs)


class AIError(RuntimeToolsError):
    """Raised when AI operations fail"""
    
    def __init__(self, message: str, model: Optional[str] = None, **kwargs):
        if model:
            kwargs.setdefault('details', {})['model'] = model
        
        kwargs.setdefault('suggestions', []).extend([
            "Check your AI API key is valid",
            "Verify you have sufficient API credits",
            "Try again with a different model",
            "Check your internet connection"
        ])
        
        super().__init__(message, **kwargs)


class ValidationError(RuntimeToolsError):
    """Raised when validation fails"""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        if field:
            kwargs.setdefault('details', {})['field'] = field
        
        kwargs.setdefault('suggestions', []).extend([
            "Check the input format",
            "Ensure all required fields are provided",
            "Verify the data types are correct"
        ])
        
        super().__init__(message, **kwargs)


class FileOperationError(RuntimeToolsError):
    """Raised when file operations fail"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, operation: Optional[str] = None, **kwargs):
        details = kwargs.setdefault('details', {})
        if file_path:
            details['file_path'] = file_path
        if operation:
            details['operation'] = operation
        
        kwargs.setdefault('suggestions', []).extend([
            "Check file permissions",
            "Ensure the file/directory exists",
            "Verify you have write access to the location",
            "Check available disk space"
        ])
        
        super().__init__(message, **kwargs)


class ChangelogError(RuntimeToolsError):
    """Raised when changelog operations fail"""
    
    def __init__(self, message: str, package: Optional[str] = None, **kwargs):
        if package:
            kwargs.setdefault('details', {})['package'] = package
        
        kwargs.setdefault('suggestions', []).extend([
            "Ensure changelog format is valid",
            "Check for conflicting versions",
            "Verify package structure is correct",
            "Run validation with --skip-validation to bypass checks"
        ])
        
        super().__init__(message, **kwargs)


class VersionError(RuntimeToolsError):
    """Raised when version operations fail"""
    
    def __init__(self, message: str, version: Optional[str] = None, **kwargs):
        if version:
            kwargs.setdefault('details', {})['version'] = version
        
        kwargs.setdefault('suggestions', []).extend([
            "Use semantic versioning (e.g., 1.2.3)",
            "Check for version conflicts",
            "Ensure version is higher than current",
            "Use --force to override version checks"
        ])
        
        super().__init__(message, **kwargs)


class DependencyError(RuntimeToolsError):
    """Raised when dependencies are missing or incompatible"""
    
    def __init__(self, message: str, dependency: Optional[str] = None, **kwargs):
        if dependency:
            kwargs.setdefault('details', {})['dependency'] = dependency
        
        kwargs.setdefault('suggestions', []).extend([
            "Install missing dependencies",
            "Update to compatible versions",
            "Check requirements.txt file",
            "Run 'pip install -r requirements.txt'"
        ])
        
        super().__init__(message, **kwargs)


class NetworkError(RuntimeToolsError):
    """Raised when network operations fail"""
    
    def __init__(self, message: str, url: Optional[str] = None, **kwargs):
        if url:
            kwargs.setdefault('details', {})['url'] = url
        
        kwargs.setdefault('suggestions', []).extend([
            "Check your internet connection",
            "Verify the URL is correct",
            "Check proxy settings if behind firewall",
            "Try again later"
        ])
        
        super().__init__(message, **kwargs)


# Convenience function to create user-friendly error messages
def format_error(error: Exception, verbose: bool = False) -> str:
    """Format any error into a user-friendly message"""
    if isinstance(error, RuntimeToolsError):
        return str(error)
    
    # For other exceptions, create a generic message
    error_type = type(error).__name__
    message = str(error)
    
    if verbose:
        import traceback
        return f"{error_type}: {message}\n\nTraceback:\n{traceback.format_exc()}"
    
    return f"{error_type}: {message}" 