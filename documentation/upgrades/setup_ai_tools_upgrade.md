# Upgrade Plan: setup_ai_tools.py

## Overview
Complete setup script for tooling environment including gemini-cli installation, API key configuration, and script permissions.

## Current State
- **Dependencies**: Standard library only
- **Key Features**: Cross-platform setup, API key management, executable permissions
- **Code Quality**: Comprehensive with good OS detection

## Recommended Upgrades

### 1. Package Management Integration
```python
# Enhanced package and dependency management
from typing import Dict, List, Optional, Tuple
import subprocess
import sys
from pathlib import Path
import pkg_resources
import platform

class DependencyManager:
    def __init__(self):
        self.required_packages = {
            # Core dependencies
            'gitpython': '>=3.1.0',
            'pyyaml': '>=6.0',
            'toml': '>=0.10.0',
            'click': '>=8.0.0',
            'rich': '>=10.0.0',
            
            # Optional but recommended
            'aiohttp': '>=3.8.0',
            'pydantic': '>=2.0.0',
            'python-dotenv': '>=1.0.0',
            'tenacity': '>=8.0.0'
        }
        
        self.system_requirements = {
            'git': self._check_git,
            'python': self._check_python_version,
            'pip': self._check_pip,
            'node': self._check_node  # For gemini-cli
        }
        
    def check_all_requirements(self) -> Tuple[bool, Dict[str, Any]]:
        """Check all system and package requirements"""
        results = {
            'system': {},
            'packages': {},
            'missing_system': [],
            'missing_packages': []
        }
        
        # Check system requirements
        for req, check_func in self.system_requirements.items():
            passed, version = check_func()
            results['system'][req] = {
                'installed': passed,
                'version': version
            }
            if not passed:
                results['missing_system'].append(req)
        
        # Check Python packages
        for package, version_spec in self.required_packages.items():
            try:
                pkg_resources.require(f"{package}{version_spec}")
                results['packages'][package] = {
                    'installed': True,
                    'version': pkg_resources.get_distribution(package).version
                }
            except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as e:
                results['packages'][package] = {
                    'installed': False,
                    'required': version_spec
                }
                results['missing_packages'].append(package)
        
        all_good = not (results['missing_system'] or results['missing_packages'])
        return all_good, results
    
    def install_missing_packages(
        self,
        packages: List[str],
        upgrade: bool = False
    ) -> Tuple[bool, List[str]]:
        """Install missing Python packages"""
        if not packages:
            return True, []
        
        cmd = [sys.executable, '-m', 'pip', 'install']
        if upgrade:
            cmd.append('--upgrade')
        
        # Add version specifications
        for package in packages:
            if package in self.required_packages:
                cmd.append(f"{package}{self.required_packages[package]}")
            else:
                cmd.append(package)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True, []
            else:
                failed = self._parse_failed_packages(result.stderr)
                return False, failed
        except Exception as e:
            return False, [str(e)]
    
    def _check_git(self) -> Tuple[bool, Optional[str]]:
        """Check git installation"""
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                version = result.stdout.strip().split()[-1]
                return True, version
        except FileNotFoundError:
            pass
        return False, None
    
    def _check_python_version(self) -> Tuple[bool, str]:
        """Check Python version meets requirements"""
        version = sys.version.split()[0]
        major, minor = sys.version_info[:2]
        
        # Require Python 3.8+
        if major >= 3 and minor >= 8:
            return True, version
        return False, version
    
    def _check_node(self) -> Tuple[bool, Optional[str]]:
        """Check Node.js installation"""
        try:
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
        except FileNotFoundError:
            pass
        return False, None
```

