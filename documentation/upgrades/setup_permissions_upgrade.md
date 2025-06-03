# Upgrade Plan: setup_permissions.py

## Overview
Sets executable permissions for all tooling scripts and handles both .sh and .py versions. Currently a simple focused utility.

## Current State
- **Dependencies**: Standard library only
- **Key Features**: Cross-platform permission setting, script discovery
- **Code Quality**: Simple and effective

## Recommended Upgrades

### 1. Enhanced Permission Management
```python
# Comprehensive permission management system
import stat
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import os
import platform

class PermissionManager:
    def __init__(self, base_dir: Path = Path('.')):
        self.base_dir = base_dir
        self.platform = platform.system().lower()
        
        # Define permission sets
        self.permission_sets = {
            'executable': stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                         stat.S_IRGRP | stat.S_IXGRP | \
                         stat.S_IROTH | stat.S_IXOTH,  # 755
            'script': stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                     stat.S_IRGRP | stat.S_IXGRP,  # 750
            'secure': stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR,  # 700
            'readonly': stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,  # 444
            'config': stat.S_IRUSR | stat.S_IWUSR | \
                     stat.S_IRGRP,  # 640
        }
        
    def scan_scripts(self) -> Dict[str, List[Path]]:
        """Scan for all scripts organized by type"""
        scripts = {
            'python': [],
            'shell': [],
            'node': [],
            'other': []
        }
        
        # Define patterns
        patterns = {
            'python': ['*.py'],
            'shell': ['*.sh', '*.bash'],
            'node': ['*.js', '*.mjs'],
        }
        
        for script_type, globs in patterns.items():
            for pattern in globs:
                for file in self.base_dir.rglob(pattern):
                    if self._should_process_file(file):
                        scripts[script_type].append(file)
        
        # Find scripts without extensions (check shebang)
        for file in self.base_dir.iterdir():
            if file.is_file() and not file.suffix:
                script_type = self._detect_script_type(file)
                if script_type:
                    scripts[script_type].append(file)
        
        return scripts
    
    def _should_process_file(self, file: Path) -> bool:
        """Check if file should be processed"""
        # Skip certain directories
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'venv'}
        
        for parent in file.parents:
            if parent.name in skip_dirs:
                return False
        
        # Skip certain files
        skip_patterns = ['test_', '_test.', '.test.']
        return not any(pattern in file.name for pattern in skip_patterns)
    
    def _detect_script_type(self, file: Path) -> Optional[str]:
        """Detect script type from shebang"""
        try:
            with open(file, 'rb') as f:
                first_line = f.readline().decode('utf-8', errors='ignore')
                
            if first_line.startswith('#!'):
                shebang = first_line.strip()
                
                if 'python' in shebang:
                    return 'python'
                elif 'bash' in shebang or 'sh' in shebang:
                    return 'shell'
                elif 'node' in shebang:
                    return 'node'
                
        except Exception:
            pass
        
        return None
    
    def check_permissions(self, file: Path) -> Dict[str, bool]:
        """Check detailed permissions for a file"""
        try:
            st = file.stat()
            mode = st.st_mode
            
            return {
                'owner_read': bool(mode & stat.S_IRUSR),
                'owner_write': bool(mode & stat.S_IWUSR),
                'owner_execute': bool(mode & stat.S_IXUSR),
                'group_read': bool(mode & stat.S_IRGRP),
                'group_write': bool(mode & stat.S_IWGRP),
                'group_execute': bool(mode & stat.S_IXGRP),
                'other_read': bool(mode & stat.S_IROTH),
                'other_write': bool(mode & stat.S_IWOTH),
                'other_execute': bool(mode & stat.S_IXOTH),
                'is_setuid': bool(mode & stat.S_ISUID),
                'is_setgid': bool(mode & stat.S_ISGID),
                'is_sticky': bool(mode & stat.S_ISVTX),
                'octal': oct(stat.S_IMODE(mode))[2:],
                'symbolic': self._mode_to_symbolic(mode)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _mode_to_symbolic(self, mode: int) -> str:
        """Convert numeric mode to symbolic representation"""
        perms = ['---', '---', '---']
        
        # Owner permissions
        if mode & stat.S_IRUSR: perms[0] = 'r' + perms[0][1:]
        if mode & stat.S_IWUSR: perms[0] = perms[0][0] + 'w' + perms[0][2]
        if mode & stat.S_IXUSR: perms[0] = perms[0][:2] + 'x'
        
        # Group permissions
        if mode & stat.S_IRGRP: perms[1] = 'r' + perms[1][1:]
        if mode & stat.S_IWGRP: perms[1] = perms[1][0] + 'w' + perms[1][2]
        if mode & stat.S_IXGRP: perms[1] = perms[1][:2] + 'x'
        
        # Other permissions
        if mode & stat.S_IROTH: perms[2] = 'r' + perms[2][1:]
        if mode & stat.S_IWOTH: perms[2] = perms[2][0] + 'w' + perms[2][2]
        if mode & stat.S_IXOTH: perms[2] = perms[2][:2] + 'x'
        
        return ''.join(perms)
    
    def set_permissions(
        self,
        file: Path,
        permission_set: str = 'script',
        custom_mode: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """Set permissions on a file"""
        try:
            if custom_mode:
                mode = custom_mode
            else:
                mode = self.permission_sets.get(permission_set, self.permission_sets['script'])
            
            file.chmod(mode)
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    def batch_set_permissions(
        self,
        files: List[Path],
        permission_set: str = 'script',
        progress_callback: Optional[callable] = None
    ) -> Dict[Path, Tuple[bool, Optional[str]]]:
        """Set permissions on multiple files"""
        results = {}
        
        for i, file in enumerate(files):
            success, error = self.set_permissions(file, permission_set)
            results[file] = (success, error)
            
            if progress_callback:
                progress_callback(i + 1, len(files), file)
        
        return results
```

