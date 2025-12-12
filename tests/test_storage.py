"""
Tests for storage module.
"""

import pytest
import json
from datetime import datetime


def test_data_metadata():
    """Test DataMetadata serialization."""
    from bsv_llm.storage import DataMetadata, DataType
    
    metadata = DataMetadata(
        name="test_data",
        data_type=DataType.JSON,
        description="Test description",
        size_bytes=1024,
        compressed=True,
        data_hash="abc123",
        custom={"key": "value"},
    )
    
    # Test to_dict
    d = metadata.to_dict()
    assert d["name"] == "test_data"
    assert d["data_type"] == "json"
    assert d["compressed"] is True
    
    # Test from_dict
    metadata2 = DataMetadata.from_dict(d)
    assert metadata2.name == metadata.name
    assert metadata2.data_type == metadata.data_type
    assert metadata2.custom == metadata.custom
    
    # Test to_json
    json_str = metadata.to_json()
    parsed = json.loads(json_str)
    assert parsed["name"] == "test_data"


def test_storage_result():
    """Test StorageResult properties."""
    from bsv_llm.storage import StorageResult
    
    # Successful single tx result
    result = StorageResult(
        success=True,
        txid="abc123",
        data_hash="hash123",
    )
    assert result.all_txids == ["abc123"]
    
    # Successful chunked result
    result = StorageResult(
        success=True,
        metadata_txid="meta123",
        chunk_txids=["chunk1", "chunk2", "chunk3"],
        data_hash="hash456",
    )
    assert result.all_txids == ["meta123", "chunk1", "chunk2", "chunk3"]


def test_data_preparation():
    """Test data preparation for storage."""
    from bsv_llm.storage import DatasetStorage, DataType
    
    storage = DatasetStorage()
    
    # Test string to bytes
    data, compressed = storage._prepare_data("hello", DataType.TEXT, compress=False)
    assert data == b"hello"
    assert compressed is False
    
    # Test dict to bytes
    test_dict = {"key": "value"}
    data, compressed = storage._prepare_data(test_dict, DataType.JSON, compress=False)
    assert json.loads(data) == test_dict
    
    # Test compression (only for larger data)
    large_data = "x" * 2000
    data, compressed = storage._prepare_data(large_data, DataType.TEXT, compress=True)
    assert compressed is True
    assert len(data) < len(large_data)


def test_chunking():
    """Test data chunking for large storage."""
    from bsv_llm.storage import DatasetStorage
    
    storage = DatasetStorage()
    
    # Small data - single chunk
    small_data = b"x" * 1000
    chunks = storage._chunk_data(small_data)
    assert len(chunks) == 1
    assert chunks[0] == small_data
    
    # Large data - multiple chunks
    large_data = b"x" * (storage.MAX_CHUNK_SIZE * 2 + 1000)
    chunks = storage._chunk_data(large_data)
    assert len(chunks) == 3
    assert b"".join(chunks) == large_data
