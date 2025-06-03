# Upgrade Plan: test_hang.py

## Overview
Isolates hanging issues in changelog sync by directly importing and testing ChangelogProcessor. Minimal test for debugging specific problems.

## Current State
- **Dependencies**: Standard library + local imports
- **Purpose**: Debug hanging issues in changelog processing
- **Scope**: Very focused debugging tool

## Recommended Upgrades

### 1. Advanced Hang Detection System
```python
# Sophisticated hang detection and analysis
import threading
import signal
import traceback
import psutil
import faulthandler
from typing import Optional, Dict, Any, Callable
import time
import os
import sys
from pathlib import Path

class AdvancedHangDetector:
    def __init__(self):
        self.monitoring_thread = None
        self.stop_monitoring = threading.Event()
        self.hang_detected = False
        self.process_snapshots = []
        self.stack_traces = []
        
        # Enable faulthandler for SIGUSR1
        faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)
        
    def monitor_process(
        self,
        target_func: Callable,
        timeout: int = 30,
        check_interval: int = 1
    ) -> Dict[str, Any]:
        """Monitor a process for hangs with detailed diagnostics"""
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(
            target=self._monitor_loop,
            args=(timeout, check_interval)
        )
        self.monitoring_thread.start()
        
        # Run target function
        start_time = time.time()
        result = None
        exception = None
        
        try:
            result = target_func()
        except Exception as e:
            exception = e
        finally:
            elapsed = time.time() - start_time
            self.stop_monitoring.set()
            self.monitoring_thread.join()
        
        # Compile report
        report = {
            'completed': not self.hang_detected,
            'elapsed_time': elapsed,
            'result': result,
            'exception': exception,
            'process_snapshots': self.process_snapshots,
            'stack_traces': self.stack_traces
        }
        
        if self.hang_detected:
            report['hang_analysis'] = self._analyze_hang()
        
        return report
    
    def _monitor_loop(self, timeout: int, check_interval: int):
        """Monitoring loop that runs in separate thread"""
        start_time = time.time()
        process = psutil.Process()
        
        while not self.stop_monitoring.is_set():
            elapsed = time.time() - start_time
            
            # Take process snapshot
            snapshot = self._take_process_snapshot(process)
            self.process_snapshots.append(snapshot)
            
            # Check for hang conditions
            if elapsed > timeout:
                self.hang_detected = True
                self._handle_hang(process)
                break
            
            # Check for other hang indicators
            if self._detect_hang_indicators(snapshot):
                self.hang_detected = True
                self._handle_hang(process)
                break
            
            time.sleep(check_interval)
    
    def _take_process_snapshot(self, process: psutil.Process) -> Dict[str, Any]:
        """Take snapshot of process state"""
        try:
            snapshot = {
                'timestamp': time.time(),
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_info': process.memory_info()._asdict(),
                'num_threads': process.num_threads(),
                'open_files': len(process.open_files()),
                'connections': len(process.connections()),
                'io_counters': process.io_counters()._asdict() if hasattr(process, 'io_counters') else None
            }
            
            # Get thread info
            if hasattr(process, 'threads'):
                snapshot['threads'] = [
                    {'id': t.id, 'cpu_time': t.user_time + t.system_time}
                    for t in process.threads()
                ]
            
            return snapshot
            
        except Exception as e:
            return {'error': str(e), 'timestamp': time.time()}
    
    def _detect_hang_indicators(self, snapshot: Dict[str, Any]) -> bool:
        """Detect indicators of a hang"""
        # Check for CPU spinning (100% CPU usage)
        if snapshot.get('cpu_percent', 0) > 95:
            return True
        
        # Check for deadlock (0% CPU with no I/O)
        if (snapshot.get('cpu_percent', 100) < 1 and 
            snapshot.get('io_counters', {}).get('read_count', 1) == 0):
            return True
        
        return False
    
    def _handle_hang(self, process: psutil.Process):
        """Handle detected hang"""
        print("\n!!! HANG DETECTED !!!")
        
        # Collect stack traces
        self._collect_stack_traces()
        
        # Dump process info
        self._dump_process_info(process)
        
        # Try to send interrupt signal
        try:
            os.kill(process.pid, signal.SIGUSR1)
        except:
            pass
    
    def _collect_stack_traces(self):
        """Collect Python stack traces"""
        import sys
        import traceback
        
        traces = []
        
        # Get all thread stack traces
        for thread_id, frame in sys._current_frames().items():
            trace = {
                'thread_id': thread_id,
                'stack': traceback.format_stack(frame)
            }
            traces.append(trace)
        
        self.stack_traces = traces
    
    def _analyze_hang(self) -> Dict[str, Any]:
        """Analyze hang data to determine cause"""
        analysis = {
            'likely_cause': 'unknown',
            'evidence': [],
            'recommendations': []
        }
        
        # Analyze CPU usage pattern
        cpu_values = [s.get('cpu_percent', 0) for s in self.process_snapshots[-5:]]
        avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
        
        if avg_cpu > 90:
            analysis['likely_cause'] = 'infinite_loop'
            analysis['evidence'].append(f'High CPU usage: {avg_cpu:.1f}%')
            analysis['recommendations'].append('Check for infinite loops in code')
        elif avg_cpu < 5:
            analysis['likely_cause'] = 'deadlock_or_blocking_io'
            analysis['evidence'].append(f'Low CPU usage: {avg_cpu:.1f}%')
            analysis['recommendations'].append('Check for blocking I/O or deadlocks')
        
        # Analyze stack traces
        if self.stack_traces:
            common_functions = self._find_common_stack_functions()
            if common_functions:
                analysis['evidence'].append(f'Common functions in stacks: {common_functions}')
        
        return analysis
    
    def _find_common_stack_functions(self) -> List[str]:
        """Find functions that appear in multiple thread stacks"""
        from collections import Counter
        
        all_functions = []
        
        for trace in self.stack_traces:
            for line in trace['stack']:
                if 'File' in line and 'line' in line:
                    # Extract function name
                    parts = line.strip().split(',')
                    if len(parts) >= 3:
                        func = parts[2].strip().replace('in ', '')
                        all_functions.append(func)
        
        # Find most common
        counter = Counter(all_functions)
        return [func for func, count in counter.most_common(5) if count > 1]
```

