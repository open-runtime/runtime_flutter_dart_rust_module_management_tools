#!/usr/bin/env python3
"""
Unit tests for package name detection functionality
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.common_config import detect_package_names, get_package_info, Colors, print_color


class TestPackageDetection(unittest.TestCase):
    """Test cases for package name detection"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp(prefix="test_package_")
        self.original_cwd = os.getcwd()
        
    def tearDown(self):
        """Clean up test environment"""
        # Return to original directory
        os.chdir(self.original_cwd)
        # Remove temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def create_project_structure(self, project_name: str, 
                               dart_name: str = None,
                               flutter_name: str = None,
                               rust_name: str = None):
        """Create a test project structure with the given names"""
        # Create project directory
        project_dir = Path(self.test_dir) / project_name
        project_dir.mkdir(parents=True)
        
        # Default names if not provided
        if dart_name is None:
            dart_name = f"runtime_{project_name}"
        if flutter_name is None:
            flutter_name = f"runtime_flutter_{project_name}"
        if rust_name is None:
            rust_name = f"runtime_rust_{project_name}"
        
        # Create dart directory and pubspec.yaml
        dart_dir = project_dir / "dart"
        dart_dir.mkdir()
        dart_pubspec = dart_dir / "pubspec.yaml"
        dart_pubspec.write_text(f"""name: {dart_name}
version: 0.0.1
description: Test Dart package

environment:
  sdk: '>=2.12.0 <3.0.0'

dependencies:
  ffi: ^2.0.0
""")
        
        # Create flutter directory and pubspec.yaml
        flutter_dir = project_dir / "flutter"
        flutter_dir.mkdir()
        flutter_pubspec = flutter_dir / "pubspec.yaml"
        flutter_pubspec.write_text(f"""name: {flutter_name}
version: 0.0.1
description: Test Flutter package

environment:
  sdk: '>=2.12.0 <3.0.0'
  flutter: '>=2.0.0'

dependencies:
  flutter:
    sdk: flutter
  {dart_name}: ^0.0.1
""")
        
        # Create rust directory and Cargo.toml
        rust_dir = dart_dir / "rust"
        rust_dir.mkdir()
        rust_cargo = rust_dir / "Cargo.toml"
        rust_cargo.write_text(f"""[package]
name = "{rust_name}"
version = "0.0.1"
edition = "2021"

[dependencies]
""")
        
        return project_dir
    
    def test_standard_package_detection(self):
        """Test detection with standard naming convention"""
        project_name = "vector_search"
        project_dir = self.create_project_structure(project_name)
        
        # Change to project directory
        os.chdir(project_dir)
        
        # Detect package names
        names = detect_package_names()
        
        # Verify detected names
        self.assertEqual(names.root_package_name, project_name)
        self.assertEqual(names.dart_package_name, f"runtime_{project_name}")
        self.assertEqual(names.flutter_package_name, f"runtime_flutter_{project_name}")
        self.assertEqual(names.rust_package_name, f"runtime_rust_{project_name}")
        
        print_color(Colors.GREEN, f"✓ Standard naming convention test passed for '{project_name}'")
    
    def test_custom_package_names(self):
        """Test detection with custom package names"""
        project_name = "my_project"
        custom_dart = "my_dart_lib"
        custom_flutter = "my_flutter_app"
        custom_rust = "my_rust_ffi"
        
        project_dir = self.create_project_structure(
            project_name,
            dart_name=custom_dart,
            flutter_name=custom_flutter,
            rust_name=custom_rust
        )
        
        # Change to project directory
        os.chdir(project_dir)
        
        # Detect package names (should detect actual names from files)
        names = detect_package_names()
        
        # Verify detected names
        self.assertEqual(names.root_package_name, project_name)
        self.assertEqual(names.dart_package_name, custom_dart)
        self.assertEqual(names.flutter_package_name, custom_flutter)
        self.assertEqual(names.rust_package_name, custom_rust)
        
        print_color(Colors.GREEN, f"✓ Custom naming test passed for '{project_name}'")
    
    def test_missing_structure(self):
        """Test detection with missing directories/files"""
        project_name = "incomplete_project"
        project_dir = Path(self.test_dir) / project_name
        project_dir.mkdir()
        
        # Change to project directory
        os.chdir(project_dir)
        
        # This should raise SystemExit due to missing structure
        with self.assertRaises(SystemExit):
            detect_package_names()
        
        # But should work with skip_validation
        names = detect_package_names(skip_validation=True)
        self.assertEqual(names.root_package_name, project_name)
        self.assertEqual(names.dart_package_name, f"runtime_{project_name}")
        
        print_color(Colors.GREEN, "✓ Missing structure test passed")
    
    def test_package_info_generation(self):
        """Test get_package_info() function"""
        project_name = "test_info"
        project_dir = self.create_project_structure(project_name)
        
        # Change to project directory
        os.chdir(project_dir)
        
        # Get package info
        package_info = get_package_info()
        
        # Verify structure
        self.assertIn("root", package_info)
        self.assertIn("dart", package_info)
        self.assertIn("flutter", package_info)
        self.assertIn("rust", package_info)
        
        # Verify root package info
        root_info = package_info["root"]
        self.assertEqual(root_info["name"], project_name)
        self.assertEqual(root_info["changelog"], "CHANGELOG.md")
        self.assertIn("description", root_info)
        
        # Verify dart package info
        dart_info = package_info["dart"]
        self.assertEqual(dart_info["name"], f"runtime_{project_name}")
        self.assertEqual(dart_info["changelog"], "dart/CHANGELOG.md")
        
        print_color(Colors.GREEN, "✓ Package info generation test passed")
    
    def test_special_characters_in_name(self):
        """Test with special characters in project name"""
        # Test with hyphens (common in project names)
        project_name = "my-awesome-project"
        project_dir = self.create_project_structure(project_name)
        
        os.chdir(project_dir)
        names = detect_package_names()
        
        # Hyphens should be converted to underscores for package names
        expected_base = "my-awesome-project"  # Keep hyphens in root
        self.assertEqual(names.root_package_name, expected_base)
        self.assertEqual(names.dart_package_name, f"runtime_{expected_base}")
        
        print_color(Colors.GREEN, "✓ Special characters test passed")


