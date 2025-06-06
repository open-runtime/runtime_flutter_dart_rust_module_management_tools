#!/usr/bin/env python3
"""
File utilities extracted from common_config.py
"""

import re
import shutil
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Union


def extract_yaml_value(file_path: str, key: str) -> Optional[str]:
    """Safely extract value from YAML file"""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip().startswith(f"{key}:"):
                    # Extract value after colon, removing quotes and whitespace
                    value = line.split(':', 1)[1].strip()
                    value = value.strip('\'"')
                    # Return None if the value is empty (e.g., for nested structures)
                    return value if value else None
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
            import os
            os.remove(backup_path)
            return True
        
        if updated == new_version:
            import os
            os.remove(backup_path)
            return True
        else:
            # Restore backup
            shutil.move(backup_path, file_path)
            return False
            
    except Exception:
        # Restore backup
        import os
        if os.path.exists(backup_path):
            shutil.move(backup_path, file_path)
        return False


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


def ensure_executable(script_path: str):
    """Make script executable"""
    script = Path(script_path)
    if script.exists() and not os.access(script, os.X_OK):
        script.chmod(script.stat().st_mode | 0o755)


def update_all_versions(new_version: str) -> bool:
    """Update all project versions"""
    from pathlib import Path
    
    # Define file paths
    DART_PUBSPEC = "dart/pubspec.yaml"
    FLUTTER_PUBSPEC = "flutter/pubspec.yaml"
    RUST_CARGO = "dart/rust/Cargo.toml"
    CARGO_DART_CONFIG = "dart/rust/cargo.dart"
    
    print(f"\nUpdating Version Files to {new_version}")
    print("=" * 40)
    
    success = True
    
    # Update Dart
    if update_version_in_file(DART_PUBSPEC, new_version, "yaml"):
        print("  ✓ Updated Dart package version")
    else:
        print("  ✗ Failed to update Dart package version")
        success = False
    
    # Update Flutter
    if update_version_in_file(FLUTTER_PUBSPEC, new_version, "yaml"):
        print("  ✓ Updated Flutter package version")
    else:
        print("  ✗ Failed to update Flutter package version")
        success = False
    
    # Update Rust
    if update_version_in_file(RUST_CARGO, new_version, "toml"):
        print("  ✓ Updated Rust package version")
    else:
        # Try cargo.dart as fallback
        if update_version_in_file(CARGO_DART_CONFIG, new_version, "dart"):
            print("  ⚠ Updated version in cargo.dart (Cargo.toml not found)")
        else:
            print("  ✗ Failed to update Rust package version")
            success = False
    
    # Also update cargo.dart if both exist
    if Path(CARGO_DART_CONFIG).exists() and Path(RUST_CARGO).exists():
        if update_version_in_file(CARGO_DART_CONFIG, new_version, "dart"):
            print("  ✓ Updated cargo.dart config")
    
    return success


def update_yaml_version(file_path: str, new_version: str) -> bool:
    """Update version in a YAML file"""
    return update_version_in_file(file_path, new_version, "yaml")


def find_files_by_pattern(pattern: str, root: Optional[Union[str, Path]] = None) -> List[str]:
    """
    Find files matching a glob pattern.
    
    Args:
        pattern: Glob pattern (e.g., "*.py", "**/CHANGELOG.md")
        root: Root directory to search from (default: current directory)
        
    Returns:
        List of file paths as strings
    """
    
    if root is None:
        root = Path.cwd()
    else:
        root = Path(root)
    
    # Use rglob for recursive patterns, glob for non-recursive
    if '**' in pattern:
        files = list(root.rglob(pattern.replace('**/', '')))
    else:
        files = list(root.glob(pattern))
    
    # Filter out directories and hidden files
    result = []
    for f in files:
        if f.is_file() and not any(part.startswith('.') for part in f.parts):
            # Skip common ignore patterns
            if not any(ignore in f.parts for ignore in ['node_modules', 'venv', '__pycache__', '.git']):
                result.append(str(f))
    
    return sorted(result) 