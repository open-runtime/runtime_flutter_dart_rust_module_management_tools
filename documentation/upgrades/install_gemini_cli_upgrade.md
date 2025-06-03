# Upgrade Plan: install_gemini_cli.py

## Overview
Simple wrapper script for backward compatibility that redirects to setup_ai_tools.py.

## Current State
- **Dependencies**: Standard library only
- **Key Features**: Backward compatibility wrapper
- **Purpose**: Maintains old command while redirecting to new implementation

## Recommended Upgrades

### 1. Enhanced Deprecation Handling
```python
# Improved deprecation with migration assistance
import warnings
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime
import json

class DeprecationManager:
    def __init__(self, deprecated_script: str, replacement_script: str):
        self.deprecated = deprecated_script
        self.replacement = replacement_script
        self.deprecation_log = Path.home() / '.tesseract_tools' / 'deprecation.log'
        self.deprecation_log.parent.mkdir(exist_ok=True)
        
    def handle_deprecation(self):
        """Handle deprecated script execution"""
        # Log usage
        self._log_usage()
        
        # Show deprecation warning
        self._show_deprecation_warning()
        
        # Offer migration
        if self._should_offer_migration():
            self._offer_migration()
        
        # Execute replacement
        self._execute_replacement()
    
    def _log_usage(self):
        """Log deprecated script usage"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'script': self.deprecated,
            'args': sys.argv[1:],
            'cwd': os.getcwd(),
            'user': os.getenv('USER', 'unknown')
        }
        
        # Append to log file
        with open(self.deprecation_log, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def _show_deprecation_warning(self):
        """Show styled deprecation warning"""
        try:
            from rich.console import Console
            from rich.panel import Panel
            
            console = Console()
            
            console.print(Panel.fit(
                f"[yellow bold]⚠️  DEPRECATION WARNING[/yellow bold]\n\n"
                f"[yellow]{self.deprecated}[/yellow] is deprecated and will be removed in a future version.\n"
                f"Please use [green]{self.replacement}[/green] instead.\n\n"
                f"Run [cyan]migrate-command {self.deprecated}[/cyan] to update your scripts.",
                title="[red]Deprecated Command[/red]",
                border_style="yellow"
            ))
            
        except ImportError:
            # Fallback to simple warning
            warnings.warn(
                f"\n{'='*60}\n"
                f"DEPRECATION: {self.deprecated} is deprecated.\n"
                f"Use {self.replacement} instead.\n"
                f"{'='*60}\n",
                DeprecationWarning,
                stacklevel=2
            )
    
    def _should_offer_migration(self) -> bool:
        """Check if we should offer migration assistance"""
        # Check if this is the first time seeing this deprecation
        migration_state_file = Path.home() / '.tesseract_tools' / f'.migrated_{self.deprecated}'
        return not migration_state_file.exists()
    
    def _offer_migration(self):
        """Offer to help migrate scripts"""
        try:
            import questionary
            
            if questionary.confirm(
                "Would you like help updating your scripts to use the new command?"
            ).ask():
                self._run_migration_assistant()
            else:
                # Mark as seen
                migration_state_file = Path.home() / '.tesseract_tools' / f'.migrated_{self.deprecated}'
                migration_state_file.touch()
                
        except ImportError:
            pass
    
    def _run_migration_assistant(self):
        """Run migration assistant"""
        from .migration_assistant import MigrationAssistant
        
        assistant = MigrationAssistant(self.deprecated, self.replacement)
        assistant.run()
    
    def _execute_replacement(self):
        """Execute the replacement script"""
        setup_script = Path(__file__).parent / self.replacement
        
        if not setup_script.exists():
            print(f"Error: Replacement script {self.replacement} not found")
            sys.exit(1)
        
        # Preserve all arguments and environment
        env = os.environ.copy()
        env['DEPRECATION_REDIRECT'] = '1'
        env['ORIGINAL_COMMAND'] = self.deprecated
        
        # Execute replacement
        result = subprocess.run(
            [sys.executable, str(setup_script)] + sys.argv[1:],
            env=env
        )
        
        sys.exit(result.returncode)
```

