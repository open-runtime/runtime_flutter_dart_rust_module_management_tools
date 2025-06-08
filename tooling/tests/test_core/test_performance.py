"""
Tests for performance module
"""
import pytest
from unittest.mock import patch, Mock, MagicMock, mock_open
import time
import json
from pathlib import Path
import os
import psutil

from tooling.core.performance import (
    BenchmarkResult, PerformanceTracker, benchmark, profile_memory,
    TimingContext, track_operation, get_performance_report, save_performance_report,
    measure_time, retry_with_backoff, track_performance, measure_operation,
    get_performance_stats, print_performance_report
)


class TestBenchmarkResult:
    """Test BenchmarkResult dataclass"""
    
    def test_benchmark_result_creation(self):
        """Test creating BenchmarkResult"""
        result = BenchmarkResult(
            name="test_operation",
            duration=1.5,
            memory_start=100.0,
            memory_peak=150.0,
            memory_end=120.0,
            iterations=10,
            metadata={"version": "1.0"}
        )
        
        assert result.name == "test_operation"
        assert result.duration == 1.5
        assert result.memory_start == 100.0
        assert result.memory_peak == 150.0
        assert result.memory_end == 120.0
        assert result.iterations == 10
        assert result.metadata == {"version": "1.0"}
    
    def test_memory_used_property(self):
        """Test memory_used property"""
        result = BenchmarkResult(
            name="test",
            duration=1.0,
            memory_start=100.0,
            memory_peak=150.0,
            memory_end=120.0
        )
        
        assert result.memory_used == 50.0  # peak - start
    
    def test_average_duration_property(self):
        """Test average_duration property"""
        result = BenchmarkResult(
            name="test",
            duration=10.0,
            memory_start=100.0,
            memory_peak=150.0,
            memory_end=120.0,
            iterations=5
        )
        
        assert result.average_duration == 2.0  # duration / iterations
    
    def test_average_duration_zero_iterations(self):
        """Test average_duration with zero iterations"""
        result = BenchmarkResult(
            name="test",
            duration=10.0,
            memory_start=100.0,
            memory_peak=150.0,
            memory_end=120.0,
            iterations=0
        )
        
        assert result.average_duration == 0
    
    def test_to_dict(self):
        """Test to_dict method"""
        result = BenchmarkResult(
            name="test",
            duration=1.0,
            memory_start=100.0,
            memory_peak=150.0,
            memory_end=120.0,
            iterations=1,
            metadata={"test": True}
        )
        
        data = result.to_dict()
        
        assert data['name'] == "test"
        assert data['duration'] == 1.0
        assert data['average_duration'] == 1.0
        assert data['memory_start'] == 100.0
        assert data['memory_peak'] == 150.0
        assert data['memory_end'] == 120.0
        assert data['memory_used'] == 50.0
        assert data['iterations'] == 1
        assert data['metadata'] == {"test": True}
        assert 'timestamp' in data