### 2. Changelog Process Debugger
```python
# Specialized debugger for changelog processing
import inspect
import functools
from typing import Any, Callable
import logging

class ChangelogDebugger:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.call_stack = []
        self.execution_times = {}
        self.memory_usage = {}
        
        # Setup logging
        self.logger = logging.getLogger('changelog.debug')
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    def trace_calls(self, func: Callable) -> Callable:
        """Decorator to trace function calls"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Record call
            call_info = {
                'function': func.__name__,
                'module': func.__module__,
                'args': args[:3],  # Limit args to prevent huge output
                'kwargs': list(kwargs.keys()),
                'start_time': time.time()
            }
            
            self.call_stack.append(call_info)
            self.logger.debug(f"Entering {func.__name__}")
            
            # Measure memory before
            process = psutil.Process()
            mem_before = process.memory_info().rss
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Record success
                call_info['status'] = 'success'
                call_info['end_time'] = time.time()
                call_info['duration'] = call_info['end_time'] - call_info['start_time']
                
                # Measure memory after
                mem_after = process.memory_info().rss
                call_info['memory_delta'] = mem_after - mem_before
                
                self.logger.debug(
                    f"Exiting {func.__name__} "
                    f"(duration: {call_info['duration']:.3f}s, "
                    f"memory: {call_info['memory_delta'] / 1024 / 1024:.1f}MB)"
                )
                
                return result
                
            except Exception as e:
                # Record failure
                call_info['status'] = 'failed'
                call_info['exception'] = str(e)
                call_info['end_time'] = time.time()
                
                self.logger.error(f"Exception in {func.__name__}: {e}")
                raise
            
            finally:
                # Always pop from stack
                if self.call_stack and self.call_stack[-1] == call_info:
                    self.call_stack.pop()
        
        return wrapper
    
    def instrument_module(self, module):
        """Instrument all functions in a module"""
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and obj.__module__ == module.__name__:
                setattr(module, name, self.trace_calls(obj))
    
    def get_slow_functions(self, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """Get functions that took longer than threshold"""
        slow_functions = []
        
        for call in self.call_stack:
            if call.get('duration', 0) > threshold:
                slow_functions.append({
                    'function': call['function'],
                    'duration': call['duration'],
                    'args': call['args']
                })
        
        return sorted(slow_functions, key=lambda x: x['duration'], reverse=True)
    
    def get_memory_heavy_functions(self, threshold_mb: float = 10.0) -> List[Dict[str, Any]]:
        """Get functions that used significant memory"""
        memory_heavy = []
        
        for call in self.call_stack:
            memory_mb = call.get('memory_delta', 0) / 1024 / 1024
            if memory_mb > threshold_mb:
                memory_heavy.append({
                    'function': call['function'],
                    'memory_mb': memory_mb,
                    'args': call['args']
                })
        
        return sorted(memory_heavy, key=lambda x: x['memory_mb'], reverse=True)
    
    def generate_debug_report(self) -> str:
        """Generate comprehensive debug report"""
        report = ["Changelog Debug Report", "=" * 40, ""]
        
        # Execution summary
        total_calls = len(self.call_stack)
        failed_calls = sum(1 for c in self.call_stack if c.get('status') == 'failed')
        total_time = sum(c.get('duration', 0) for c in self.call_stack)
        
        report.append(f"Total function calls: {total_calls}")
        report.append(f"Failed calls: {failed_calls}")
        report.append(f"Total execution time: {total_time:.2f}s")
        report.append("")
        
        # Slow functions
        slow_functions = self.get_slow_functions()
        if slow_functions:
            report.append("Slow Functions (>1s):")
            for func in slow_functions[:10]:
                report.append(f"  - {func['function']}: {func['duration']:.2f}s")
            report.append("")
        
        # Memory usage
        memory_heavy = self.get_memory_heavy_functions()
        if memory_heavy:
            report.append("Memory Heavy Functions (>10MB):")
            for func in memory_heavy[:10]:
                report.append(f"  - {func['function']}: {func['memory_mb']:.1f}MB")
            report.append("")
        
        # Call frequency
        from collections import Counter
        function_calls = Counter(c['function'] for c in self.call_stack)
        
        report.append("Most Called Functions:")
        for func, count in function_calls.most_common(10):
            report.append(f"  - {func}: {count} calls")
        
        return "\n".join(report)
```

