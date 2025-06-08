#!/usr/bin/env python3
"""
Setup script for building Runtime Tools binaries.

Supports building for macOS, Linux, and Windows.
"""
import os
import sys
import platform
import shutil
from pathlib import Path

# Platform-specific configurations
PLATFORM_CONFIGS = {
    'Darwin': {
        'name': 'macos',
        'binary_name': 'runtime_fdr_management_tools',
        'icon': None,  # Can add .icns file later
        'extra_args': ['--windowed=False']
    },
    'Linux': {
        'name': 'linux',
        'binary_name': 'runtime_fdr_management_tools',
        'icon': None,
        'extra_args': []
    },
    'Windows': {
        'name': 'windows',
        'binary_name': 'runtime_fdr_management_tools.exe',
        'icon': None,  # Can add .ico file later
        'extra_args': ['--console']
    }
}


def create_spec_file():
    """Create PyInstaller spec file with all dependencies"""
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# Get the root directory
ROOT_DIR = Path(os.path.abspath(SPECPATH)).parent

# Add tooling to path
sys.path.insert(0, str(ROOT_DIR))

a = Analysis(
    ['runtime_fdr_management_tools.py'],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        # Include configuration files
        ('.rtconfig.yaml', '.'),
        # Include any templates or data files
        ('cli/templates', 'tooling/cli/templates'),
    ],
    hiddenimports=[
        # Core imports
        'tooling.core.imports',
        'tooling.core.config_manager',
        'tooling.core.plugin_system',
        'tooling.core.logging',
        'tooling.core.ai_operations',
        'tooling.core.performance',
        
        # CLI tools
        'tooling.cli.cli_tools_base',
        'tooling.cli.cli_utils',
        'tooling.cli.interactive_mode',
        'tooling.cli.commit_tools',
        'tooling.cli.release_tools',
        'tooling.cli.pr_tools',
        'tooling.cli.version_tools',
        'tooling.cli.setup_tools',
        'tooling.cli.changelog_tools',
        'tooling.cli.contributor_analyzer',
        
        # Utils
        'tooling.utils.git_utils',
        'tooling.utils.file_utils',
        'tooling.utils.prompts',
        'tooling.utils.async_file_utils',
        'tooling.utils.async_git_utils',
        
        # External packages
        'click',
        'rich',
        'rich.console',
        'rich.table',
        'rich.panel',
        'rich.progress',
        'rich.prompt',
        'rich.syntax',
        'prompt_toolkit',
        'questionary',
        'pydantic',
        'yaml',
        'git',
        'aiofiles',
        'aiohttp',
        'httpx',
        'tenacity',
        'structlog',
        
        # Platform-specific
        'colorama',  # Windows color support
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{binary_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {extra_args}
)
"""
    return spec_content


def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        os.system(f"{sys.executable} -m pip install pyinstaller")


def build_binary():
    """Build the binary for the current platform"""
    system = platform.system()
    if system not in PLATFORM_CONFIGS:
        print(f"Unsupported platform: {system}")
        return False
    
    config = PLATFORM_CONFIGS[system]
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Create spec file
    spec_content = create_spec_file()
    spec_content = spec_content.format(
        binary_name=config['binary_name'],
        extra_args=', '.join(f'"{arg}"' for arg in config['extra_args'])
    )
    
    # Write spec file
    spec_path = Path('runtime_fdr_management_tools.spec')
    with open(spec_path, 'w') as f:
        f.write(spec_content)
    
    # Change to tooling directory
    os.chdir('tooling')
    
    # Build with PyInstaller
    print(f"Building for {config['name']}...")
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--onefile',
        f'--name={config["binary_name"].replace(".exe", "")}',
    ]
    
    if config['icon']:
        cmd.append(f'--icon={config["icon"]}')
    
    cmd.extend(config['extra_args'])
    cmd.append('runtime_fdr_management_tools.spec')
    
    result = os.system(' '.join(cmd))
    
    if result == 0:
        # Move binary to root
        dist_path = Path('dist') / config['binary_name']
        if dist_path.exists():
            target_path = Path('..') / config['binary_name']
            shutil.move(str(dist_path), str(target_path))
            print(f"✓ Binary created: {target_path}")
            
            # Make executable on Unix
            if system in ['Darwin', 'Linux']:
                os.chmod(str(target_path), 0o755)
            
            return True
    
    return False


def create_platform_script():
    """Create platform-specific wrapper scripts"""
    # Windows batch file
    batch_content = """@echo off
python "%~dp0\\tooling\\runtime_fdr_management_tools.py" %*
"""
    
    # Unix shell script
    shell_content = """#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
python3 "$DIR/tooling/runtime_fdr_management_tools.py" "$@"
"""
    
    # PowerShell script
    ps_content = """$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
& python "$scriptPath\\tooling\\runtime_fdr_management_tools.py" $args
"""
    
    # Create scripts
    if platform.system() == 'Windows':
        with open('runtime_fdr_management_tools.bat', 'w') as f:
            f.write(batch_content)
        with open('runtime_fdr_management_tools.ps1', 'w') as f:
            f.write(ps_content)
        print("✓ Created runtime_fdr_management_tools.bat and runtime_fdr_management_tools.ps1")
    else:
        with open('runtime_fdr_management_tools', 'w') as f:
            f.write(shell_content)
        os.chmod('runtime_fdr_management_tools', 0o755)
        print("✓ Created runtime_fdr_management_tools shell script")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build Runtime Tools binary")
    parser.add_argument(
        '--script-only',
        action='store_true',
        help='Only create wrapper scripts, don\'t build binary'
    )
    parser.add_argument(
        '--all-platforms',
        action='store_true',
        help='Build for all platforms (requires cross-compilation setup)'
    )
    
    args = parser.parse_args()
    
    if args.script_only:
        create_platform_script()
    else:
        if build_binary():
            print("\n✓ Build successful!")
            print("\nTo distribute:")
            print("1. Test the binary thoroughly")
            print("2. Sign it (macOS/Windows)")
            print("3. Create installer or package")
        else:
            print("\n✗ Build failed!")
            print("\nTroubleshooting:")
            print("1. Check PyInstaller logs")
            print("2. Ensure all dependencies are installed")
            print("3. Try building with --script-only first")


if __name__ == '__main__':
    main() 