### 2. Shebang Management
```python
# Shebang verification and fixing
import re
from typing import Tuple, Optional, List

class ShebangManager:
    def __init__(self):
        self.standard_shebangs = {
            'python': '#!/usr/bin/env python3',
            'python2': '#!/usr/bin/env python2',
            'shell': '#!/usr/bin/env bash',
            'sh': '#!/bin/sh',
            'node': '#!/usr/bin/env node',
            'ruby': '#!/usr/bin/env ruby',
            'perl': '#!/usr/bin/env perl'
        }
        
        self.shebang_patterns = [
            (re.compile(r'^#!\s*/usr/bin/env\s+python3?'), 'python'),
            (re.compile(r'^#!\s*/usr/bin/python3?'), 'python'),
            (re.compile(r'^#!\s*/usr/bin/env\s+bash'), 'shell'),
            (re.compile(r'^#!\s*/bin/bash'), 'shell'),
            (re.compile(r'^#!\s*/bin/sh'), 'sh'),
            (re.compile(r'^#!\s*/usr/bin/env\s+node'), 'node'),
        ]
    
    def check_shebang(self, file: Path) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if file has valid shebang"""
        try:
            with open(file, 'rb') as f:
                first_bytes = f.read(2)
                
                # Check for shebang
                if first_bytes != b'#!':
                    return False, None, "No shebang found"
                
                # Read full first line
                f.seek(0)
                first_line = f.readline().decode('utf-8', errors='ignore').strip()
            
            # Validate shebang
            for pattern, script_type in self.shebang_patterns:
                if pattern.match(first_line):
                    return True, script_type, first_line
            
            return False, None, f"Invalid shebang: {first_line}"
            
        except Exception as e:
            return False, None, f"Error reading file: {str(e)}"
    
    def fix_shebang(
        self,
        file: Path,
        script_type: Optional[str] = None,
        custom_shebang: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Add or fix shebang in file"""
        try:
            # Read file content
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Determine shebang to use
            if custom_shebang:
                shebang = custom_shebang
            elif script_type:
                shebang = self.standard_shebangs.get(script_type, '#!/usr/bin/env bash')
            else:
                # Try to detect from file extension
                if file.suffix == '.py':
                    shebang = self.standard_shebangs['python']
                elif file.suffix in ['.sh', '.bash']:
                    shebang = self.standard_shebangs['shell']
                elif file.suffix == '.js':
                    shebang = self.standard_shebangs['node']
                else:
                    shebang = '#!/usr/bin/env bash'
            
            # Remove existing shebang if present
            lines = content.split('\n')
            if lines and lines[0].startswith('#!'):
                lines = lines[1:]
            
            # Add new shebang
            new_content = shebang + '\n' + '\n'.join(lines)
            
            # Write back
            with open(file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True, shebang
            
        except Exception as e:
            return False, str(e)
    
    def validate_interpreter(self, shebang: str) -> Tuple[bool, Optional[str]]:
        """Validate that interpreter in shebang exists"""
        import shutil
        
        # Extract interpreter path
        parts = shebang.strip().split()
        
        if len(parts) < 1:
            return False, "Invalid shebang format"
        
        if parts[0] == '#!/usr/bin/env' and len(parts) > 1:
            # env style - check if command exists
            command = parts[1]
            if shutil.which(command):
                return True, None
            else:
                return False, f"Command not found: {command}"
        else:
            # Direct path
            interpreter = parts[0][2:]  # Remove #!
            if Path(interpreter).exists():
                return True, None
            else:
                return False, f"Interpreter not found: {interpreter}"
```