### 3. Interactive Hang Debugger
```python
# Interactive debugging session for hangs
import code
import readline
import rlcompleter

class InteractiveHangDebugger:
    def __init__(self):
        self.breakpoints = {}
        self.watch_expressions = []
        self.step_mode = False
        
        # Enable tab completion
        readline.parse_and_bind("tab: complete")
        
    def debug_changelog_processor(self, repo_path: str):
        """Start interactive debugging session"""
        print("Interactive Changelog Debugger")
        print("Commands: break, watch, step, continue, inspect, help")
        print("-" * 40)
        
        # Import and prepare processor
        from sync_changelogs import ChangelogProcessor
        
        processor = ChangelogProcessor()
        
        # Inject debugging hooks
        self._inject_hooks(processor)
        
        # Start debugging loop
        self._debug_loop(processor, repo_path)
    
    def _inject_hooks(self, processor):
        """Inject debugging hooks into processor"""
        # Wrap key methods
        original_process = processor.process_commits
        
        def wrapped_process(*args, **kwargs):
            if self.step_mode:
                self._break_point('process_commits', args, kwargs)
            
            return original_process(*args, **kwargs)
        
        processor.process_commits = wrapped_process
    
    def _debug_loop(self, processor, repo_path: str):
        """Main debugging loop"""
        context = {
            'processor': processor,
            'repo_path': repo_path,
            'debugger': self
        }
        
        while True:
            try:
                cmd = input("(debug) > ").strip()
                
                if not cmd:
                    continue
                
                if cmd == 'quit':
                    break
                elif cmd == 'help':
                    self._show_help()
                elif cmd.startswith('break '):
                    self._set_breakpoint(cmd[6:])
                elif cmd.startswith('watch '):
                    self._add_watch(cmd[6:])
                elif cmd == 'step':
                    self.step_mode = True
                    print("Step mode enabled")
                elif cmd == 'continue':
                    self.step_mode = False
                    # Run processor
                    processor.process_repository(repo_path)
                elif cmd.startswith('inspect '):
                    self._inspect_object(cmd[8:], context)
                else:
                    # Execute as Python code
                    exec(cmd, globals(), context)
                    
            except KeyboardInterrupt:
                print("\nInterrupted")
            except Exception as e:
                print(f"Error: {e}")
    
    def _break_point(self, location: str, args, kwargs):
        """Handle breakpoint"""
        print(f"\nBreakpoint hit: {location}")
        print(f"Args: {args[:3]}...")  # Limit output
        print(f"Kwargs: {list(kwargs.keys())}")
        
        # Drop into interactive console
        code.interact(local=locals())
    
    def _show_help(self):
        """Show debugging help"""
        help_text = """
Debugging Commands:
  break <function>  - Set breakpoint on function
  watch <expr>      - Add watch expression
  step              - Enable step-by-step execution
  continue          - Continue execution
  inspect <object>  - Inspect object details
  quit              - Exit debugger

You can also execute arbitrary Python code.
"""
        print(help_text)
```