### 2. Configuration Management
```python
# Centralized configuration with validation
from pathlib import Path
import os
import json
from typing import Dict, Optional
from cryptography.fernet import Fernet
import keyring

class ToolingConfiguration:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / '.tesseract_tools'
        self.config_dir.mkdir(exist_ok=True)
        
        self.config_file = self.config_dir / 'config.json'
        self.secrets_file = self.config_dir / 'secrets.enc'
        
        self.config = self._load_config()
        self.cipher = self._setup_encryption()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return json.load(f)
        
        # Default configuration
        return {
            'version': '1.0.0',
            'gemini_cli_path': None,
            'api_keys': {},
            'features': {
                'ai_commit': True,
                'auto_changelog': True,
                'smart_release': True
            },
            'paths': {
                'tools_dir': str(Path(__file__).parent),
                'backup_dir': str(self.config_dir / 'backups'),
                'cache_dir': str(self.config_dir / 'cache')
            },
            'preferences': {
                'color_output': True,
                'verbose': False,
                'parallel_operations': True
            }
        }
    
    def _setup_encryption(self) -> Fernet:
        """Setup encryption for sensitive data"""
        key_file = self.config_dir / '.key'
        
        if key_file.exists():
            key = key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            # Restrict permissions
            key_file.chmod(0o600)
        
        return Fernet(key)
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_api_key(self, key_name: str = 'GEMINI_API_KEY') -> Optional[str]:
        """Get API key from various sources"""
        # 1. Environment variable
        if key_name in os.environ:
            return os.environ[key_name]
        
        # 2. System keyring (most secure)
        try:
            key = keyring.get_password('tesseract_tools', key_name)
            if key:
                return key
        except Exception:
            pass
        
        # 3. Encrypted file
        if self.secrets_file.exists():
            try:
                encrypted_data = self.secrets_file.read_bytes()
                decrypted = self.cipher.decrypt(encrypted_data)
                secrets = json.loads(decrypted)
                if key_name in secrets:
                    return secrets[key_name]
            except Exception:
                pass
        
        # 4. Config file (least secure, for backwards compatibility)
        return self.config.get('api_keys', {}).get(key_name)
    
    def save_api_key(self, key_name: str, key_value: str, secure: bool = True):
        """Save API key securely"""
        if secure:
            # Try system keyring first
            try:
                keyring.set_password('tesseract_tools', key_name, key_value)
                return
            except Exception:
                pass
            
            # Fall back to encrypted file
            secrets = {}
            if self.secrets_file.exists():
                try:
                    encrypted_data = self.secrets_file.read_bytes()
                    decrypted = self.cipher.decrypt(encrypted_data)
                    secrets = json.loads(decrypted)
                except Exception:
                    pass
            
            secrets[key_name] = key_value
            encrypted = self.cipher.encrypt(json.dumps(secrets).encode())
            self.secrets_file.write_bytes(encrypted)
            self.secrets_file.chmod(0o600)
        else:
            # Save to config file (backwards compatibility)
            self.config.setdefault('api_keys', {})[key_name] = key_value
            self.save_config()
```

### 3. Health Check System
```python
# Comprehensive health check and diagnostics
from typing import Dict, List, Tuple, Callable
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import asyncio

console = Console()

class ToolingHealthCheck:
    def __init__(self):
        self.checks = []
        self.results = {}
        self._register_checks()
        
    def _register_checks(self):
        """Register all health checks"""
        self.checks = [
            ('python_version', self._check_python_version, self._fix_python_version),
            ('git_installed', self._check_git, None),
            ('git_config', self._check_git_config, self._fix_git_config),
            ('node_installed', self._check_node, self._fix_node),
            ('gemini_cli', self._check_gemini_cli, self._fix_gemini_cli),
            ('api_keys', self._check_api_keys, self._fix_api_keys),
            ('permissions', self._check_permissions, self._fix_permissions),
            ('dependencies', self._check_dependencies, self._fix_dependencies),
            ('disk_space', self._check_disk_space, None),
            ('network', self._check_network, None)
        ]
    
    async def run_health_checks(self) -> Tuple[bool, Dict[str, Any]]:
        """Run all health checks with progress"""
        with Progress() as progress:
            task = progress.add_task("Running health checks...", total=len(self.checks))
            
            for check_name, check_func, fix_func in self.checks:
                try:
                    result = await self._run_check_async(check_func)
                    self.results[check_name] = {
                        'status': 'ok' if result else 'failed',
                        'can_fix': fix_func is not None,
                        'details': result
                    }
                except Exception as e:
                    self.results[check_name] = {
                        'status': 'error',
                        'error': str(e),
                        'can_fix': False
                    }
                
                progress.advance(task)
        
        # Display results
        self._display_results()
        
        all_ok = all(r['status'] == 'ok' for r in self.results.values())
        return all_ok, self.results
    
    async def _run_check_async(self, check_func: Callable) -> Any:
        """Run check function asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, check_func)
    
    def _display_results(self):
        """Display health check results in a table"""
        table = Table(title="Tooling Health Check Results")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Details")
        table.add_column("Fixable")
        
        for check_name, result in self.results.items():
            status = result['status']
            
            if status == 'ok':
                status_display = "[green]✓ OK[/green]"
            elif status == 'failed':
                status_display = "[red]✗ Failed[/red]"
            else:
                status_display = "[yellow]⚠ Error[/yellow]"
            
            details = result.get('error', result.get('details', ''))
            if isinstance(details, dict):
                details = ', '.join(f"{k}: {v}" for k, v in details.items())
            
            fixable = "Yes" if result.get('can_fix', False) else "No"
            
            table.add_row(
                check_name.replace('_', ' ').title(),
                status_display,
                str(details)[:50] + '...' if len(str(details)) > 50 else str(details),
                fixable
            )
        
        console.print(table)
    
    def fix_issues(self, issues: Optional[List[str]] = None) -> Dict[str, bool]:
        """Attempt to fix failed checks"""
        fixed = {}
        
        if issues is None:
            # Fix all fixable issues
            issues = [
                name for name, result in self.results.items()
                if result['status'] == 'failed' and result.get('can_fix', False)
            ]
        
        for issue in issues:
            # Find the fix function
            fix_func = None
            for check_name, _, fix in self.checks:
                if check_name == issue:
                    fix_func = fix
                    break
            
            if fix_func:
                try:
                    console.print(f"Fixing {issue}...")
                    success = fix_func()
                    fixed[issue] = success
                    
                    if success:
                        console.print(f"[green]✓ Fixed {issue}[/green]")
                    else:
                        console.print(f"[red]✗ Failed to fix {issue}[/red]")
                except Exception as e:
                    console.print(f"[red]Error fixing {issue}: {e}[/red]")
                    fixed[issue] = False
        
        return fixed
    
    def _check_gemini_cli(self) -> bool:
        """Check if gemini-cli is installed"""
        try:
            result = subprocess.run(
                ['gemini', '--version'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _fix_gemini_cli(self) -> bool:
        """Install gemini-cli"""
        try:
            # Check for npm/yarn
            npm_available = subprocess.run(
                ['npm', '--version'],
                capture_output=True
            ).returncode == 0
            
            if npm_available:
                result = subprocess.run(
                    ['npm', 'install', '-g', '@gemini/cli'],
                    capture_output=True
                )
                return result.returncode == 0
            
            return False
        except Exception:
            return False
```