### 3. Security Audit
```python
# Security audit for permissions
from typing import List, Dict, Tuple
import pwd
import grp
from datetime import datetime

class PermissionSecurityAudit:
    def __init__(self):
        self.security_risks = {
            'world_writable': self._check_world_writable,
            'setuid_setgid': self._check_setuid_setgid,
            'excessive_permissions': self._check_excessive_permissions,
            'ownership_issues': self._check_ownership_issues,
            'sensitive_files': self._check_sensitive_files
        }
        
    def audit_directory(self, directory: Path) -> Dict[str, List[Dict]]:
        """Perform security audit on directory"""
        issues = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'info': []
        }
        
        # Scan all files
        for file in directory.rglob('*'):
            if file.is_file():
                file_issues = self._audit_file(file)
                
                for severity, issue_list in file_issues.items():
                    issues[severity].extend(issue_list)
        
        return issues
    
    def _audit_file(self, file: Path) -> Dict[str, List[Dict]]:
        """Audit individual file"""
        issues = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'info': []
        }
        
        try:
            st = file.stat()
            mode = st.st_mode
            
            # Run all security checks
            for risk_name, check_func in self.security_risks.items():
                severity, issue = check_func(file, st, mode)
                
                if issue:
                    issues[severity].append({
                        'file': str(file),
                        'risk': risk_name,
                        'details': issue,
                        'timestamp': datetime.now().isoformat()
                    })
            
        except Exception as e:
            issues['info'].append({
                'file': str(file),
                'risk': 'access_error',
                'details': str(e)
            })
        
        return issues
    
    def _check_world_writable(
        self,
        file: Path,
        st: os.stat_result,
        mode: int
    ) -> Tuple[str, Optional[str]]:
        """Check for world-writable files"""
        if mode & stat.S_IWOTH:
            return 'high', "File is world-writable"
        return '', None
    
    def _check_setuid_setgid(
        self,
        file: Path,
        st: os.stat_result,
        mode: int
    ) -> Tuple[str, Optional[str]]:
        """Check for setuid/setgid bits"""
        if mode & stat.S_ISUID:
            return 'critical', "File has setuid bit set"
        if mode & stat.S_ISGID:
            return 'high', "File has setgid bit set"
        return '', None
    
    def _check_excessive_permissions(
        self,
        file: Path,
        st: os.stat_result,
        mode: int
    ) -> Tuple[str, Optional[str]]:
        """Check for excessive permissions"""
        # Check if non-script has execute permissions
        if file.suffix not in ['.py', '.sh', '.bash', '.js', '']:
            if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                return 'medium', f"Non-script file has execute permissions"
        
        # Check if config files are too permissive
        if file.suffix in ['.json', '.yaml', '.yml', '.toml', '.env']:
            if mode & (stat.S_IWGRP | stat.S_IWOTH):
                return 'high', "Configuration file is group/world writable"
            if mode & (stat.S_IROTH):
                return 'medium', "Configuration file is world readable"
        
        return '', None
    
    def _check_sensitive_files(
        self,
        file: Path,
        st: os.stat_result,
        mode: int
    ) -> Tuple[str, Optional[str]]:
        """Check permissions on sensitive files"""
        sensitive_patterns = [
            '.env', 'secrets', 'credentials', 'token', 'key', 'password'
        ]
        
        file_lower = file.name.lower()
        
        for pattern in sensitive_patterns:
            if pattern in file_lower:
                # Should be readable only by owner
                if mode & (stat.S_IRGRP | stat.S_IROTH):
                    return 'high', f"Sensitive file is readable by group/others"
                if mode & (stat.S_IWGRP | stat.S_IWOTH):
                    return 'critical', f"Sensitive file is writable by group/others"
        
        return '', None
    
    def generate_audit_report(
        self,
        issues: Dict[str, List[Dict]]
    ) -> str:
        """Generate human-readable audit report"""
        from rich.console import Console
        from rich.table import Table
        from io import StringIO
        
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        
        # Summary
        total_issues = sum(len(issue_list) for issue_list in issues.values())
        
        console.print(f"\n[bold]Permission Security Audit Report[/bold]")
        console.print(f"Total issues found: {total_issues}\n")
        
        # Issues by severity
        for severity in ['critical', 'high', 'medium', 'low', 'info']:
            if issues[severity]:
                color = {
                    'critical': 'red',
                    'high': 'orange1',
                    'medium': 'yellow',
                    'low': 'blue',
                    'info': 'green'
                }[severity]
                
                console.print(f"[{color}]■ {severity.upper()} ({len(issues[severity])} issues)[/{color}]")
                
                table = Table(show_header=True, header_style="bold")
                table.add_column("File", style="cyan", width=40)
                table.add_column("Risk", style="magenta")
                table.add_column("Details", style="white")
                
                for issue in issues[severity][:10]:  # Show first 10
                    file_path = Path(issue['file']).name
                    table.add_row(
                        file_path,
                        issue['risk'].replace('_', ' ').title(),
                        issue['details']
                    )
                
                if len(issues[severity]) > 10:
                    table.add_row(
                        "...",
                        f"And {len(issues[severity]) - 10} more",
                        ""
                    )
                
                console.print(table)
                console.print()
        
        return buffer.getvalue()
```

