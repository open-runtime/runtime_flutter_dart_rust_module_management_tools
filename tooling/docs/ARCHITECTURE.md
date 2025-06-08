# Runtime Tools Architecture

## Overview

Runtime Tools is a comprehensive CLI toolkit for managing Flutter, Dart, and Rust packages in a monorepo environment. It provides automated tools for version management, changelog synchronization, release automation, and development workflow optimization.

## Core Design Principles

1. **Modularity**: Each tool is self-contained and can be used independently
2. **Extensibility**: Easy to add new tools and features
3. **Performance**: Optimized for large monorepos with many packages
4. **Developer Experience**: Beautiful CLI with helpful error messages
5. **Cross-Platform**: Works on macOS, Linux, and Windows

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │   runtime_fdr_management_tools    │ │ commit  │ │release  │ │changelog│  │
│  │ (main)  │ │  tools  │ │  tools  │ │  tools  │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │
│       └───────────┴───────────┴───────────┘        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│                   Core Layer                         │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ Base Config │ │ AI Operations│ │  Git Utils   │ │
│  └─────────────┘ └──────────────┘ └──────────────┘ │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │  Logging    │ │ Performance  │ │  Exceptions  │ │
│  └─────────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│                 Utils Layer                          │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ File Utils  │ │ Version Utils│ │Process Utils │ │
│  └─────────────┘ └──────────────┘ └──────────────┘ │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ Async File  │ │  Async Git   │ │CLI Utilities │ │
│  └─────────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────────────────────────────────────┘
```

## Component Details

### CLI Layer (`tooling/cli/`)

The CLI layer provides the user-facing commands and interfaces.

#### Main Entry Point (`runtime_fdr_management_tools.py`)
- Unified command interface
- Command routing and discovery
- Interactive mode support
- Shell completion

#### Tool Modules
Each tool inherits from `CLIToolsBase` and provides:
- Command-line argument parsing
- Business logic implementation
- Error handling and user feedback
- Performance tracking

**Key Tools:**
- `commit_tools.py`: AI-powered commit message generation
- `changelog_tools.py`: Changelog synchronization across packages
- `release_tools.py`: Automated release management
- `version_tools.py`: Version bumping and tagging
- `pr_tools.py`: Pull request automation

### Core Layer (`tooling/core/`)

The core layer provides fundamental services and abstractions.

#### Configuration (`base_config.py`)
- Centralized configuration management
- Environment variable handling
- Project structure validation
- Tool-specific settings

#### AI Operations (`ai_operations.py`, `ai_client.py`)
- Gemini API integration
- Prompt template management
- Response caching
- Retry logic with exponential backoff

#### Logging (`logging.py`)
- Structured logging with context
- Multiple output formats (JSON, plain text)
- Log levels and filtering
- Progress tracking

#### Performance (`performance.py`)
- Function and operation timing
- Memory profiling
- Performance reports
- Benchmarking decorators

#### Error Handling (`exceptions.py`)
- Custom exception hierarchy
- User-friendly error messages
- Recovery suggestions
- Error context preservation

### Utils Layer (`tooling/utils/`)

The utils layer provides reusable utilities and helpers.

#### File Operations
- `file_utils.py`: Synchronous file operations
- `async_file_utils.py`: Asynchronous file operations with batching
- Path manipulation and validation
- Safe file writing with atomic operations

#### Git Operations
- `git_utils.py`: Synchronous Git commands
- `async_git_utils.py`: Asynchronous Git operations
- Branch management
- Commit and tag operations

#### Version Management (`version_utils.py`)
- Semantic versioning parsing
- Version comparison and validation
- Multi-language version file handling
- Version bumping strategies

#### CLI Utilities (`cli_utils.py`)
- Rich terminal output
- Interactive prompts
- Progress bars and spinners
- Table formatting

## Data Flow

### Typical Command Execution Flow

1. **User Input**: User runs `runtime_fdr_management_tools commit` command
2. **CLI Parsing**: Arguments parsed by Click framework
3. **Tool Initialization**: CommitTools instance created with config
4. **Git Analysis**: Analyze staged changes and diffs
5. **AI Generation**: Send context to Gemini API
6. **User Interaction**: Show generated message, allow editing
7. **Git Operation**: Create commit with approved message
8. **Performance Tracking**: Log operation metrics
9. **User Feedback**: Display success/error message

### Asynchronous Operations

For performance-critical operations, we use async/await:

```python
# Parallel file reading
async with AsyncFileUtils() as file_utils:
    contents = await file_utils.read_files_batch(file_paths)

