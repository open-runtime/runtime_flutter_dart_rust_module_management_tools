#!/usr/bin/env python3
"""
common_config.py - Shared configuration and utilities for all tooling scripts
Import this module in other scripts: from tooling.core.common_config import *

Provides the same functionality as common_config.sh but in Python

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import subprocess
import tempfile
import shutil
import re
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

class Colors:
    """ANSI color codes for output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    GRAY = '\033[0;90m'
    NC = '\033[0m'  # No Color

# Gemini configuration
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-pro-preview-05-06')

# Project paths
ROOT_CHANGELOG = "CHANGELOG.md"
DART_CHANGELOG = "dart/CHANGELOG.md"
FLUTTER_CHANGELOG = "flutter/CHANGELOG.md"
RUST_CHANGELOG = "dart/rust/CHANGELOG.md"
DART_PUBSPEC = "dart/pubspec.yaml"
FLUTTER_PUBSPEC = "flutter/pubspec.yaml"
RUST_CARGO = "dart/rust/Cargo.toml"
CARGO_DART_CONFIG = "dart/utils/configs/cargo.dart"

# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def print_color(color: str, message: str, file=None):
    """Print colored output"""
    print(f"{color}{message}{Colors.NC}", file=file or sys.stdout)

def print_header(message: str):
    """Print section headers"""
    print()
    print_color(Colors.PURPLE, "━" * 40)
    print_color(Colors.PURPLE, f"  {message}")
    print_color(Colors.PURPLE, "━" * 40)
    print()

# ============================================================================
# PROJECT VALIDATION
# ============================================================================

def ensure_project_root():
    """Ensure script is run from project root"""
    dart_pubspec = Path(DART_PUBSPEC)
    flutter_pubspec = Path(FLUTTER_PUBSPEC)
    
    if not dart_pubspec.exists() or not flutter_pubspec.exists():
        print_color(Colors.RED, "Error: This script must be run from the project root directory")
        print_color(Colors.YELLOW, f"Current directory: {os.getcwd()}")
        print_color(Colors.YELLOW, "Please cd to the project root and try again")
        sys.exit(1)

# ============================================================================
# PACKAGE NAME DETECTION
# ============================================================================

@dataclass
class PackageNames:
    """Container for all package names in the project"""
    root_package_name: str
    dart_package_name: str
    flutter_package_name: str
    rust_package_name: str
    
    def __str__(self):
        return f"Root: {self.root_package_name}, Dart: {self.dart_package_name}, Flutter: {self.flutter_package_name}, Rust: {self.rust_package_name}"