### 4. Batch Operations with Progress
```python
# Enhanced batch operations with rich progress
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.console import Console
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any

console = Console()

class BatchPermissionOperations:
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.permission_manager = PermissionManager()
        self.shebang_manager = ShebangManager()
        
    def batch_fix_permissions(
        self,
        files: List[Path],
        permission_set: str = 'script',
        fix_shebangs: bool = True,
        parallel: bool = True
    ) -> Dict[str, Any]:
        """Fix permissions and shebangs for multiple files"""
        
        results = {
            'total': len(files),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': {}
        }
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task(
                "Setting permissions...",
                total=len(files)
            )
            
            if parallel and len(files) > 10:
                # Parallel processing for large batches
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(
                            self._process_file,
                            file,
                            permission_set,
                            fix_shebangs
                        ): file
                        for file in files
                    }
                    
                    for future in as_completed(futures):
                        file = futures[future]
                        try:
                            result = future.result()
                            results['details'][str(file)] = result
                            
                            if result['success']:
                                results['success'] += 1
                            else:
                                results['failed'] += 1
                                
                        except Exception as e:
                            results['details'][str(file)] = {
                                'success': False,
                                'error': str(e)
                            }
                            results['failed'] += 1
                        
                        progress.advance(task)
            else:
                # Sequential processing for small batches
                for file in files:
                    result = self._process_file(file, permission_set, fix_shebangs)
                    results['details'][str(file)] = result
                    
                    if result['success']:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                    
                    progress.advance(task)
        
        return results
    
    def _process_file(
        self,
        file: Path,
        permission_set: str,
        fix_shebangs: bool
    ) -> Dict[str, Any]:
        """Process single file"""
        result = {
            'file': str(file),
            'success': True,
            'actions': []
        }
        
        try:
            # Fix shebang if requested
            if fix_shebangs and file.suffix in ['.py', '.sh', '.bash', '.js', '']:
                has_shebang, script_type, current = self.shebang_manager.check_shebang(file)
                
                if not has_shebang or script_type is None:
                    success, shebang = self.shebang_manager.fix_shebang(file)
                    if success:
                        result['actions'].append(f"Added shebang: {shebang}")
                    else:
                        result['actions'].append(f"Failed to add shebang: {shebang}")
            
            # Set permissions
            success, error = self.permission_manager.set_permissions(file, permission_set)
            
            if success:
                result['actions'].append(f"Set permissions to {permission_set}")
            else:
                result['success'] = False
                result['error'] = error
                
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
        
        return result
```

