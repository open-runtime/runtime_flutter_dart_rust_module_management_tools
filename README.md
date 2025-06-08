# Runtime Flutter/Dart/Rust Module Management Tools 🚀

[![Build and Release](https://github.com/open-runtime/runtime_flutter_dart_rust_module_management_tools/actions/workflows/workflow.yaml/badge.svg)](https://github.com/open-runtime/runtime_flutter_dart_rust_module_management_tools/actions/workflows/workflow.yaml)
[![codecov](https://codecov.io/gh/open-runtime/runtime_flutter_dart_rust_module_management_tools/branch/main/graph/badge.svg)](https://codecov.io/gh/open-runtime/runtime_flutter_dart_rust_module_management_tools)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A comprehensive CLI toolset for managing Flutter, Dart, and Rust projects with AI-powered features, automated workflows, and production-ready capabilities.

## ✨ Features

- **🤖 AI-Powered Operations**: Intelligent commit messages, changelog generation, and PR descriptions
- **📦 Multi-Package Management**: Synchronized version control across Dart, Flutter, and Rust packages
- **🔄 Automated Workflows**: Release automation, changelog synchronization, and version bumping
- **⚡ High Performance**: Async operations, parallel processing, and smart caching
- **🎨 Beautiful CLI**: Rich terminal UI with progress indicators and interactive mode
- **🔌 Plugin System**: Extensible architecture for custom tools and workflows
- **🛡️ Type-Safe**: Full type hints and Pydantic-based configuration
- **📊 Comprehensive Testing**: 80%+ test coverage with CI/CD integration

## 🚀 Quick Start

### Installation

#### Using Pre-built Binaries (Recommended)

Download the latest binary for your platform from the [releases page](https://github.com/open-runtime/runtime_flutter_dart_rust_module_management_tools/releases).

```bash
# macOS/Linux
chmod +x runtime_fdr_management_tools
sudo mv runtime_fdr_management_tools /usr/local/bin/

# Windows
# Add the exe to your PATH
```

#### From Source

```bash
git clone https://github.com/open-runtime/runtime_flutter_dart_rust_module_management_tools.git
cd runtime_flutter_dart_rust_module_management_tools
make install
```

### Basic Usage

```bash
# Interactive mode
runtime_fdr_management_tools

# Or use the shorthand
runtime_fdr_management_tools

# Specific commands
runtime_fdr_management_tools release 1.2.3
runtime_fdr_management_tools changelog sync
runtime_fdr_management_tools commit --ai
runtime_fdr_management_tools pr create
```

## 📚 Documentation

### Available Commands

| Command | Description |
|---------|-------------|
| `release` | Create a new release with automated version bumping and changelog updates |
| `changelog` | Manage changelogs with AI-powered generation and synchronization |
| `commit` | Create commits with AI-generated messages following conventional commits |
| `pr` | Create and manage pull requests with AI-generated descriptions |
| `version` | Manage version numbers across all packages |
| `test` | Run tests across Dart, Flutter, and Rust packages |
| `format` | Format code using language-specific formatters |
| `lint` | Run linters and static analysis |

### Configuration

The tools use a Pydantic-based configuration system with environment variable support:

```bash
# Set API key for AI features
export RUNTIME_FDR_GEMINI_API_KEY=your-api-key

# Or use the legacy format
export GEMINI_API_KEY=your-api-key
```

Configuration can be customized via environment variables with the `RUNTIME_FDR_` prefix:

- `RUNTIME_FDR_LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `RUNTIME_FDR_USE_COLOR`: Enable/disable colored output
- `RUNTIME_FDR_QUIET`: Suppress non-essential output
- `RUNTIME_FDR_DRY_RUN`: Run commands without making changes

## 🏗️ Architecture

### Project Structure

```
runtime_flutter_dart_rust_module_management_tools/
├── tooling/                 # Main tooling package
│   ├── cli/                # CLI commands and tools
│   ├── core/              # Core functionality and configuration
│   ├── utils/             # Utility modules
│   ├── tests/             # Comprehensive test suite
│   └── runtime_fdr_management_tools.py              # Main entry point
├── dart/                   # Dart package
├── flutter/               # Flutter package
├── dart/rust/             # Rust FFI package
└── Makefile               # Build automation
```

### Key Components

- **CLI Tools**: Modular command structure with rich terminal UI
- **AI Operations**: Unified sync/async AI operations with multiple provider support
- **Configuration**: Type-safe Pydantic models with validation
- **Plugin System**: Extensible architecture for custom tools
- **Async Support**: High-performance async operations for file and git operations

## 🧪 Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/open-runtime/runtime_flutter_dart_rust_module_management_tools.git
cd runtime_flutter_dart_rust_module_management_tools

# Create virtual environment
make venv

# Install dependencies
make install-dev

# Run tests
make test

# Run linters
make lint
```

### Pre-commit Hooks

The project uses pre-commit hooks for code quality:

```bash
pre-commit install
```

### Building Binaries

```bash
# Build for current platform
make build

# Build for all platforms (requires Docker)
make build-all

# Build for specific platform
make build-macos
make build-linux
make build-windows
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`make test`)
5. Run linters (`make lint`)
6. Commit your changes (`git commit -m 'feat: add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📈 Technical Debt Status

We maintain high code quality standards. See [TECHNICAL_DEBT_CHECKLIST.md](tooling/TECHNICAL_DEBT_CHECKLIST.md) for our ongoing improvements.

### Current Metrics

- **Test Coverage**: 80%+ (target)
- **Type Coverage**: 90%+ (target)
- **Documentation**: Comprehensive API docs
- **Performance**: Optimized with async operations
- **Security**: Regular vulnerability scanning

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful terminal UI
- Powered by [Pydantic](https://pydantic-docs.helpmanual.io/) for robust configuration
- AI features via Google Gemini API
- Inspired by modern CLI tools like [GitHub CLI](https://cli.github.com/)

## 📞 Support

- 📧 Email: support@open-runtime.org
- 💬 Discord: [Join our community](https://discord.gg/open-runtime)
- 🐛 Issues: [GitHub Issues](https://github.com/open-runtime/runtime_flutter_dart_rust_module_management_tools/issues)

---

Made with ❤️ by the Open Runtime team