def detect_package_names(skip_validation: bool = False) -> PackageNames:
    """
    Detect package names based on repository structure.
    
    Expected structure:
    root_package_name/
    ├── dart/
    │   ├── pubspec.yaml          [runtime_{root_package_name} - Dart Package]
    │   └── rust/
    │       └── Cargo.toml        [runtime_rust_{root_package_name} - Rust Crate]
    └── flutter/
        └── pubspec.yaml          [runtime_flutter_{root_package_name} - Flutter Package]
    
    Args:
        skip_validation: Skip structure validation (for project generators)
        
    Returns:
        PackageNames object with all detected names
        
    Raises:
        SystemExit if validation fails and skip_validation is False
    """
    # Get the root package name from current directory
    current_dir = Path.cwd()
    root_package_name = current_dir.name
    
    # Validate structure unless skipped
    if not skip_validation:
        # Check required directories exist
        dart_dir = current_dir / "dart"
        flutter_dir = current_dir / "flutter"
        rust_dir = dart_dir / "rust"
        
        missing_dirs = []
        if not dart_dir.exists():
            missing_dirs.append("dart/")
        if not flutter_dir.exists():
            missing_dirs.append("flutter/")
        if not rust_dir.exists():
            missing_dirs.append("dart/rust/")
            
        # Check required files exist
        missing_files = []
        if not (dart_dir / "pubspec.yaml").exists():
            missing_files.append("dart/pubspec.yaml")
        if not (flutter_dir / "pubspec.yaml").exists():
            missing_files.append("flutter/pubspec.yaml")
        if not (rust_dir / "Cargo.toml").exists():
            missing_files.append("dart/rust/Cargo.toml")
            
        # Report any issues
        if missing_dirs or missing_files:
            print_color(Colors.RED, "Error: Invalid project structure")
            print_color(Colors.YELLOW, f"Root package name detected: {root_package_name}")
            
            if missing_dirs:
                print_color(Colors.RED, "\nMissing directories:")
                for dir_name in missing_dirs:
                    print_color(Colors.YELLOW, f"  • {dir_name}")
                    
            if missing_files:
                print_color(Colors.RED, "\nMissing files:")
                for file_name in missing_files:
                    print_color(Colors.YELLOW, f"  • {file_name}")
                    
            print_color(Colors.BLUE, "\nExpected structure:")
            print_color(Colors.GRAY, f"{root_package_name}/")
            print_color(Colors.GRAY, "├── dart/")
            print_color(Colors.GRAY, "│   ├── pubspec.yaml")
            print_color(Colors.GRAY, "│   └── rust/")
            print_color(Colors.GRAY, "│       └── Cargo.toml")
            print_color(Colors.GRAY, "└── flutter/")
            print_color(Colors.GRAY, "    └── pubspec.yaml")
            sys.exit(1)
            
        # Validate package names in files match expected convention
        dart_name = extract_yaml_value(str(dart_dir / "pubspec.yaml"), "name")
        flutter_name = extract_yaml_value(str(flutter_dir / "pubspec.yaml"), "name")
        rust_name = extract_toml_value(str(rust_dir / "Cargo.toml"), "name")
        
        expected_dart = f"runtime_{root_package_name}"
        expected_flutter = f"runtime_flutter_{root_package_name}"
        expected_rust = f"runtime_rust_{root_package_name}"
        
        mismatches = []
        if dart_name and dart_name != expected_dart:
            mismatches.append(f"Dart package: found '{dart_name}', expected '{expected_dart}'")
        if flutter_name and flutter_name != expected_flutter:
            mismatches.append(f"Flutter package: found '{flutter_name}', expected '{expected_flutter}'")
        if rust_name and rust_name != expected_rust:
            mismatches.append(f"Rust package: found '{rust_name}', expected '{expected_rust}'")
            
        if mismatches:
            print_color(Colors.YELLOW, "\nWarning: Package names don't match expected convention:")
            for mismatch in mismatches:
                print_color(Colors.YELLOW, f"  • {mismatch}")
            print_color(Colors.BLUE, "\nUsing detected names from files instead of convention.")
            
            # Use actual names from files
            return PackageNames(
                root_package_name=root_package_name,
                dart_package_name=dart_name or expected_dart,
                flutter_package_name=flutter_name or expected_flutter,
                rust_package_name=rust_name or expected_rust
            )
    
    # Return package names based on convention
    return PackageNames(
        root_package_name=root_package_name,
        dart_package_name=f"runtime_{root_package_name}",
        flutter_package_name=f"runtime_flutter_{root_package_name}",
        rust_package_name=f"runtime_rust_{root_package_name}"
    )

def get_package_info() -> Dict[str, Dict[str, Any]]:
    """
    Get package information dynamically based on detected names.
    
    Returns:
        Dictionary with package configurations including names, paths, and descriptions
    """
    names = detect_package_names()
    
    return {
        "root": {
            "changelog": "CHANGELOG.md",
            "path_pattern": r".*",  # Match all files
            "exclude_patterns": [r"^dart/", r"^flutter/"],  # But exclude package-specific files
            "name": names.root_package_name,
            "title": "Changelog",
            "description": "this project"
        },
        "dart": {
            "changelog": "dart/CHANGELOG.md",
            "path_pattern": r"^dart/(?!rust/)",
            "name": names.dart_package_name,
            "title": f"Changelog - {names.dart_package_name}",
            "description": f"the {names.dart_package_name} Dart package"
        },
        "flutter": {
            "changelog": "flutter/CHANGELOG.md", 
            "path_pattern": r"^flutter/",
            "name": names.flutter_package_name,
            "title": f"Changelog - {names.flutter_package_name}",
            "description": f"the {names.flutter_package_name} Flutter package"
        },
        "rust": {
            "changelog": "dart/rust/CHANGELOG.md",
            "path_pattern": r"^dart/rust/",
            "name": names.rust_package_name,
            "title": f"Changelog - {names.rust_package_name}",
            "description": "the Rust FFI bindings"
        }
    }

# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