### 2. Migration Assistant
```python
# Help users migrate from deprecated commands
import re
from pathlib import Path
from typing import List, Dict, Tuple

class MigrationAssistant:
    def __init__(self, old_command: str, new_command: str):
        self.old_command = old_command
        self.new_command = new_command
        
    def run(self):
        """Run migration assistant"""
        print(f"\n🔄 Migration Assistant: {self.old_command} → {self.new_command}")
        
        # Find scripts using old command
        scripts = self._find_scripts_using_command()
        
        if not scripts:
            print("✅ No scripts found using the deprecated command.")
            self._mark_migrated()
            return
        
        print(f"\nFound {len(scripts)} scripts using {self.old_command}:")
        for script in scripts:
            print(f"  - {script}")
        
        # Offer to update scripts
        if self._confirm_update():
            self._update_scripts(scripts)
        
        # Offer to create alias
        if self._confirm_alias():
            self._create_alias()
        
        self._mark_migrated()
    
    def _find_scripts_using_command(self) -> List[Path]:
        """Find scripts that use the deprecated command"""
        scripts = []
        
        # Search common locations
        search_paths = [
            Path.home() / 'bin',
            Path.home() / '.local' / 'bin',
            Path('/usr/local/bin'),
            Path.cwd()
        ]
        
        patterns = [
            f'{self.old_command}',
            f'python {self.old_command}',
            f'python3 {self.old_command}'
        ]
        
        for search_path in search_paths:
            if search_path.exists():
                for file in search_path.rglob('*'):
                    if file.is_file() and self._file_contains_command(file, patterns):
                        scripts.append(file)
        
        # Also check shell history
        history_files = [
            Path.home() / '.bash_history',
            Path.home() / '.zsh_history'
        ]
        
        for history_file in history_files:
            if history_file.exists() and self._file_contains_command(history_file, patterns):
                print(f"\n📝 Note: Found usage in {history_file.name}")
        
        return scripts
    
    def _file_contains_command(self, file: Path, patterns: List[str]) -> bool:
        """Check if file contains deprecated command"""
        try:
            content = file.read_text()
            for pattern in patterns:
                if pattern in content:
                    return True
        except:
            pass
        return False
    
    def _update_scripts(self, scripts: List[Path]):
        """Update scripts to use new command"""
        updated = 0
        
        for script in scripts:
            try:
                # Read content
                content = script.read_text()
                
                # Replace command
                original = content
                content = content.replace(self.old_command, self.new_command)
                content = content.replace(f'python {self.old_command}', f'python {self.new_command}')
                content = content.replace(f'python3 {self.old_command}', f'python3 {self.new_command}')
                
                if content != original:
                    # Backup original
                    backup = script.with_suffix(script.suffix + '.bak')
                    backup.write_text(original)
                    
                    # Write updated content
                    script.write_text(content)
                    
                    print(f"✅ Updated: {script} (backup: {backup})")
                    updated += 1
                    
            except Exception as e:
                print(f"❌ Failed to update {script}: {e}")
        
        print(f"\nUpdated {updated} scripts.")
    
    def _create_alias(self):
        """Create shell alias for backward compatibility"""
        alias_line = f"alias {self.old_command}='{self.new_command}'"
        
        # Detect shell
        shell = os.environ.get('SHELL', '/bin/bash')
        
        if 'zsh' in shell:
            rc_file = Path.home() / '.zshrc'
        elif 'bash' in shell:
            rc_file = Path.home() / '.bashrc'
        else:
            print(f"Unknown shell: {shell}")
            return
        
        # Add alias
        if rc_file.exists():
            content = rc_file.read_text()
            
            if alias_line not in content:
                with open(rc_file, 'a') as f:
                    f.write(f"\n# Added by Tesseract Tools migration\n")
                    f.write(f"{alias_line}\n")
                
                print(f"✅ Added alias to {rc_file}")
                print(f"   Run 'source {rc_file}' to activate")
    
    def _confirm_update(self) -> bool:
        """Confirm script updates"""
        try:
            import questionary
            return questionary.confirm(
                "Update these scripts automatically?"
            ).ask()
        except ImportError:
            response = input("Update scripts? (y/n): ")
            return response.lower() == 'y'
    
    def _confirm_alias(self) -> bool:
        """Confirm alias creation"""
        try:
            import questionary
            return questionary.confirm(
                f"Create alias '{self.old_command}' → '{self.new_command}'?"
            ).ask()
        except ImportError:
            response = input("Create alias? (y/n): ")
            return response.lower() == 'y'
    
    def _mark_migrated(self):
        """Mark migration as complete"""
        migration_state_file = Path.home() / '.tesseract_tools' / f'.migrated_{self.old_command}'
        migration_state_file.parent.mkdir(exist_ok=True)
        migration_state_file.touch()
```