### 4. Hang Prevention System
```python
# Proactive hang prevention
from typing import Optional, Dict, Any
import asyncio
import concurrent.futures

class HangPreventionSystem:
    def __init__(self):
        self.timeout_config = {
            'git_commands': 30,
            'ai_requests': 60,
            'file_operations': 10,
            'network_requests': 30
        }
        
        self.circuit_breakers = {}
        
    def with_timeout(self, operation_type: str):
        """Decorator to add timeout to operations"""
        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                timeout = self.timeout_config.get(operation_type, 60)
                
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(
                        f"{func.__name__} timed out after {timeout}s"
                    )
            
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                timeout = self.timeout_config.get(operation_type, 60)
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(func, *args, **kwargs)
                    
                    try:
                        return future.result(timeout=timeout)
                    except concurrent.futures.TimeoutError:
                        # Try to cancel
                        future.cancel()
                        raise TimeoutError(
                            f"{func.__name__} timed out after {timeout}s"
                        )
            
            # Return appropriate wrapper
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def circuit_breaker(self, operation_name: str, failure_threshold: int = 5):
        """Circuit breaker pattern to prevent repeated failures"""
        def decorator(func):
            breaker = self._get_circuit_breaker(operation_name, failure_threshold)
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if breaker['state'] == 'open':
                    # Check if we should try again
                    if time.time() - breaker['opened_at'] > breaker['reset_timeout']:
                        breaker['state'] = 'half_open'
                    else:
                        raise RuntimeError(
                            f"Circuit breaker open for {operation_name}"
                        )
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Success - reset failure count
                    breaker['failures'] = 0
                    if breaker['state'] == 'half_open':
                        breaker['state'] = 'closed'
                    
                    return result
                    
                except Exception as e:
                    breaker['failures'] += 1
                    
                    if breaker['failures'] >= failure_threshold:
                        breaker['state'] = 'open'
                        breaker['opened_at'] = time.time()
                    
                    raise e
            
            return wrapper
        
        return decorator
    
    def _get_circuit_breaker(self, name: str, threshold: int) -> Dict[str, Any]:
        """Get or create circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = {
                'state': 'closed',
                'failures': 0,
                'threshold': threshold,
                'opened_at': None,
                'reset_timeout': 60  # 1 minute
            }
        
        return self.circuit_breakers[name]
```

### 5. Hang Test Scenarios
```python
# Comprehensive test scenarios for hang detection
import pytest
import time
import threading

class TestHangScenarios:
    """Test various hang scenarios"""
    
    def test_infinite_loop_detection(self):
        """Test detection of infinite loops"""
        detector = AdvancedHangDetector()
        
        def infinite_loop():
            while True:
                pass
        
        report = detector.monitor_process(infinite_loop, timeout=2)
        
        assert not report['completed']
        assert report['hang_analysis']['likely_cause'] == 'infinite_loop'
    
    def test_deadlock_detection(self):
        """Test detection of deadlocks"""
        detector = AdvancedHangDetector()
        
        lock1 = threading.Lock()
        lock2 = threading.Lock()
        
        def deadlock_func():
            def thread1():
                with lock1:
                    time.sleep(0.1)
                    with lock2:
                        pass
            
            def thread2():
                with lock2:
                    time.sleep(0.1)
                    with lock1:
                        pass
            
            t1 = threading.Thread(target=thread1)
            t2 = threading.Thread(target=thread2)
            
            t1.start()
            t2.start()
            
            t1.join()
            t2.join()
        
        report = detector.monitor_process(deadlock_func, timeout=3)
        
        assert not report['completed']
        assert 'deadlock' in report['hang_analysis']['likely_cause']
    
    def test_blocking_io_detection(self):
        """Test detection of blocking I/O"""
        detector = AdvancedHangDetector()
        
        def blocking_io():
            import socket
            s = socket.socket()
            s.settimeout(None)  # No timeout
            # This will block forever
            s.connect(('192.0.2.0', 80))  # Non-routable IP
        
        report = detector.monitor_process(blocking_io, timeout=3)
        
        assert not report['completed']
        assert 'blocking_io' in report['hang_analysis']['likely_cause']
    
    @pytest.mark.parametrize("scenario,expected_cause", [
        ("cpu_spin", "infinite_loop"),
        ("deadlock", "deadlock_or_blocking_io"),
        ("network_hang", "blocking_io"),
        ("file_lock", "blocking_io")
    ])
    def test_hang_scenarios(self, scenario, expected_cause):
        """Test various hang scenarios"""
        # Implementation for each scenario
        pass
```

## Dependencies to Add
```toml
[project.dependencies]
psutil = "^5.9.6"
faulthandler = "^3.2"  # Built-in but for clarity
pytest = "^7.4.3"
pytest-timeout = "^2.2.0"
matplotlib = "^3.8.2"
memory-profiler = "^0.61.0"
py-spy = "^0.3.14"  # For profiling
```

## Migration Strategy
1. Keep simple hang test for quick debugging
2. Add advanced hang detection
3. Build interactive debugger
4. Implement prevention system
5. Create comprehensive test scenarios

## Expected Benefits
- **Detection**: Identify hangs quickly and accurately
- **Diagnosis**: Understand why hangs occur
- **Prevention**: Avoid hangs proactively
- **Debugging**: Interactive tools for investigation
- **Testing**: Comprehensive hang scenario coverage