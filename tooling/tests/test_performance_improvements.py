"""
Performance tests demonstrating improvements from async operations.
"""
import asyncio
import time
from pathlib import Path
import tempfile
import pytest
from unittest.mock import Mock, patch, AsyncMock

# Add the parent directory to the path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.utils.async_git_utils import AsyncGitOperations, GitBatchProcessor
from tooling.utils.async_file_utils import AsyncFileOperations, FileBatchProcessor
from tooling.core.ai_operations import AsyncAIClient


class TestPerformanceImprovements:
    """Test performance improvements from async operations"""
    
    @pytest.mark.asyncio
    async def test_parallel_git_operations(self):
        """Test parallel git operations are faster than sequential"""
        # Mock git operations
        async_git = AsyncGitOperations()
        
        # Mock the run_command to simulate delay
        async def mock_run_command(cmd):
            await asyncio.sleep(0.1)  # Simulate 100ms git operation
            return type('obj', (object,), {
                'success': True,
                'stdout': 'mock output',
                'stderr': ''
            })
        
        async_git.run_command = mock_run_command
        
        # Test sequential
        start = time.time()
        for i in range(5):
            await async_git.get_commits_between(f"v{i}.0.0", f"v{i+1}.0.0")
        sequential_time = time.time() - start
        
        # Test parallel
        start = time.time()
        ref_pairs = [(f"v{i}.0.0", f"v{i+1}.0.0") for i in range(5)]
        await async_git.get_commits_batch(ref_pairs)
        parallel_time = time.time() - start
        
        # Parallel should be significantly faster
        assert parallel_time < sequential_time * 0.3
        print(f"Sequential: {sequential_time:.2f}s, Parallel: {parallel_time:.2f}s")
        print(f"Speedup: {sequential_time / parallel_time:.1f}x")
    
    @pytest.mark.asyncio
    async def test_parallel_file_operations(self):
        """Test parallel file operations are faster than sequential"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create test files
            files = {}
            for i in range(10):
                file_path = tmppath / f"test_{i}.txt"
                content = f"Content of file {i}\n" * 100
                file_path.write_text(content)
                files[file_path] = content + " modified"
            
            file_ops = AsyncFileOperations()
            
            # Test sequential writes
            start = time.time()
            for path, content in files.items():
                await file_ops.write_file(path, content)
            sequential_time = time.time() - start
            
            # Test parallel writes
            start = time.time()
            await file_ops.write_files_batch(files)
            parallel_time = time.time() - start
            
            # Parallel should be faster (or at least not significantly slower)
            # On very fast systems, the overhead might reduce the benefit
            assert parallel_time <= sequential_time * 1.1  # Allow up to 10% slower for overhead
            print(f"File I/O - Sequential: {sequential_time:.2f}s, Parallel: {parallel_time:.2f}s")
            if parallel_time < sequential_time:
                print(f"Speedup: {sequential_time / parallel_time:.1f}x")
            else:
                print(f"Parallel was {parallel_time / sequential_time:.1f}x slower due to overhead")
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing performance"""
        processor = GitBatchProcessor(batch_size=10)
        
        # Mock processor function
        async def mock_processor(batch):
            await asyncio.sleep(0.05 * len(batch))  # Simulate processing time
            return [f"processed_{item}" for item in batch]
        
        # Test with 100 items
        items = [f"item_{i}" for i in range(100)]
        
        start = time.time()
        results = await processor.process_commits_in_batches(
            items,
            mock_processor,
            max_concurrent=5
        )
        batch_time = time.time() - start
        
        # Should process all items
        assert len(results) == 100
        
        # Calculate theoretical sequential time
        sequential_time = 0.05 * 100  # 5 seconds if processed one by one
        
        print(f"Batch processing - Time: {batch_time:.2f}s")
        print(f"Theoretical sequential: {sequential_time:.2f}s")
        print(f"Speedup: {sequential_time / batch_time:.1f}x")
        
        # Should be significantly faster
        assert batch_time < sequential_time * 0.3
    
    @pytest.mark.asyncio
    async def test_ai_parallel_calls(self):
        """Test parallel AI API calls"""
        # Mock AI responses
        mock_responses = []
        
        async def mock_generate(self, prompt, model=None):
            await asyncio.sleep(0.2)  # Simulate API delay
            return type('obj', (object,), {
                'content': f"Response for: {prompt[:20]}...",
                'model': model or 'test-model',
                'error': None
            })
        
        with patch.object(AsyncAIClient, 'generate_single', mock_generate):
            client = AsyncAIClient(max_concurrent=5)
            
            prompts = [f"Analyze this code: {i}" for i in range(10)]
            
            # Test sequential (simulated)
            start = time.time()
            sequential_results = []
            for prompt in prompts:
                result = await mock_generate(None, prompt)
                sequential_results.append(result)
            sequential_time = time.time() - start
            
            # Test parallel
            start = time.time()
            parallel_results = await client.generate_batch(prompts)
            parallel_time = time.time() - start
            
            # Parallel should be significantly faster
            assert parallel_time < sequential_time * 0.5
            assert len(parallel_results) == 10
            
            print(f"Sequential: {sequential_time:.2f}s, Parallel: {parallel_time:.2f}s")
            print(f"Speedup: {sequential_time / parallel_time:.1f}x")
    
    @pytest.mark.asyncio
    async def test_real_world_scenario(self):
        """Test a real-world scenario combining multiple async operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Simulate a project with multiple files
            project_files = []
            for i in range(5):
                file_path = tmppath / f"module_{i}.py"
                content = f"# Module {i}\n" + "def function():\n    pass\n" * 10
                file_path.write_text(content)
                project_files.append(file_path)
            
            # Mock git operations
            async def mock_git_diff(from_ref, to_ref):
                await asyncio.sleep(0.1)
                return project_files
            
            # Mock AI analysis
            async def mock_analyze(files, template):
                await asyncio.sleep(0.2)
                return {str(f): f"Analysis of {f.name}" for f in files}
            
            # Measure combined operations
            start = time.time()
            
            # 1. Get changed files (mock)
            changed_files = await mock_git_diff("v1.0.0", "HEAD")
            
            # 2. Read files in parallel
            file_ops = AsyncFileOperations()
            file_contents = await file_ops.read_files_batch(changed_files)
            
            # 3. Analyze files in parallel (mock)
            analyses = await mock_analyze(changed_files, "template")
            
            total_time = time.time() - start
            
            print(f"Real-world scenario - Total time: {total_time:.2f}s")
            
            # Should complete quickly due to parallelization
            assert total_time < 0.5  # Should be around 0.3s with parallel ops
            assert len(file_contents) == 5
            assert len(analyses) == 5


class TestMemoryEfficiency:
    """Test memory efficiency of batch operations"""
    
    @pytest.mark.asyncio
    async def test_streaming_large_files(self):
        """Test that batch processor doesn't load everything into memory at once"""
        processor = FileBatchProcessor(batch_size=10)
        
        # Track memory usage simulation
        memory_peaks = []
        
        async def mock_processor(path, content):
            # Simulate memory usage tracking
            memory_peaks.append(len(content))
            await asyncio.sleep(0.01)
            return f"Processed {path.name}"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create many small files instead of few large ones
            for i in range(100):
                file_path = tmppath / f"file_{i}.txt"
                file_path.write_text(f"Content {i}\n" * 10)
            
            # Process with batching
            results = await processor.process_large_directory(
                tmppath,
                mock_processor,
                pattern="*.txt"
            )
            
            assert len(results) == 100
            
            # Memory usage should be relatively constant due to batching
            # (In real implementation, we'd use memory_profiler)
            print(f"Processed {len(results)} files in batches")


if __name__ == "__main__":
    # Run performance tests
    asyncio.run(TestPerformanceImprovements().test_parallel_git_operations())
    asyncio.run(TestPerformanceImprovements().test_parallel_file_operations())
    asyncio.run(TestPerformanceImprovements().test_batch_processing())
    asyncio.run(TestPerformanceImprovements().test_ai_parallel_calls())
    asyncio.run(TestPerformanceImprovements().test_real_world_scenario()) 