### 5. Interactive Permission Management
```python
# Interactive CLI for permission management
import click
from rich.prompt import Prompt, Confirm
from rich.table import Table
import questionary

@click.command()
@click.option('--directory', '-d', default='.', help='Directory to process')
@click.option('--audit', is_flag=True, help='Run security audit')
@click.option('--fix', is_flag=True, help='Fix permissions automatically')
@click.option('--interactive', '-i', is_flag=True, help='Interactive mode')
@click.option('--permission-set', '-p', default='script', help='Permission set to apply')
def manage_permissions(directory, audit, fix, interactive, permission_set):
    """Manage file permissions for tooling scripts"""
    
    manager = PermissionManager(Path(directory))
    console = Console()
    
    # Scan for scripts
    scripts = manager.scan_scripts()
    
    # Display summary
    table = Table(title="Script Summary")
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Example Files")
    
    for script_type, files in scripts.items():
        if files:
            examples = ', '.join(f.name for f in files[:3])
            if len(files) > 3:
                examples += f" ... +{len(files) - 3} more"
            
            table.add_row(script_type.title(), str(len(files)), examples)
    
    console.print(table)
    
    # Run audit if requested
    if audit:
        auditor = PermissionSecurityAudit()
        issues = auditor.audit_directory(Path(directory))
        
        report = auditor.generate_audit_report(issues)
        console.print(report)
        
        if issues['critical'] or issues['high']:
            if Confirm.ask("Fix critical/high issues?"):
                fix = True
    
    # Interactive mode
    if interactive:
        choices = []
        
        for script_type, files in scripts.items():
            if files:
                choices.extend([
                    questionary.Choice(
                        f"{f.relative_to(Path(directory))} ({script_type})",
                        value=f
                    )
                    for f in files
                ])
        
        selected = questionary.checkbox(
            "Select files to process:",
            choices=choices
        ).ask()
        
        if selected:
            # Ask for permission set
            perm_choice = questionary.select(
                "Select permission set:",
                choices=[
                    questionary.Choice("Script (750)", value="script"),
                    questionary.Choice("Executable (755)", value="executable"),
                    questionary.Choice("Secure (700)", value="secure"),
                    questionary.Choice("Custom", value="custom")
                ]
            ).ask()
            
            if perm_choice == "custom":
                custom = Prompt.ask("Enter octal permissions (e.g., 644)")
                permission_set = int(custom, 8)
            else:
                permission_set = perm_choice
            
            # Process selected files
            batch_ops = BatchPermissionOperations()
            results = batch_ops.batch_fix_permissions(
                selected,
                permission_set,
                fix_shebangs=True
            )
            
            # Display results
            console.print(f"\n[green]✓ Processed {results['success']} files successfully[/green]")
            if results['failed']:
                console.print(f"[red]✗ Failed to process {results['failed']} files[/red]")
    
    elif fix:
        # Fix all scripts automatically
        all_files = []
        for files in scripts.values():
            all_files.extend(files)
        
        if all_files:
            batch_ops = BatchPermissionOperations()
            results = batch_ops.batch_fix_permissions(
                all_files,
                permission_set,
                fix_shebangs=True
            )
            
            console.print(f"\n[green]✓ Fixed permissions for {results['success']} files[/green]")
```

