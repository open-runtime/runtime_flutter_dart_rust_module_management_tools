from setuptools import setup, find_packages
import os

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
def read_requirements(filename):
    """Read requirements from a file."""
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Base requirements
install_requires = [
    "click>=8.0.0",
    "colorama>=0.4.4",
    "requests>=2.25.0",
    "gitpython>=3.1.0",
    "pyyaml>=5.4.0",
    "toml>=0.10.2",
    "jinja2>=3.0.0",
    "aiohttp>=3.8.0",
    "aiofiles>=0.8.0",
    "networkx>=2.6.0",
    "matplotlib>=3.4.0",
    "numpy>=1.21.0",
    "scikit-learn>=1.0.0",
]

# Optional dependencies for different features
extras_require = {
    'ai': [
        'openai>=0.27.0',  # For OpenAI integration
    ],
    'dev': [
        'pytest>=6.2.0',
        'pytest-asyncio>=0.18.0',
        'pytest-cov>=3.0.0',
        'black>=22.0.0',
        'flake8>=4.0.0',
        'mypy>=0.950',
    ],
    'all': [],  # Will be populated below
}

# Add all extras to 'all'
extras_require['all'] = list(set(sum(extras_require.values(), [])))

setup(
    name="runtime-fdr-pkg-tools",
    version="0.1.0",
    author="Tsavo Knott",
    author_email="your.email@example.com",
    description="A comprehensive suite of CLI tools for managing multi-package repositories",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/open-runtime/runtime_flutter_dart_rust_package_management_tools",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Version Control :: Git",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            # AI-Powered Commit Tools
            "rt-commit=tooling.cli.smart_commit:main",
            "rt-commit-fast=tooling.cli.smart_commit_fast:main",
            
            # Changelog Management
            "rt-changelog=tooling.cli.sync_changelogs:main",
            "rt-changelog-ultra=tooling.cli.sync_changelog_ultra:main",
            "rt-changelog-analyze=tooling.cli.analyze_changelog_history:main",
            
            # Release Management
            "rt-release=tooling.cli.release:main",
            "rt-prepare-patch=tooling.cli.prepare_new_patch:main",
            "rt-push-patch=tooling.cli.push_new_patch:main",
            "rt-retag=tooling.cli.retag_release:main",
            
            # Version Management
            "rt-version=tooling.cli.update_version:main",
            "rt-next-tag=tooling.cli.get_new_patch_tag:main",
            
            # Validation Tools
            "rt-validate=tooling.cli.validate_changelogs:main",
            "rt-prerelease-check=tooling.cli.pre_release_check:main",
            
            # GitHub Integration
            "rt-pr=tooling.cli.open_pull_request_current_tagged_branch:main",
            "rt-release-notes=tooling.cli.generate_release_notes:main",
            
            # Setup and Configuration
            "rt-setup=tooling.cli.setup_ai_tools:main",
            "rt-setup-permissions=tooling.cli.setup_permissions:main",
            "rt-install-gemini=tooling.cli.install_gemini_cli:main",
            
            # Aliases for common commands
            "rtc=tooling.cli.smart_commit_fast:main",  # Quick commit
            "rtcl=tooling.cli.sync_changelogs:main",   # Quick changelog
            "rtr=tooling.cli.release:main",            # Quick release
        ],
    },
    include_package_data=True,
    package_data={
        'tooling': [
            'templates/*.j2',
            'templates/*.html',
            'config/*.yaml',
            'config/*.json',
        ],
    },
) 