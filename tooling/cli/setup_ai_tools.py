#!/usr/bin/env python3
"""
setup_ai_tools.py - Complete setup for all tooling scripts

This script:
1. Installs gemini-cli for AI-powered features
2. Configures API key setup
3. Makes ALL tooling scripts executable
4. Provides overview of all available tools

Key features:
- Ultra-fast commits (2-3s) with smart_commit_fast.py
- AI-powered changelog generation with git attribution
- Complete release workflow automation

Requires: Python 3.6+

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import subprocess
import platform
import shutil
import stat
from pathlib import Path
from typing import List, Tuple, Optional

# ============================================================================
# CONSTANTS
# ============================================================================

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    NC = '\033[0m'  # No Color

def print_color(color: str, message: str):
    """Print colored message"""
    print(f"{color}{message}{Colors.NC}")

def print_header(title: str):
    """Print a formatted header"""
    print()
    print_color(Colors.PURPLE, "━" * 40)
    print_color(Colors.PURPLE, f"  {title}")
    print_color(Colors.PURPLE, "━" * 40)
    print()

# List of all tooling scripts
TOOLING_SCRIPTS = [
    # Python scripts
    "smart_commit_fast.py",
    "smart_commit.py",
    "sync_changelogs.py",
    "sync_changelog_ultra.py",
    "release.py",
    "prepare_new_patch.py",
    "push_new_patch.py",
    "retag_release.py",
    "open_pull_request_current_tagged_branch.py",
    "update_version.py",
    "get_new_patch_tag.py",
    "setup_permissions.py",
    "setup_ai_tools.py",
    "install_gemini_cli.py",
    "validate_changelogs.py",
    "pre_release_check.py",
    "analyze_changelog_history.py",
    "generate_release_notes.py",
    "common_config.py",
    # Test scripts (optional)
    "test_hang.py",
    "test_git_commands.py",
    "simple_changelog_test.py",
    # Legacy bash scripts if they still exist
    "smart_commit_fast.sh",
    "smart_commit.sh",
    "sync_changelogs.sh",
    "release.sh",
    "prepare_new_patch.sh",
    "push_new_patch.sh",
    "retag_release.sh",
    "update_version.sh",
    "get_new_patch_tag.sh",
    "setup_permissions.sh",
    "install_gemini_cli.sh",
    "common_config.sh",
    "validate_changelogs.sh",
    "pre_release_check.sh",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def run_command(cmd: List[str], capture_output: bool = True) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)"""
    try:
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        else:
            result = subprocess.run(cmd)
            return result.returncode, "", ""
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)

def command_exists(command: str) -> bool:
    """Check if a command exists in PATH"""
    return shutil.which(command) is not None

def get_project_root() -> Optional[Path]:
    """Find the project root directory"""
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    
    # Check if we're in the correct location
    dart_pubspec = project_root / "dart" / "pubspec.yaml"
    flutter_pubspec = project_root / "flutter" / "pubspec.yaml"
    
    if dart_pubspec.exists() and flutter_pubspec.exists():
        return project_root
    return None

def make_executable(file_path: Path) -> bool:
    """Make a file executable"""
    try:
        current_permissions = file_path.stat().st_mode
        new_permissions = current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        file_path.chmod(new_permissions)
        return True
    except Exception:
        return False

def get_go_bin_paths() -> List[str]:
    """Get potential Go bin paths"""
    paths = []
    home = Path.home()
    
    # Common Go bin locations
    paths.append(str(home / "go" / "bin"))
    paths.append(str(home / ".go" / "bin"))
    
    # Check GOPATH
    gopath = os.environ.get('GOPATH')
    if gopath:
        paths.append(os.path.join(gopath, 'bin'))
    
    return paths

def update_path_env():
    """Update PATH to include Go bin directories"""
    go_paths = get_go_bin_paths()
    current_path = os.environ.get('PATH', '')
    
    for path in go_paths:
        if os.path.exists(path) and path not in current_path:
            os.environ['PATH'] = f"{current_path}:{path}"

# ============================================================================
# INSTALLATION FUNCTIONS
# ============================================================================

def check_go_installation() -> bool:
    """Check if Go is installed"""
    if command_exists('go'):
        print_color(Colors.GREEN, "✓ Go is already installed")
        code, stdout, _ = run_command(['go', 'version'])
        if code == 0:
            print(f"  {stdout}")
        return True
    return False