### 6. Cross-Platform Support
```python
# Platform-specific permission handling
import platform
from typing import Dict, Any

class CrossPlatformPermissions:
    def __init__(self):
        self.system = platform.system().lower()
        
        self.handlers = {
            'windows': self._handle_windows,
            'darwin': self._handle_unix,
            'linux': self._handle_unix
        }
    
    def make_executable(self, file: Path) -> Tuple[bool, Optional[str]]:
        """Make file executable on current platform"""
        handler = self.handlers.get(self.system, self._handle_unix)
        return handler(file)
    
    def _handle_windows(self, file: Path) -> Tuple[bool, Optional[str]]:
        """Handle Windows permissions"""
        # Windows doesn't have traditional Unix permissions
        # But we can set file attributes
        import win32api
        import win32con
        
        try:
            # Remove read-only attribute if set
            attrs = win32api.GetFileAttributes(str(file))
            if attrs & win32con.FILE_ATTRIBUTE_READONLY:
                win32api.SetFileAttributes(
                    str(file),
                    attrs & ~win32con.FILE_ATTRIBUTE_READONLY
                )
            
            # For Python/shell scripts, associate with interpreter
            if file.suffix == '.py':
                # Ensure .py files are associated with Python
                import winreg
                
                try:
                    key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, '.py')
                    winreg.SetValue(key, '', winreg.REG_SZ, 'Python.File')
                    winreg.CloseKey(key)
                except:
                    pass
            
            return True, None
            
        except Exception as e:
            return False, f"Windows permission error: {str(e)}"
    
    def _handle_unix(self, file: Path) -> Tuple[bool, Optional[str]]:
        """Handle Unix-like permissions"""
        try:
            # Get current permissions
            current = file.stat().st_mode
            
            # Add execute permission for owner, group
            new_mode = current | stat.S_IXUSR | stat.S_IXGRP
            
            file.chmod(new_mode)
            return True, None
            
        except Exception as e:
            return False, f"Unix permission error: {str(e)}"
    
    def get_permission_display(self, file: Path) -> str:
        """Get platform-appropriate permission display"""
        if self.system == 'windows':
            import win32api
            import win32con
            
            try:
                attrs = win32api.GetFileAttributes(str(file))
                
                flags = []
                if attrs & win32con.FILE_ATTRIBUTE_READONLY:
                    flags.append('READONLY')
                if attrs & win32con.FILE_ATTRIBUTE_HIDDEN:
                    flags.append('HIDDEN')
                if attrs & win32con.FILE_ATTRIBUTE_SYSTEM:
                    flags.append('SYSTEM')
                
                return ' '.join(flags) if flags else 'NORMAL'
                
            except:
                return 'UNKNOWN'
        else:
            # Unix-like systems
            try:
                mode = file.stat().st_mode
                return oct(stat.S_IMODE(mode))[2:]
            except:
                return 'UNKNOWN'
```

## Dependencies to Add
```toml
[project.dependencies]
rich = "^13.7.0"
click = "^8.1.7"
questionary = "^2.0.1"
psutil = "^5.9.6"
tabulate = "^0.9.0"

# Platform-specific
pywin32 = { version = "^306", platform = "win32" }
```

## Migration Strategy
1. Keep existing simple functionality as default
2. Add enhanced features behind flags
3. Implement security audit first
4. Add interactive mode
5. Enhance with platform-specific support

## Expected Benefits
- **Security**: Comprehensive permission auditing
- **Flexibility**: Multiple permission sets
- **Automation**: Batch operations with progress
- **Cross-Platform**: Works on Windows/Mac/Linux
- **User Experience**: Interactive and CLI modes