def check_api_key() -> bool:
    """Check and normalize API key"""
    gemini_key = os.environ.get('GEMINI_API_KEY')
    
    if not gemini_key:
        alt_key = os.environ.get('GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS')
        if alt_key:
            os.environ['GEMINI_API_KEY'] = alt_key
            return True
        else:
            print_color(Colors.RED, "Error: GEMINI_API_KEY environment variable is not set")
            print_color(Colors.YELLOW, "")
            print_color(Colors.YELLOW, "To set up AI tools and API key, run:")
            print_color(Colors.GREEN, "  ./tooling/setup_ai_tools.py")
            print_color(Colors.YELLOW, "")
            print_color(Colors.YELLOW, "This will:")
            print_color(Colors.YELLOW, "  • Install gemini-cli if needed")
            print_color(Colors.YELLOW, "  • Guide you through API key setup")
            print_color(Colors.YELLOW, "  • Make all scripts executable")
            print_color(Colors.YELLOW, "")
            print_color(Colors.YELLOW, "Or set it temporarily:")
            print_color(Colors.GREEN, "  export GEMINI_API_KEY='your-api-key-here'")
            return False
    return True

def check_gemini_cli() -> bool:
    """Check if gemini-cli is available"""
    if not shutil.which('gemini-cli'):
        print_color(Colors.RED, "Error: gemini-cli is not installed")
        print_color(Colors.YELLOW, "")
        print_color(Colors.YELLOW, "To install gemini-cli and set up AI tools, run:")
        print_color(Colors.GREEN, "  ./tooling/setup_ai_tools.py")
        print_color(Colors.YELLOW, "")
        print_color(Colors.YELLOW, "This will:")
        print_color(Colors.YELLOW, "  • Install Go if needed")
        print_color(Colors.YELLOW, "  • Install gemini-cli")
        print_color(Colors.YELLOW, "  • Set up your API key")
        print_color(Colors.YELLOW, "  • Configure your PATH")
        return False
    return True

def check_ai_prerequisites() -> bool:
    """Check all AI prerequisites (convenience function)"""
    all_good = True
    
    # Check gemini-cli
    if not check_gemini_cli():
        all_good = False
    
    # Check API key
    if not check_api_key():
        all_good = False
    
    if not all_good:
        print_color(Colors.YELLOW, "")
        print_color(Colors.YELLOW, "To set up all AI tools at once, run:")
        print_color(Colors.GREEN, "  ./tooling/setup_ai_tools.py")
        return False
    
    return True

# ============================================================================
# FILE OPERATIONS
# ============================================================================

def ensure_executable(script_path: str):
    """Make script executable"""
    script = Path(script_path)
    if script.exists() and not os.access(script, os.X_OK):
        script.chmod(script.stat().st_mode | 0o755)

def add_go_bin_to_path():
    """Add Go bin directories to PATH (avoiding duplicates)"""
    home = Path.home()
    go_bin = home / "go" / "bin"
    
    current_path = os.environ.get('PATH', '')
    go_bin_str = str(go_bin)
    
    if go_bin_str not in current_path:
        os.environ['PATH'] = f"{current_path}:{go_bin_str}"

# ============================================================================
# FILE PARSING UTILITIES
# ============================================================================

def extract_yaml_value(file_path: str, key: str) -> Optional[str]:
    """Safely extract value from YAML file"""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip().startswith(f"{key}:"):
                    # Extract value after colon, removing quotes and whitespace
                    value = line.split(':', 1)[1].strip()
                    value = value.strip('\'"')
                    return value
    except FileNotFoundError:
        return None
    return None

def extract_toml_value(file_path: str, key: str) -> Optional[str]:
    """Safely extract value from TOML file"""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip().startswith(f'{key} ='):
                    # Extract value between quotes
                    match = re.search(r'"([^"]*)"', line)
                    if match:
                        return match.group(1)
    except FileNotFoundError:
        return None
    return None

def get_current_version() -> Optional[str]:
    """Get current version from Dart pubspec"""
    version = extract_yaml_value(DART_PUBSPEC, "version")
    if not version:
        print_color(Colors.RED, f"Error: Could not extract version from {DART_PUBSPEC}")
        return None
    return version

# ============================================================================
# COMMAND EXECUTION
# ============================================================================

