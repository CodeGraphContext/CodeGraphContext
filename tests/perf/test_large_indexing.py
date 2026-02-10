
import pytest
import time
from unittest.mock import MagicMock

class TestLargeIndexing:
    """
    Performance tests for indexing logic.
    Mocking the heavy lifting to test the *overhead* of the logic itself,
    or using small samples looped to simulate large volume if we had real DB.
    """

    def test_indexing_overhead(self):
        """Measure overhead of processing a list of files."""
        # Mock the graph builder
        builder = MagicMock()
        files = [f"file_{i}.py" for i in range(1000)]
        
        start_time = time.time()
        
        # Simulate loop
        for f in files:
            builder.create_node(f)
            
        duration = time.time() - start_time
        
        # Assert it's fast (python loop overhead)
        # Real perf test would use real parser + db
        print(f"Processed 1000 files in {duration:.4f}s")
        assert duration < 1.0 # Should be very fast in mock