class TestPerformanceTracker:
    """Test PerformanceTracker class"""
    
    def test_tracker_initialization(self):
        """Test creating PerformanceTracker"""
        tracker = PerformanceTracker("test_tracker")
        
        assert tracker.name == "test_tracker"
        assert tracker.results == []
        assert tracker._start_time is None
        assert tracker._start_memory is None
        assert tracker._peak_memory is None
    
    @patch('psutil.Process')
    def test_start_tracking(self, mock_process):
        """Test starting performance tracking"""
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.return_value = mock_proc
        
        tracker = PerformanceTracker()
        tracker.start()
        
        assert tracker._start_time is not None
        assert tracker._start_memory == 100.0
        assert tracker._peak_memory == 100.0
    
    @patch('psutil.Process')
    @patch('time.time')
    def test_stop_tracking(self, mock_time, mock_process):
        """Test stopping performance tracking"""
        mock_time.side_effect = [1000.0, 1001.5]  # start, stop
        
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.return_value = mock_proc
        
        tracker = PerformanceTracker()
        tracker.start()
        
        result = tracker.stop("test_op", iterations=5, test=True)
        
        assert result.name == "test_op"
        assert result.duration == 1.5
        assert result.iterations == 5
        assert result.metadata == {"test": True}
        assert len(tracker.results) == 1
        
        # Check tracker was reset
        assert tracker._start_time is None
    
    def test_stop_without_start(self):
        """Test stopping tracker without starting"""
        tracker = PerformanceTracker()
        
        with pytest.raises(RuntimeError, match="Tracker not started"):
            tracker.stop("test")
    
    @patch('psutil.Process')
    def test_get_memory_usage(self, mock_process):
        """Test getting memory usage"""
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 150 * 1024 * 1024  # 150 MB
        mock_process.return_value = mock_proc
        
        tracker = PerformanceTracker()
        memory = tracker._get_memory_usage()
        
        assert memory == 150.0
    
    def test_get_summary_empty(self):
        """Test getting summary with no results"""
        tracker = PerformanceTracker("test")
        summary = tracker.get_summary()
        
        assert summary == {'name': 'test', 'results': 0}
    
    def test_get_summary_with_results(self):
        """Test getting summary with results"""
        tracker = PerformanceTracker("test")
        
        # Add some results
        tracker.results = [
            BenchmarkResult("op1", 1.0, 100, 110, 105, 1),
            BenchmarkResult("op2", 2.0, 100, 120, 110, 1),
            BenchmarkResult("op3", 1.5, 100, 115, 108, 1)
        ]
        
        summary = tracker.get_summary()
        
        assert summary['name'] == 'test'
        assert summary['results'] == 3
        assert summary['duration']['total'] == 4.5
        assert summary['duration']['mean'] == 1.5
        assert summary['duration']['min'] == 1.0
        assert summary['duration']['max'] == 2.0
        assert 'memory' in summary
    
    def test_save_results(self, tmp_path):
        """Test saving results to file"""
        tracker = PerformanceTracker("test")
        tracker.results = [
            BenchmarkResult("op1", 1.0, 100, 110, 105, 1)
        ]
        
        file_path = tmp_path / "results.json"
        tracker.save_results(file_path)
        
        assert file_path.exists()
        
        with open(file_path) as f:
            data = json.load(f)
        
        assert data['name'] == 'test'
        assert 'summary' in data
        assert len(data['results']) == 1