def run_command(cmd: List[str], capture_output: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
    """Run command with retry capability"""
    try:
        if capture_output:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        else:
            result = subprocess.run(cmd, timeout=timeout)
            return result.returncode, "", ""
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)

def run_with_retry(max_attempts: int, command: List[str]) -> bool:
    """Run command with retry logic"""
    attempt = 1
    
    while attempt <= max_attempts:
        code, stdout, stderr = run_command(command)
        if code == 0:
            return True
        
        if attempt < max_attempts:
            print_color(Colors.YELLOW, f"  Retry attempt {attempt}/{max_attempts}...")
            time.sleep(2)
        attempt += 1
    
    return False

# ============================================================================
# CLEANUP
# ============================================================================

def cleanup_temp_files():
    """Cleanup temp files on exit"""
    temp_dir = tempfile.gettempdir()
    patterns = ['smart_commit_*', 'sync_changelog_*', 'prepare_patch_*']
    
    for pattern in patterns:
        for temp_file in Path(temp_dir).glob(pattern):
            try:
                temp_file.unlink()
            except:
                pass

# ============================================================================
# VERSION VALIDATION
# ============================================================================

def validate_version(version: str) -> bool:
    """Validate semantic version format"""
    return bool(re.match(r'^\d+\.\d+\.\d+$', version))

def compare_versions(v1: str, v2: str) -> int:
    """Compare versions (returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2)"""
    def version_tuple(v):
        return tuple(map(int, v.split('.')))
    
    v1_tuple = version_tuple(v1)
    v2_tuple = version_tuple(v2)
    
    if v1_tuple < v2_tuple:
        return -1
    elif v1_tuple > v2_tuple:
        return 1
    else:
        return 0

# ============================================================================
# GIT OPERATIONS
# ============================================================================

def check_git_repo() -> bool:
    """Check if we're in a git repository"""
    code, _, _ = run_command(['git', 'rev-parse', '--git-dir'])
    return code == 0

def check_git_state() -> bool:
    """Check git state (detached HEAD, rebase, etc.)"""
    # Check for detached HEAD
    code, _, _ = run_command(['git', 'symbolic-ref', '-q', 'HEAD'])
    if code != 0:
        print_color(Colors.YELLOW, "Warning: You are in 'detached HEAD' state")
        return False
    
    # Get git directory
    code, git_dir, _ = run_command(['git', 'rev-parse', '--git-dir'])
    if code != 0:
        return False
    
    git_path = Path(git_dir)
    
    # Check for rebase in progress
    if (git_path / "rebase-merge").exists() or (git_path / "rebase-apply").exists():
        print_color(Colors.RED, "Error: Rebase in progress. Please complete or abort the rebase.")
        return False
    
    # Check for merge in progress
    if (git_path / "MERGE_HEAD").exists():
        print_color(Colors.RED, "Error: Merge in progress. Please complete or abort the merge.")
        return False
    
    # Check for cherry-pick in progress
    if (git_path / "CHERRY_PICK_HEAD").exists():
        print_color(Colors.RED, "Error: Cherry-pick in progress. Please complete or abort the cherry-pick.")
        return False
    
    return True

def check_remote_sync() -> bool:
    """Check if current branch is up to date with remote"""
    # Get current branch
    code, branch, _ = run_command(['git', 'branch', '--show-current'])
    if code != 0:
        return False
    
    # Fetch latest from remote
    run_command(['git', 'fetch', 'origin', branch, '--quiet'])
    
    # Check if we're behind
    code, behind_str, _ = run_command(['git', 'rev-list', '--count', f'HEAD..origin/{branch}'])
    if code == 0:
        behind = int(behind_str) if behind_str.isdigit() else 0
        if behind > 0:
            print_color(Colors.YELLOW, f"Warning: Your branch is {behind} commits behind origin/{branch}")
            print_color(Colors.YELLOW, f"Consider pulling latest changes: git pull origin {branch}")
            return False
    
    # Check if we're ahead
    code, ahead_str, _ = run_command(['git', 'rev-list', '--count', f'origin/{branch}..HEAD'])
    if code == 0:
        ahead = int(ahead_str) if ahead_str.isdigit() else 0
        if ahead > 0:
            print_color(Colors.BLUE, f"Info: Your branch is {ahead} commits ahead of origin/{branch}")
    
    return True

# ============================================================================
# VERSION FILE UPDATES
# ============================================================================