### 4. Interactive Setup Wizard
```python
# Interactive setup with rich UI
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog, radiolist_dialog
import questionary
from rich.panel import Panel

class InteractiveSetupWizard:
    def __init__(self):
        self.config_manager = ToolingConfiguration()
        self.dep_manager = DependencyManager()
        self.health_checker = ToolingHealthCheck()
        
    async def run_setup(self):
        """Run interactive setup wizard"""
        console.clear()
        console.print(Panel.fit(
            "[bold blue]Tesseract Tooling Setup Wizard[/bold blue]\n"
            "This wizard will help you set up your development environment",
            border_style="blue"
        ))
        
        # Step 1: Check system requirements
        await self._check_requirements()
        
        # Step 2: Install dependencies
        await self._install_dependencies()
        
        # Step 3: Configure API keys
        await self._configure_api_keys()
        
        # Step 4: Setup features
        await self._setup_features()
        
        # Step 5: Make scripts executable
        await self._setup_permissions()
        
        # Step 6: Run health check
        await self._final_health_check()
        
        console.print("\n[green]✨ Setup complete![/green]")
    
    async def _check_requirements(self):
        """Check and display system requirements"""
        console.print("\n[yellow]Step 1: Checking system requirements...[/yellow]")
        
        all_good, results = self.dep_manager.check_all_requirements()
        
        if not all_good:
            console.print("\n[red]Missing requirements detected:[/red]")
            
            if results['missing_system']:
                console.print("\nMissing system tools:")
                for tool in results['missing_system']:
                    console.print(f"  - {tool}")
                
                if not questionary.confirm(
                    "Continue anyway? (Some features may not work)"
                ).ask():
                    raise SystemExit("Setup cancelled")
    
    async def _install_dependencies(self):
        """Install Python dependencies"""
        console.print("\n[yellow]Step 2: Installing Python dependencies...[/yellow]")
        
        _, results = self.dep_manager.check_all_requirements()
        
        if results['missing_packages']:
            choices = questionary.checkbox(
                "Select packages to install:",
                choices=[
                    questionary.Choice(
                        f"{pkg} {self.dep_manager.required_packages[pkg]}",
                        value=pkg
                    )
                    for pkg in results['missing_packages']
                ],
                default=results['missing_packages']
            ).ask()
            
            if choices:
                with console.status("Installing packages..."):
                    success, failed = self.dep_manager.install_missing_packages(choices)
                    
                if success:
                    console.print("[green]✓ All packages installed successfully[/green]")
                else:
                    console.print(f"[red]Failed to install: {', '.join(failed)}[/red]")
    
    async def _configure_api_keys(self):
        """Configure API keys"""
        console.print("\n[yellow]Step 3: Configuring API keys...[/yellow]")
        
        api_keys = {
            'GEMINI_API_KEY': 'Gemini API key for AI features',
            'GITHUB_TOKEN': 'GitHub token for release management (optional)',
            'OPENAI_API_KEY': 'OpenAI API key (optional alternative)'
        }
        
        for key_name, description in api_keys.items():
            current = self.config_manager.get_api_key(key_name)
            
            if current:
                if questionary.confirm(
                    f"{key_name} already configured. Update?"
                ).ask():
                    self._set_api_key(key_name, description)
            else:
                if questionary.confirm(
                    f"Configure {description}?"
                ).ask():
                    self._set_api_key(key_name, description)
    
    def _set_api_key(self, key_name: str, description: str):
        """Set a single API key"""
        key_value = questionary.password(
            f"Enter {description}:"
        ).ask()
        
        if key_value:
            secure = questionary.confirm(
                "Store securely in system keyring?"
            ).ask()
            
            self.config_manager.save_api_key(key_name, key_value, secure)
            console.print(f"[green]✓ {key_name} saved[/green]")
```