def show_go_installation_instructions():
    """Show OS-specific Go installation instructions"""
    print_color(Colors.YELLOW, "Go is not installed.")
    
    system = platform.system().lower()
    
    print_color(Colors.BLUE, "\nInstallation options for Go:")
    print()
    
    if system == 'darwin':  # macOS
        print_color(Colors.BLUE, "On macOS, you can install Go using:")
        print()
        print("  1. Homebrew (recommended):")
        print_color(Colors.GREEN, "     brew install go")
        print()
        print("  2. MacPorts:")
        print_color(Colors.GREEN, "     sudo port install go")
        print()
        print("  3. Download installer from:")
        print_color(Colors.BLUE, "     https://go.dev/dl/")
        
        # Offer to install via Homebrew if available
        if command_exists('brew'):
            print()
            response = input(f"{Colors.YELLOW}Install Go via Homebrew now? (Y/n): {Colors.NC}")
            if not response.lower().startswith('n'):
                print("Installing Go via Homebrew...")
                code, _, stderr = run_command(['brew', 'install', 'go'], capture_output=False)
                if code == 0:
                    print_color(Colors.GREEN, "✓ Go installed successfully")
                    return True
                else:
                    print_color(Colors.RED, "Failed to install Go via Homebrew")
                    if stderr:
                        print(stderr)
                    
    elif system == 'linux':
        print_color(Colors.BLUE, "On Linux, you can install Go using:")
        print()
        print("  Package manager:")
        print()
        print("  • Ubuntu/Debian:")
        print_color(Colors.GREEN, "    sudo apt-get update && sudo apt-get install golang")
        print()
        print("  • Fedora:")
        print_color(Colors.GREEN, "    sudo dnf install golang")
        print()
        print("  • Arch:")
        print_color(Colors.GREEN, "    sudo pacman -S go")
        print()
        print("  • Download from:")
        print_color(Colors.BLUE, "    https://go.dev/dl/")
        
    else:  # Windows and others
        print_color(Colors.BLUE, "Please install Go from:")
        print_color(Colors.BLUE, "  https://go.dev/dl/")
    
    return False

def install_gemini_cli() -> bool:
    """Install gemini-cli using go install"""
    print_header("Installing gemini-cli")
    
    print_color(Colors.YELLOW, "Installing gemini-cli...")
    
    # Update PATH to include Go bin
    update_path_env()
    
    code, stdout, stderr = run_command(['go', 'install', 'github.com/eliben/gemini-cli@latest'])
    
    if code == 0:
        print_color(Colors.GREEN, "✓ gemini-cli installed")
        return True
    else:
        print_color(Colors.RED, "Failed to install gemini-cli")
        if stderr:
            print(f"Error: {stderr}")
        return False

def check_gemini_cli() -> bool:
    """Check if gemini-cli is installed and accessible"""
    # Update PATH first
    update_path_env()
    
    if command_exists('gemini-cli'):
        print_color(Colors.GREEN, "✓ gemini-cli is already installed")
        code, stdout, _ = run_command(['gemini-cli', '--version'])
        if code == 0:
            print(f"  {stdout}")
        else:
            print_color(Colors.YELLOW, "  (version check failed)")
        return True
    return False

def check_api_key():
    """Check if Gemini API key is configured"""
    api_key = os.environ.get('GEMINI_API_KEY')
    alt_key = os.environ.get('GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS')
    
    if not api_key and not alt_key:
        print_color(Colors.YELLOW, "No Gemini API key found.")
        print()
        print_color(Colors.BLUE, "To set up your API key:")
        print()
        print("1. Get your API key from:")
        print_color(Colors.BLUE, "   https://makersuite.google.com/app/apikey")
        print()
        print("2. Create a secure key file:")
        print_color(Colors.GREEN, "   mkdir -p ~/.secrets")
        print_color(Colors.GREEN, "   echo 'YOUR-API-KEY' > ~/.secrets/gemini_api_key")
        print_color(Colors.GREEN, "   chmod 600 ~/.secrets/gemini_api_key")
        print()
        print("3. Add to your shell config (~/.zshrc or ~/.bashrc):")
        print_color(Colors.GREEN, '   export GEMINI_API_KEY="$(cat ~/.secrets/gemini_api_key 2>/dev/null)"')
        print_color(Colors.GREEN, "   export PATH=$PATH:~/go/bin")
        print()
        print("4. Reload your shell:")
        print_color(Colors.GREEN, "   source ~/.zshrc")
        print()
        print_color(Colors.YELLOW, "Alternative: You can also use GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS")
    else:
        if alt_key and not api_key:
            print_color(Colors.YELLOW, "✓ Using GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS")
        else:
            print_color(Colors.GREEN, "✓ Gemini API key is already configured")

def make_scripts_executable(script_dir: Path):
    """Make all tooling scripts executable"""
    print_header("Setting Permissions")
    
    print_color(Colors.YELLOW, "Making all tooling scripts executable...")
    
    for script in TOOLING_SCRIPTS:
        script_path = script_dir / script
        if script_path.exists():
            if make_executable(script_path):
                print_color(Colors.GREEN, f"  ✓ {script}")
            else:
                print_color(Colors.RED, f"  ✗ {script} (failed to set permissions)")
        else:
            # Don't warn about missing files - we're transitioning from .sh to .py
            pass
    
    # Make this script itself executable
    this_script = script_dir / "setup_ai_tools.py"
    if this_script.exists():
        make_executable(this_script)
    
    # Also ensure common_config.py is executable (it's imported by other scripts)
    common_config = script_dir / "common_config.py"
    if common_config.exists():
        make_executable(common_config)