### 3. Command Compatibility Layer
```python
# Maintain backward compatibility with command transformations
from typing import List, Dict, Optional

class CommandCompatibilityLayer:
    def __init__(self):
        self.command_mappings = {
            'install_gemini_cli.py': {
                'replacement': 'setup_ai_tools.py',
                'arg_mappings': {
                    '--force': '--reinstall',
                    '--quiet': '--silent',
                    '--api-key': '--gemini-api-key'
                },
                'removed_args': ['--legacy'],
                'new_defaults': {
                    '--setup-all': True
                }
            }
        }
    
    def transform_command(self, old_command: str, args: List[str]) -> Tuple[str, List[str]]:
        """Transform old command and arguments to new format"""
        if old_command not in self.command_mappings:
            return old_command, args
        
        mapping = self.command_mappings[old_command]
        new_command = mapping['replacement']
        new_args = []
        
        # Transform arguments
        i = 0
        while i < len(args):
            arg = args[i]
            
            # Skip removed arguments
            if arg in mapping.get('removed_args', []):
                # Skip this arg and its value if it has one
                if i + 1 < len(args) and not args[i + 1].startswith('-'):
                    i += 1
                i += 1
                continue
            
            # Map old arguments to new
            if arg in mapping.get('arg_mappings', {}):
                new_arg = mapping['arg_mappings'][arg]
                new_args.append(new_arg)
            else:
                new_args.append(arg)
            
            i += 1
        
        # Add new defaults
        for arg, value in mapping.get('new_defaults', {}).items():
            if arg not in new_args:
                if isinstance(value, bool) and value:
                    new_args.append(arg)
                elif not isinstance(value, bool):
                    new_args.extend([arg, str(value)])
        
        return new_command, new_args
```

### 4. Usage Analytics
```python
# Track deprecated command usage for removal planning
from collections import Counter
from datetime import datetime, timedelta
import json

class DeprecationAnalytics:
    def __init__(self):
        self.log_file = Path.home() / '.tesseract_tools' / 'deprecation.log'
        
    def analyze_usage(self, days: int = 30) -> Dict[str, Any]:
        """Analyze deprecated command usage"""
        if not self.log_file.exists():
            return {'error': 'No deprecation log found'}
        
        # Parse log entries
        entries = []
        with open(self.log_file) as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except:
                    continue
        
        # Filter by date
        cutoff = datetime.now() - timedelta(days=days)
        recent_entries = [
            e for e in entries
            if datetime.fromisoformat(e['timestamp']) > cutoff
        ]
        
        # Analyze usage
        analysis = {
            'period_days': days,
            'total_uses': len(recent_entries),
            'unique_users': len(set(e.get('user', 'unknown') for e in recent_entries)),
            'by_script': Counter(e['script'] for e in recent_entries),
            'by_user': Counter(e.get('user', 'unknown') for e in recent_entries),
            'with_args': sum(1 for e in recent_entries if e.get('args')),
            'daily_average': len(recent_entries) / days if days > 0 else 0
        }
        
        # Recommendations
        if analysis['total_uses'] == 0:
            analysis['recommendation'] = 'Safe to remove - no recent usage'
        elif analysis['daily_average'] < 0.1:
            analysis['recommendation'] = 'Consider removal - very low usage'
        else:
            analysis['recommendation'] = 'Keep deprecation - still actively used'
        
        return analysis
    
    def generate_report(self) -> str:
        """Generate deprecation report"""
        from rich.console import Console
        from rich.table import Table
        from io import StringIO
        
        buffer = StringIO()
        console = Console(file=buffer)
        
        # Analyze different periods
        periods = [7, 30, 90]
        
        for period in periods:
            analysis = self.analyze_usage(period)
            
            if 'error' not in analysis:
                console.print(f"\n[bold]Last {period} days:[/bold]")
                
                table = Table()
                table.add_column("Metric", style="cyan")
                table.add_column("Value", justify="right")
                
                table.add_row("Total Uses", str(analysis['total_uses']))
                table.add_row("Unique Users", str(analysis['unique_users']))
                table.add_row("Daily Average", f"{analysis['daily_average']:.2f}")
                table.add_row("With Arguments", str(analysis['with_args']))
                
                console.print(table)
                
                # Top scripts
                if analysis['by_script']:
                    console.print("\n[bold]Top deprecated scripts:[/bold]")
                    for script, count in analysis['by_script'].most_common(5):
                        console.print(f"  {script}: {count} uses")
                
                console.print(f"\n[yellow]Recommendation: {analysis['recommendation']}[/yellow]")
        
        return buffer.getvalue()
```