### 5. Platform-Specific Enhancements
```python
# Platform-specific setup improvements
import platform
import shutil
from typing import Dict, List, Optional

class PlatformSpecificSetup:
    def __init__(self):
        self.system = platform.system().lower()
        self.machine = platform.machine().lower()
        
        self.platform_handlers = {
            'darwin': self._setup_macos,
            'linux': self._setup_linux,
            'windows': self._setup_windows
        }
    
    def setup_platform_specific(self) -> Dict[str, Any]:
        """Run platform-specific setup"""
        handler = self.platform_handlers.get(self.system, self._setup_generic)
        return handler()
    
    def _setup_macos(self) -> Dict[str, Any]:
        """macOS-specific setup"""
        results = {
            'platform': 'macOS',
            'actions': []
        }
        
        # Check for Homebrew
        if shutil.which('brew'):
            results['homebrew'] = True
            
            # Install tools via Homebrew
            tools_to_install = []
            
            if not shutil.which('node'):
                tools_to_install.append('node')
            if not shutil.which('rg'):  # ripgrep
                tools_to_install.append('ripgrep')
            
            if tools_to_install:
                console.print(f"Installing tools via Homebrew: {', '.join(tools_to_install)}")
                for tool in tools_to_install:
                    subprocess.run(['brew', 'install', tool])
                    results['actions'].append(f"Installed {tool}")
        
        # Add to PATH if needed
        shell_config = Path.home() / '.zshrc'  # Default on modern macOS
        if not shell_config.exists():
            shell_config = Path.home() / '.bash_profile'
        
        self._update_shell_path(shell_config, results)
        
        return results
    
    def _setup_linux(self) -> Dict[str, Any]:
        """Linux-specific setup"""
        results = {
            'platform': 'Linux',
            'distribution': self._get_linux_distribution(),
            'actions': []
        }
        
        # Detect package manager
        if shutil.which('apt-get'):
            pkg_manager = 'apt'
        elif shutil.which('yum'):
            pkg_manager = 'yum'
        elif shutil.which('pacman'):
            pkg_manager = 'pacman'
        else:
            pkg_manager = None
        
        results['package_manager'] = pkg_manager
        
        # Install missing tools
        if pkg_manager == 'apt':
            missing_tools = []
            
            if not shutil.which('git'):
                missing_tools.append('git')
            if not shutil.which('python3-pip'):
                missing_tools.append('python3-pip')
            
            if missing_tools:
                subprocess.run(['sudo', 'apt-get', 'update'])
                subprocess.run(['sudo', 'apt-get', 'install', '-y'] + missing_tools)
                results['actions'].extend([f"Installed {tool}" for tool in missing_tools])
        
        # Update shell configuration
        shell_config = Path.home() / '.bashrc'
        self._update_shell_path(shell_config, results)
        
        return results
    
    def _setup_windows(self) -> Dict[str, Any]:
        """Windows-specific setup"""
        results = {
            'platform': 'Windows',
            'version': platform.version(),
            'actions': []
        }
        
        # Check for Windows Terminal
        if shutil.which('wt'):
            results['windows_terminal'] = True
        
        # Check for Git Bash
        git_bash = Path(r'C:\Program Files\Git\bin\bash.exe')
        if git_bash.exists():
            results['git_bash'] = True
        
        # Update PATH via PowerShell
        tools_dir = Path(__file__).parent
        
        ps_command = f'''
        $path = [Environment]::GetEnvironmentVariable("PATH", "User")
        if ($path -notlike "*{tools_dir}*") {{
            [Environment]::SetEnvironmentVariable("PATH", "$path;{tools_dir}", "User")
            Write-Host "Added {tools_dir} to PATH"
        }}
        '''
        
        try:
            subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True
            )
            results['actions'].append("Updated PATH environment variable")
        except Exception as e:
            results['path_error'] = str(e)
        
        return results
    
    def _get_linux_distribution(self) -> str:
        """Get Linux distribution name"""
        try:
            with open('/etc/os-release') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=')[1].strip().strip('"')
        except:
            pass
        return 'Unknown'
    
    def _update_shell_path(self, config_file: Path, results: Dict):
        """Update shell PATH configuration"""
        tools_dir = Path(__file__).parent
        
        if config_file.exists():
            content = config_file.read_text()
            
            path_export = f'export PATH="{tools_dir}:$PATH"'
            
            if path_export not in content:
                with open(config_file, 'a') as f:
                    f.write(f'\n# Added by Tesseract Tooling Setup\n')
                    f.write(f'{path_export}\n')
                
                results['actions'].append(f"Updated {config_file.name}")
```