def show_available_tools():
    """Display information about available tools"""
    print_header("Setup Complete!")
    
    print_color(Colors.GREEN, "All tools are ready to use!")
    print()
    
    print_color(Colors.YELLOW, "🚀 AI-Powered Commit Tools:")
    print()
    print_color(Colors.GREEN, "  Fast Commit (NEW - Default):")
    print("    • ./tooling/smart_commit_fast.py         - Ultra-fast commits (2-3s with Flash)")
    print("    • ./tooling/smart_commit_fast.py --max   - Detailed analysis (15-20s with Pro)")
    print("    • ./tooling/smart_commit.py              - Original analyzer (30-50s, 11 AI calls)")
    print()
    
    print_color(Colors.YELLOW, "📋 Changelog & Release Tools:")
    print("    • ./tooling/sync_changelogs.py          - AI changelog generation with git attribution")
    print("    • ./tooling/sync_changelog_ultra.py      - Ultra-fast changelog sync (experimental)")
    print("    • ./tooling/analyze_changelog_history.py - Analyze changelog patterns and history")
    print("    • ./tooling/release.py                   - Full release workflow with AI assistance")
    print("    • ./tooling/prepare_new_patch.py         - Prepare a new patch version")
    print("    • ./tooling/push_new_patch.py            - Push and create GitHub release")
    print("    • ./tooling/retag_release.py             - Fix/update an existing release tag")
    print("    • ./tooling/open_pull_request_current_tagged_branch.py - Open PR for release branch")
    print()
    
    print_color(Colors.YELLOW, "✅ Validation Tools:")
    print("    • ./tooling/validate_changelogs.py       - Check all changelogs have entries")
    print("    • ./tooling/pre_release_check.py         - Comprehensive pre-release validation")
    print()
    
    print_color(Colors.YELLOW, "🔧 Utility Tools:")
    print("    • ./tooling/update_version.py            - Update version across all packages")
    print("    • ./tooling/get_new_patch_tag.py         - Calculate next patch version")
    print("    • ./tooling/setup_permissions.py         - Fix script permissions")
    print()
    
    print_color(Colors.PURPLE, "⚡ AI Model Information:")
    print("  • Default: gemini-2.5-flash-preview-05-20 (ultra-fast for daily use)")
    print("  • Max mode: gemini-2.5-pro-preview-05-06 (comprehensive analysis)")
    print()
    
    print_color(Colors.BLUE, "Next steps:")
    print("1. Set up your API key (if not already done)")
    print("2. Add PATH to your shell config: export PATH=$PATH:~/go/bin")
    print("3. Reload your terminal or run: source ~/.zshrc")
    print("4. Try the fast commit: ./tooling/smart_commit_fast.py")
    print()
    
    print_color(Colors.GREEN, "Tip: Most developers only need smart_commit_fast.py for daily work!")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main setup process"""
    print_header("Tooling Setup")
    
    # Check project root
    project_root = get_project_root()
    if not project_root:
        print_color(Colors.RED, "Error: Cannot find project root")
        print_color(Colors.YELLOW, "This script should be in the tooling/ directory of your project")
        sys.exit(1)
    
    script_dir = Path(__file__).parent.absolute()
    
    # Check if gemini-cli is already installed
    gemini_installed = check_gemini_cli()
    
    if not gemini_installed:
        # Check Go installation
        go_installed = check_go_installation()
        
        if not go_installed:
            show_go_installation_instructions()
            
            # Check again after potential installation
            if not check_go_installation():
                print_color(Colors.YELLOW, "\nAfter installing Go:")
                print_color(Colors.GREEN, "  1. Restart your terminal")
                print_color(Colors.GREEN, "  2. Run this script again: ./tooling/setup_ai_tools.py")
                sys.exit(1)
        
        # Install gemini-cli
        if not install_gemini_cli():
            sys.exit(1)
        
        # Verify installation
        update_path_env()
        if not command_exists('gemini-cli'):
            print_color(Colors.YELLOW, "gemini-cli installed but not in PATH")
            print_color(Colors.YELLOW, "Add this to your ~/.zshrc or ~/.bashrc:")
            print_color(Colors.BLUE, "export PATH=$PATH:~/go/bin")
        else:
            print_color(Colors.GREEN, "✓ gemini-cli is available")
    
    # Always show API key setup info
    print_header("API Key Setup")
    check_api_key()
    
    # Make scripts executable
    make_scripts_executable(script_dir)
    
    # Show available tools
    show_available_tools()

if __name__ == "__main__":
    main()