class TestDecorators:
    """Test performance decorators"""
    
    @patch('psutil.Process')
    @patch('time.time')
    def test_benchmark_decorator(self, mock_time, mock_process):
        """Test benchmark decorator"""
        mock_time.side_effect = [1000.0, 1001.0]
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_process.return_value = mock_proc
        
        call_count = 0
        
        @benchmark(iterations=3)
        def test_func():
            nonlocal call_count
            call_count += 1
            return "result"
        
        result = test_func()
        
        assert result == "result"
        assert call_count == 3  # Called 3 times
    
    @patch('psutil.Process')
    def test_profile_memory_decorator(self, mock_process):
        """Test profile_memory decorator"""
        mock_proc = Mock()
        # Memory increases from 100MB to 150MB
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_process.return_value = mock_proc
        
        @profile_memory
        def test_func():
            # Simulate memory increase
            mock_proc.memory_info.return_value.rss = 150 * 1024 * 1024
            return "result"
        
        result = test_func()
        assert result == "result"
    
    def test_measure_time_wrapper(self):
        """Test measure_time wrapper"""
        def test_func(x):
            time.sleep(0.1)
            return x * 2
        
        timed_func = measure_time(test_func)
        result, duration = timed_func(5)
        
        assert result == 10
        assert duration >= 0.1
    
    def test_retry_with_backoff_success(self):
        """Test retry_with_backoff with eventual success"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = test_func()
        
        assert result == "success"
        assert call_count == 2
    
    def test_retry_with_backoff_all_failures(self):
        """Test retry_with_backoff when all attempts fail"""
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            test_func()
        
        assert call_count == 3


class TestTimingContext:
    """Test TimingContext class"""
    
    @patch('time.time')
    def test_timing_context(self, mock_time):
        """Test TimingContext usage"""
        mock_time.side_effect = [1000.0, 1001.5]
        
        with TimingContext("test_operation") as ctx:
            pass
        
        assert ctx.duration == 1.5
    
    def test_timing_context_attributes(self):
        """Test TimingContext attributes"""
        ctx = TimingContext("test", log_level="debug")
        
        assert ctx.name == "test"
        assert ctx.log_level == "debug"
        assert ctx.start_time is None
        assert ctx.duration is None


class TestTrackingFunctions:
    """Test tracking utility functions"""
    
    @patch('psutil.Process')
    @patch('time.time')
    def test_track_operation(self, mock_time, mock_process):
        """Test track_operation context manager"""
        mock_time.side_effect = [1000.0, 1000.0, 1001.0, 1001.0]  # start enter, start tracker, stop exit, stop tracker
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_process.return_value = mock_proc
        
        with track_operation("test_op", version="1.0"):
            pass
        
        # Operation should be tracked in global tracker
        report = get_performance_report()
        assert report['results'] >= 1
    
    def test_track_performance_decorator(self):
        """Test track_performance decorator"""
        @track_performance("test_operation")
        def test_func():
            return "result"
        
        result = test_func()
        assert result == "result"
    
    def test_measure_operation_context(self):
        """Test measure_operation context manager"""
        # measure_operation takes metadata as dict, not kwargs
        with measure_operation("test_op", {"type": "test"}):
            time.sleep(0.01)
        
        # Should not raise any errors
        
    def test_get_performance_stats(self):
        """Test get_performance_stats function"""
        # Get stats for all operations
        stats = get_performance_stats()
        assert isinstance(stats, dict)
        
        # Get stats for specific operation
        stats = get_performance_stats("test_op")
        assert isinstance(stats, dict)
    
    @patch('builtins.print')
    def test_print_performance_report(self, mock_print):
        """Test print_performance_report function"""
        print_performance_report()
        mock_print.assert_called()
        
        print_performance_report(detailed=True)
        assert mock_print.call_count >= 1


class TestBackwardCompatibility:
    """Test backward compatibility methods"""
    
    def test_tracker_track_method(self):
        """Test PerformanceTracker.track class method"""
        decorator = PerformanceTracker.track("test_op")
        
        @decorator
        def test_func():
            return "result"
        
        result = test_func()
        assert result == "result"
    
    @patch('psutil.Process')
    def test_tracker_measure_method(self, mock_process):
        """Test PerformanceTracker.measure method"""
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_process.return_value = mock_proc
        
        tracker = PerformanceTracker()
        
        with tracker.measure("test_op"):
            pass
        
        # Should not raise errors
    
    def test_tracker_get_stats_method(self):
        """Test PerformanceTracker.get_stats method"""
        tracker = PerformanceTracker()
        tracker.results = [
            BenchmarkResult("op1", 1.0, 100, 110, 105, 1),
            BenchmarkResult("op2", 2.0, 100, 120, 110, 1)
        ]
        
        # Get all stats
        stats = tracker.get_stats()
        assert stats['count'] == 2
        assert stats['total_time'] == 3.0
        
        # Get specific operation stats
        stats = tracker.get_stats("op1")
        assert stats['count'] == 1
        assert stats['total_time'] == 1.0
    
    @patch('builtins.print')
    def test_tracker_report_method(self, mock_print):
        """Test PerformanceTracker.report method"""
        tracker = PerformanceTracker()
        tracker.report()
        mock_print.assert_called()
        
        tracker.report(detailed=True)
        assert mock_print.call_count >= 1 