def run_demo():
    """Run a demo showing package detection in action"""
    print_color(Colors.PURPLE, "\n" + "="*60)
    print_color(Colors.PURPLE, "Package Detection Demo")
    print_color(Colors.PURPLE, "="*60 + "\n")
    
    # Create a temporary demo project
    with tempfile.TemporaryDirectory(prefix="demo_") as temp_dir:
        project_name = "example_project"
        project_dir = Path(temp_dir) / project_name
        
        print_color(Colors.BLUE, f"Creating demo project: {project_name}")
        
        # Create structure
        project_dir.mkdir()
        
        # Create directories
        (project_dir / "dart").mkdir()
        (project_dir / "flutter").mkdir()
        (project_dir / "dart" / "rust").mkdir()
        
        # Create files
        (project_dir / "dart" / "pubspec.yaml").write_text(f"""name: runtime_{project_name}
version: 0.0.1
""")
        
        (project_dir / "flutter" / "pubspec.yaml").write_text(f"""name: runtime_flutter_{project_name}
version: 0.0.1
""")
        
        (project_dir / "dart" / "rust" / "Cargo.toml").write_text(f"""[package]
name = "runtime_rust_{project_name}"
version = "0.0.1"
""")
        
        # Change to project directory
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        try:
            # Detect names
            print_color(Colors.BLUE, "\nDetecting package names...")
            names = detect_package_names()
            
            print_color(Colors.GREEN, "\n✓ Package names detected:")
            print_color(Colors.GRAY, f"  Root:    {names.root_package_name}")
            print_color(Colors.GRAY, f"  Dart:    {names.dart_package_name}")
            print_color(Colors.GRAY, f"  Flutter: {names.flutter_package_name}")
            print_color(Colors.GRAY, f"  Rust:    {names.rust_package_name}")
            
            # Get package info
            print_color(Colors.BLUE, "\nGetting package configurations...")
            package_info = get_package_info()
            
            print_color(Colors.GREEN, "\n✓ Package configurations:")
            for key, info in package_info.items():
                print_color(Colors.BLUE, f"\n  {key}:")
                print_color(Colors.GRAY, f"    Name:        {info['name']}")
                print_color(Colors.GRAY, f"    Changelog:   {info['changelog']}")
                print_color(Colors.GRAY, f"    Description: {info['description']}")
                
        finally:
            os.chdir(original_cwd)
    
    print_color(Colors.PURPLE, "\n" + "="*60)


if __name__ == "__main__":
    # Check if running as demo or test
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        # Run unit tests
        print_color(Colors.PURPLE, "Running Package Detection Unit Tests")
        print_color(Colors.PURPLE, "="*50)
        print()
        
        # Run tests
        unittest.main(verbosity=2, exit=False)
        
        # Also run demo
        run_demo() 