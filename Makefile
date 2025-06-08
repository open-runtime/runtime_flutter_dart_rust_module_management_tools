# Runtime Tools Makefile
# Build binaries for all platforms

.PHONY: all clean build-macos build-linux build-windows release-all test install dev-install

# Variables
PYTHON := python3
BINARY_NAME := runtime_fdr_management_tools
VERSION := $(shell grep version pyproject.toml | head -1 | cut -d'"' -f2)

all: build-macos

clean:
	rm -rf build/ dist/ *.spec
	rm -f $(BINARY_NAME) $(BINARY_NAME).exe
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

install:
	$(PYTHON) -m pip install -e .

dev-install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tooling/tests/

build-macos:
	@echo "Building for macOS..."
	cd tooling && $(PYTHON) setup_binary.py
	@echo "✅ macOS binary built: $(BINARY_NAME)"

build-linux:
	@echo "Building for Linux..."
	cd tooling && $(PYTHON) setup_binary.py
	@echo "✅ Linux binary built: $(BINARY_NAME)"

build-windows:
	@echo "Building for Windows..."
	cd tooling && $(PYTHON) setup_binary.py
	@echo "✅ Windows binary built: $(BINARY_NAME).exe"

# Cross-platform builds (requires Docker)
build-linux-docker:
	docker run --rm -v "$(PWD)":/app -w /app python:3.9-slim \
		bash -c "pip install -r requirements.txt && cd tooling && python setup_binary.py"

build-windows-docker:
	docker run --rm -v "$(PWD)":/app -w /app tobix/pywine:3.9 \
		bash -c "pip install -r requirements.txt && cd tooling && python setup_binary.py"

release-all: clean
	@echo "Building release binaries for version $(VERSION)..."
	make build-macos
	mv $(BINARY_NAME) $(BINARY_NAME)-$(VERSION)-macos
	make build-linux-docker
	mv $(BINARY_NAME) $(BINARY_NAME)-$(VERSION)-linux
	make build-windows-docker
	mv $(BINARY_NAME).exe $(BINARY_NAME)-$(VERSION)-windows.exe
	@echo "✅ All binaries built for version $(VERSION)"

# Development shortcuts
fmt:
	black tooling/
	ruff tooling/ --fix

lint:
	black --check tooling/
	ruff tooling/
	mypy tooling/ --ignore-missing-imports

coverage:
	$(PYTHON) -m pytest --cov=tooling --cov-report=html tooling/tests/
	@echo "Coverage report generated in htmlcov/"

# Quick commands
commit:
	./runtime_fdr_management_tools commit

release:
	./runtime_fdr_management_tools release

changelog:
	./runtime_fdr_management_tools changelog

# Help
help:
	@echo "Runtime Tools Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install          Install the package"
	@echo "  make dev-install      Install with dev dependencies"
	@echo "  make test            Run tests"
	@echo "  make build-macos     Build macOS binary"
	@echo "  make build-linux     Build Linux binary"
	@echo "  make build-windows   Build Windows binary"
	@echo "  make release-all     Build all platform binaries"
	@echo "  make clean           Clean build artifacts"
	@echo "  make fmt             Format code"
	@echo "  make lint            Run linters"
	@echo "  make coverage        Generate coverage report" 