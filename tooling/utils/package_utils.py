#!/usr/bin/env python3
"""
Package detection and information utilities
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    from tooling.utils.file_utils import extract_yaml_value, extract_toml_value
except ImportError:
    from utils.file_utils import extract_yaml_value, extract_toml_value


@dataclass
class PackageNames:
    """Container for package names"""
    root_package_name: str
    dart_package_name: str
    flutter_package_name: str
    rust_package_name: str


@dataclass
class PackageInfo:
    """Information about a package"""
    name: str
    path: Path
    changelog: str
    description: str
    version: Optional[str] = None


def detect_package_names(skip_validation: bool = False) -> PackageNames:
    """
    Detect package names from project structure.
    
    Args:
        skip_validation: Skip validation of project structure
        
    Returns:
        PackageNames object with detected names
    """
    # Get project root
    project_root = Path.cwd()
    root_name = project_root.name
    
    # Try to detect from actual files
    dart_name = None
    flutter_name = None
    rust_name = None
    
    # Check dart/pubspec.yaml
    dart_pubspec = project_root / 'dart' / 'pubspec.yaml'
    if dart_pubspec.exists():
        dart_name = extract_yaml_value(str(dart_pubspec), 'name')
    
    # Check flutter/pubspec.yaml
    flutter_pubspec = project_root / 'flutter' / 'pubspec.yaml'
    if flutter_pubspec.exists():
        flutter_name = extract_yaml_value(str(flutter_pubspec), 'name')
    
    # Check dart/rust/Cargo.toml
    rust_cargo = project_root / 'dart' / 'rust' / 'Cargo.toml'
    if rust_cargo.exists():
        rust_name = extract_toml_value(str(rust_cargo), 'name')
    
    # Use defaults if not found
    if not dart_name:
        dart_name = f"runtime_{root_name}"
    if not flutter_name:
        flutter_name = f"runtime_flutter_{root_name}"
    if not rust_name:
        rust_name = f"runtime_rust_{root_name}"
    
    # Validate structure if not skipping
    if not skip_validation:
        missing = []
        if not dart_pubspec.exists():
            missing.append("dart/pubspec.yaml")
        if not flutter_pubspec.exists():
            missing.append("flutter/pubspec.yaml")
        if not rust_cargo.exists():
            missing.append("dart/rust/Cargo.toml")
        
        if missing:
            print(f"Error: Missing required files: {', '.join(missing)}")
            print("Use --skip-validation to bypass this check")
            sys.exit(1)
    
    return PackageNames(
        root_package_name=root_name,
        dart_package_name=dart_name,
        flutter_package_name=flutter_name,
        rust_package_name=rust_name
    )


def get_package_info() -> Dict[str, PackageInfo]:
    """
    Get package information for all packages in the project.
    
    Returns:
        Dictionary with package information
    """
    names = detect_package_names(skip_validation=True)
    project_root = Path.cwd()
    
    packages = {
        "root": PackageInfo(
            name=names.root_package_name,
            path=project_root,
            changelog="CHANGELOG.md",
            description=f"Root package for {names.root_package_name}"
        ),
        "dart": PackageInfo(
            name=names.dart_package_name,
            path=project_root / "dart",
            changelog="dart/CHANGELOG.md",
            description=f"Dart package for {names.root_package_name}"
        ),
        "flutter": PackageInfo(
            name=names.flutter_package_name,
            path=project_root / "flutter",
            changelog="flutter/CHANGELOG.md",
            description=f"Flutter package for {names.root_package_name}"
        ),
        "rust": PackageInfo(
            name=names.rust_package_name,
            path=project_root / "dart" / "rust",
            changelog="dart/rust/CHANGELOG.md",
            description=f"Rust FFI bindings for {names.root_package_name}"
        )
    }
    
    # Try to get versions
    dart_pubspec = project_root / 'dart' / 'pubspec.yaml'
    if dart_pubspec.exists():
        version = extract_yaml_value(str(dart_pubspec), 'version')
        if version:
            packages["dart"].version = version
            packages["flutter"].version = version
            packages["root"].version = version
    
    rust_cargo = project_root / 'dart' / 'rust' / 'Cargo.toml'
    if rust_cargo.exists():
        version = extract_toml_value(str(rust_cargo), 'version')
        if version:
            packages["rust"].version = version
    
    return packages 