# Concurrent Git operations  
async with AsyncGitUtils() as git:
    results = await asyncio.gather(
        git.get_status(),
        git.get_log(limit=10),
        git.get_branches()
    )
```

## Configuration

### Configuration Hierarchy

1. **Default Values**: Built-in defaults in code
2. **Configuration File**: `.runtime-tools.toml` in project root
3. **Environment Variables**: Override specific settings
4. **Command Arguments**: Highest priority

### Example Configuration

```toml
# .runtime-tools.toml
[project]
name = "my-project"
type = "monorepo"

[git]
default_branch = "main"
commit_style = "conventional"

[ai]
provider = "gemini"
model = "gemini-2.0-flash-001"
temperature = 0.7

[changelog]
format = "keepachangelog"
sections = ["Added", "Changed", "Fixed", "Removed"]
```

## Testing Strategy

### Test Organization

```
tests/
├── test_cli/          # CLI command tests
├── test_core/         # Core functionality tests
├── test_utils/        # Utility function tests
├── test_setup/        # Setup and installation tests
└── fixtures/          # Test data and mocks
```

### Test Categories

1. **Unit Tests**: Individual functions and classes
2. **Integration Tests**: Component interactions
3. **CLI Tests**: Command-line interface testing
4. **Performance Tests**: Benchmark critical operations

### Coverage Goals

- Overall: 80%+ coverage
- Critical paths: 95%+ coverage
- New code: 100% coverage requirement

## Performance Considerations

### Optimization Strategies

1. **Caching**: AI responses, Git operations, file reads
2. **Parallelization**: Async operations for I/O
3. **Lazy Loading**: Import heavy dependencies only when needed
4. **Batch Operations**: Process multiple files together

### Performance Monitoring

```python
@benchmark(iterations=100)
def critical_operation():
    # Automatically tracked
    pass

with track_operation("changelog_sync"):
    # Manual tracking for complex operations
    sync_all_changelogs()
```

## Security Considerations

### API Key Management
- Never commit API keys
- Use environment variables
- Validate API key format
- Secure key storage recommendations

### File Operations
- Validate all file paths
- Prevent directory traversal
- Use atomic writes for critical files
- Check file permissions

### Git Operations
- Validate branch names
- Sanitize commit messages
- Verify remote URLs
- Check GPG signatures when configured

## Extension Points

### Adding New Tools

1. Create new module in `tooling/cli/`
2. Inherit from `CLIToolsBase`
3. Implement required methods
4. Add to command registry in `runtime_fdr_management_tools.py`
5. Add tests and documentation

### Custom AI Providers

1. Implement provider interface
2. Add to AI operations module
3. Update configuration schema
4. Add provider-specific tests

### Plugin System (Future)

- Dynamic tool loading
- Third-party extensions
- Hook system for events
- Custom command namespaces

## Best Practices

### Code Style
- Type hints for all functions
- Docstrings with examples
- Consistent error handling
- Performance tracking for slow operations

### Error Handling
```python
try:
    result = perform_operation()
except SpecificError as e:
    raise ToolError(
        "Operation failed",
        suggestions=["Try this", "Or this"],
        details={"operation": "name"}
    ) from e
```

### Logging
```python
logger.info("operation_started", 
    operation="sync",
    package=package_name,
    version=version
)
```

### Testing
```python
@pytest.mark.asyncio
async def test_async_operation():
    async with AsyncContext() as ctx:
        result = await ctx.operation()
        assert result.success
```

## Deployment

### Binary Distribution
- PyInstaller for standalone executables
- Platform-specific builds
- Auto-update mechanism
- Code signing for security

### Package Distribution
- PyPI package: `runtime-tools`
- Homebrew formula (macOS)
- Snap package (Linux)
- Chocolatey package (Windows)

## Future Roadmap

### Planned Features
1. **Web UI**: Browser-based interface
2. **IDE Plugins**: VSCode, IntelliJ integration  
3. **CI/CD Integration**: GitHub Actions, GitLab CI
4. **Multi-repo Support**: Manage multiple repositories
5. **Team Features**: Shared configurations, templates

### Performance Goals
- Sub-second response for most operations
- Handle 1000+ packages efficiently
- Minimal memory footprint
- Offline mode support

## Contributing

See [DEVELOPMENT.md](../../DEVELOPMENT.md) for development setup and guidelines.

### Key Areas for Contribution
- New tool development
- Performance optimization
- Documentation improvements
- Test coverage expansion
- Platform-specific features 