def update_version_in_file(file_path: str, new_version: str, file_type: str) -> bool:
    """Update version in any file type"""
    file_obj = Path(file_path)
    if not file_obj.exists():
        return False
    
    # Create backup
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        if file_type == "yaml":
            # Update YAML version line
            new_content = re.sub(
                r'^version:\s*.*$',
                f'version: {new_version}',
                content,
                flags=re.MULTILINE
            )
        elif file_type == "toml":
            # Update TOML version line
            new_content = re.sub(
                r'^version\s*=\s*"[^"]*"',
                f'version = "{new_version}"',
                content,
                flags=re.MULTILINE
            )
        elif file_type == "dart":
            # Update Dart constant
            new_content = re.sub(
                r"const String CARGO_VERSION = '[^']*'",
                f"const String CARGO_VERSION = '{new_version}'",
                content
            )
        else:
            return False
        
        # Write updated content
        with open(file_path, 'w') as f:
            f.write(new_content)
        
        # Verify the update
        if file_type == "yaml":
            updated = extract_yaml_value(file_path, "version")
        elif file_type == "toml":
            updated = extract_toml_value(file_path, "version")
        else:  # dart
            # For dart files, just assume success since it's a simple replacement
            os.remove(backup_path)
            return True
        
        if updated == new_version:
            os.remove(backup_path)
            return True
        else:
            # Restore backup
            shutil.move(backup_path, file_path)
            return False
            
    except Exception:
        # Restore backup
        if os.path.exists(backup_path):
            shutil.move(backup_path, file_path)
        return False

def update_all_versions(new_version: str) -> bool:
    """Update all project versions"""
    print_header(f"Updating Version Files to {new_version}")
    
    success = True
    
    # Update Dart
    if update_version_in_file(DART_PUBSPEC, new_version, "yaml"):
        print_color(Colors.GREEN, "  ✓ Updated Dart package version")
    else:
        print_color(Colors.RED, "  ✗ Failed to update Dart package version")
        success = False
    
    # Update Flutter
    if update_version_in_file(FLUTTER_PUBSPEC, new_version, "yaml"):
        print_color(Colors.GREEN, "  ✓ Updated Flutter package version")
    else:
        print_color(Colors.RED, "  ✗ Failed to update Flutter package version")
        success = False
    
    # Update Rust
    if update_version_in_file(RUST_CARGO, new_version, "toml"):
        print_color(Colors.GREEN, "  ✓ Updated Rust package version")
    else:
        # Try cargo.dart as fallback
        if update_version_in_file(CARGO_DART_CONFIG, new_version, "dart"):
            print_color(Colors.YELLOW, "  ⚠ Updated version in cargo.dart (Cargo.toml not found)")
        else:
            print_color(Colors.RED, "  ✗ Failed to update Rust package version")
            success = False
    
    # Also update cargo.dart if both exist
    if Path(CARGO_DART_CONFIG).exists() and Path(RUST_CARGO).exists():
        if update_version_in_file(CARGO_DART_CONFIG, new_version, "dart"):
            print_color(Colors.GREEN, "  ✓ Updated cargo.dart config")
    
    return success

# ============================================================================
# CHANGELOG OPERATIONS
# ============================================================================

def extract_changelog_section(file_path: str, version: str) -> str:
    """Extract changelog section for a specific version"""
    # Remove 'v' prefix if present for consistency
    version = version.lstrip('v')
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return ""
    
    # Find the version header
    start_line = None
    for i, line in enumerate(lines):
        if line.startswith('## [') and f'[v{version}]' in line:
            start_line = i + 1
            break
    
    if start_line is None:
        return ""
    
    # Find the next version header or end of file
    end_line = len(lines)
    for i in range(start_line, len(lines)):
        if lines[i].startswith('## ['):
            end_line = i
            break
    
    # Extract the section and trim empty lines
    section_lines = lines[start_line:end_line]
    
    # Remove empty lines at start and end
    while section_lines and not section_lines[0].strip():
        section_lines.pop(0)
    while section_lines and not section_lines[-1].strip():
        section_lines.pop()
    
    return ''.join(section_lines).rstrip()

# ============================================================================
# SETUP ON IMPORT
# ============================================================================

# Add Go bin to PATH when module is imported
add_go_bin_to_path()

# Set up cleanup on exit
import atexit
atexit.register(cleanup_temp_files)