### 5. Graceful Removal Path
```python
# Plan for eventual removal of deprecated commands
from datetime import datetime, timedelta
from typing import Optional

class DeprecationLifecycle:
    def __init__(self, deprecated_command: str):
        self.command = deprecated_command
        self.lifecycle_file = Path.home() / '.tesseract_tools' / f'{deprecated_command}.lifecycle'
        
        # Deprecation stages
        self.stages = {
            'soft_deprecation': {
                'duration_days': 90,
                'action': 'warn',
                'message': 'This command is deprecated'
            },
            'hard_deprecation': {
                'duration_days': 180,
                'action': 'warn_strongly',
                'message': 'This command will be removed soon'
            },
            'final_warning': {
                'duration_days': 30,
                'action': 'require_confirmation',
                'message': 'FINAL WARNING: This command will be removed'
            },
            'removed': {
                'duration_days': None,
                'action': 'block',
                'message': 'This command has been removed'
            }
        }
    
    def get_current_stage(self) -> Tuple[str, Dict]:
        """Get current deprecation stage"""
        if not self.lifecycle_file.exists():
            # Initialize lifecycle
            self._initialize_lifecycle()
        
        with open(self.lifecycle_file) as f:
            lifecycle_data = json.load(f)
        
        start_date = datetime.fromisoformat(lifecycle_data['start_date'])
        days_elapsed = (datetime.now() - start_date).days
        
        cumulative_days = 0
        for stage_name, stage_config in self.stages.items():
            if stage_config['duration_days'] is None:
                return stage_name, stage_config
            
            cumulative_days += stage_config['duration_days']
            if days_elapsed < cumulative_days:
                return stage_name, stage_config
        
        return 'removed', self.stages['removed']
    
    def _initialize_lifecycle(self):
        """Initialize deprecation lifecycle"""
        lifecycle_data = {
            'command': self.command,
            'start_date': datetime.now().isoformat(),
            'stages': list(self.stages.keys())
        }
        
        self.lifecycle_file.parent.mkdir(exist_ok=True)
        with open(self.lifecycle_file, 'w') as f:
            json.dump(lifecycle_data, f, indent=2)
    
    def handle_stage_action(self, stage_name: str, stage_config: Dict) -> bool:
        """Handle action for current stage"""
        action = stage_config['action']
        
        if action == 'warn':
            self._show_warning(stage_config['message'], level='warning')
            return True
            
        elif action == 'warn_strongly':
            self._show_warning(stage_config['message'], level='error')
            return True
            
        elif action == 'require_confirmation':
            self._show_warning(stage_config['message'], level='critical')
            
            try:
                import questionary
                return questionary.confirm(
                    "Do you really want to continue with this deprecated command?"
                ).ask()
            except ImportError:
                response = input("Continue anyway? (yes/no): ")
                return response.lower() == 'yes'
                
        elif action == 'block':
            self._show_removal_message()
            return False
        
        return True
    
    def _show_removal_message(self):
        """Show removal message with migration help"""
        try:
            from rich.console import Console
            from rich.panel import Panel
            
            console = Console()
            
            console.print(Panel(
                f"[red bold]❌ REMOVED COMMAND[/red bold]\n\n"
                f"The command '{self.command}' has been removed.\n\n"
                f"Please use the replacement command instead.\n"
                f"Run 'tesseract-tools migrate-help {self.command}' for assistance.",
                title="[red]Command Removed[/red]",
                border_style="red"
            ))
            
        except ImportError:
            print(f"\nERROR: {self.command} has been removed.")
            print("Use the replacement command instead.\n")
```

## Dependencies to Add
```toml
[project.dependencies]
rich = "^13.7.0"
questionary = "^2.0.1"
python-dateutil = "^2.8.2"
```

## Migration Strategy
1. Keep simple wrapper as is for compatibility
2. Add deprecation tracking
3. Implement migration assistant
4. Add analytics for removal planning
5. Plan phased removal

## Expected Benefits
- **Compatibility**: Smooth transition for users
- **Analytics**: Data-driven removal decisions
- **Assistance**: Automated migration help
- **Communication**: Clear deprecation stages
- **Planning**: Structured removal lifecycle