### 6. Post-Setup Actions
```python
# Automated post-setup tasks
from typing import List, Dict
import webbrowser

class PostSetupActions:
    def __init__(self):
        self.actions = []
        
    def run_post_setup(self):
        """Run post-setup actions"""
        console.print("\n[yellow]Running post-setup actions...[/yellow]")
        
        # Create useful aliases
        self._create_aliases()
        
        # Generate quick reference
        self._generate_quick_reference()
        
        # Offer to run demo
        if questionary.confirm("Would you like to see a demo?").ask():
            self._run_demo()
        
        # Open documentation
        if questionary.confirm("Open documentation in browser?").ask():
            webbrowser.open("https://github.com/tesseract/tooling/wiki")
    
    def _create_aliases(self):
        """Create useful command aliases"""
        aliases = {
            'smart-commit': 'python smart_commit.py',
            'release': 'python release.py',
            'sync-changelog': 'python sync_changelogs.py',
            'patch': 'python prepare_new_patch.py && python push_new_patch.py'
        }
        
        # Create aliases script
        alias_script = Path('aliases.sh')
        with open(alias_script, 'w') as f:
            f.write('#!/bin/bash\n\n')
            f.write('# Tesseract Tooling Aliases\n')
            
            for alias, command in aliases.items():
                f.write(f'alias {alias}="{command}"\n')
        
        alias_script.chmod(0o755)
        
        console.print(f"\n[green]Created aliases script: {alias_script}[/green]")
        console.print("Add to your shell config: source aliases.sh")
    
    def _generate_quick_reference(self):
        """Generate quick reference card"""
        reference = """# Tesseract Tooling Quick Reference

## Common Commands

### Commits
- `smart-commit` - AI-powered commit messages
- `smart-commit --fast` - Quick mode (2-3s)

### Releases
- `release` - Interactive release workflow
- `prepare-new-patch` - Prepare patch release
- `push-new-patch` - Push prepared patch

### Changelogs
- `sync-changelogs` - Generate changelogs
- `validate-changelogs` - Check changelog format

### Version Management
- `update-version <version>` - Update all versions
- `get-new-patch-tag` - Get next patch version

## Tips
- Use `--help` on any command for options
- Set GEMINI_API_KEY for AI features
- Run in git repository root
"""
        
        ref_file = Path('QUICK_REFERENCE.md')
        ref_file.write_text(reference)
        
        console.print(f"\n[green]Created quick reference: {ref_file}[/green]")
```

## Dependencies to Add
```toml
[project.dependencies]
packaging = "^23.2"
questionary = "^2.0.1"
python-dotenv = "^1.0.0"
setuptools = "^69.0.0"
keyring = "^24.3.0"
cryptography = "^41.0.7"
rich = "^13.7.0"
prompt-toolkit = "^3.0.43"
aiofiles = "^23.2.1"
psutil = "^5.9.6"  # For system checks
```

## Migration Strategy
1. Add dependency management first
2. Implement secure configuration storage
3. Create health check system
4. Build interactive wizard
5. Add platform-specific enhancements

## Expected Benefits
- **Security**: Secure API key storage with encryption
- **Reliability**: Comprehensive health checks
- **User Experience**: Interactive setup wizard
- **Cross-Platform**: Platform-specific optimizations
- **Maintenance**: Self-healing capabilities