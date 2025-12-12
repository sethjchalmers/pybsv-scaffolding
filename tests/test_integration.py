"""
Integration tests for BSV-LLM with live Teranode container.

These tests run against the local Docker Teranode instance.
"""

import pytest
import asyncio
import hashlib
import json
from unittest.mock import patch, AsyncMock

import httpx


# Test configuration - matches docker-compose settings
TERANODE_RPC_URL = "http://localhost:9292"
TERANODE_RPC_USER = "teranode"
TERANODE_RPC_PASSWORD = "teranode123"


class TestTeranodeConnection:
    """Test basic connectivity to Teranode container."""
    
    @pytest.fixture
    def rpc_auth(self):
        """RPC authentication tuple."""
        return (TERANODE_RPC_USER, TERANODE_RPC_PASSWORD)
    
    @pytest.mark.asyncio
    async def test_rpc_connection(self, rpc_auth):
        """Test that we can connect to the Teranode RPC."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                TERANODE_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getinfo",
                    "params": []
                },
                auth=rpc_auth,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "result" in data or "error" not in data or data["error"] is None
    
    @pytest.mark.asyncio
    async def test_get_blockchain_info(self, rpc_auth):
        """Test getting blockchain info from Teranode."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                TERANODE_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getblockchaininfo",
                    "params": []
                },
                auth=rpc_auth,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            result = data.get("result", {})
            
            # Verify we're on teratestnet
            assert result.get("chain") == "teratestnet"
            # Block count should be >= 0
            assert result.get("blocks", -1) >= 0
    
    @pytest.mark.asyncio
    async def test_get_block_count(self, rpc_auth):
        """Test getting current block height via getblockchaininfo."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                TERANODE_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getblockchaininfo",
                    "params": []
                },
                auth=rpc_auth,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            result = data.get("result", {})
            # Block count should be a non-negative integer
            assert isinstance(result.get("blocks"), int)
            assert result["blocks"] >= 0


class TestDataStorageRetrieval:
    """Test data storage and retrieval functionality."""
    
    TEST_DATA = b"Seth is cool"
    TEST_DATA_HASH = hashlib.sha256(TEST_DATA).hexdigest()
    
    @pytest.fixture
    def rpc_auth(self):
        """RPC authentication tuple."""
        return (TERANODE_RPC_USER, TERANODE_RPC_PASSWORD)
    
    def test_data_hash_computation(self):
        """Test that we correctly compute data hashes."""
        data = b"Seth is cool"
        expected_hash = hashlib.sha256(data).hexdigest()
        
        assert expected_hash == self.TEST_DATA_HASH
        assert len(expected_hash) == 64  # SHA256 produces 64 hex chars
    
    def test_create_op_return_script(self):
        """Test creating an OP_RETURN script with data."""
        from bsv import Script
        
        data = self.TEST_DATA
        
        # Build OP_RETURN script: OP_FALSE OP_RETURN <data>
        # The BSV SDK uses from_asm with hex-encoded data
        script = Script.from_asm(f'OP_FALSE OP_RETURN {data.hex()}')
        
        # Verify script was created
        script_hex = script.hex()
        assert script_hex is not None
        assert len(script_hex) > 0
        
        # Verify OP_FALSE (0x00) and OP_RETURN (0x6a) are present
        script_bytes = bytes.fromhex(script_hex)
        assert script_bytes[0] == 0x00  # OP_FALSE
        assert script_bytes[1] == 0x6a  # OP_RETURN
        
        # Verify data is in the script
        assert data in script_bytes
    
    def test_extract_data_from_op_return_script(self):
        """Test extracting data from an OP_RETURN script."""
        from bsv import Script
        
        original_data = self.TEST_DATA
        
        # Create the script using from_asm
        script = Script.from_asm(f'OP_FALSE OP_RETURN {original_data.hex()}')
        
        script_bytes = bytes.fromhex(script.hex())
        
        # Extract data from script
        # Format: OP_FALSE (1 byte) + OP_RETURN (1 byte) + pushdata opcode + data
        assert script_bytes[0] == 0x00  # OP_FALSE
        assert script_bytes[1] == 0x6a  # OP_RETURN
        
        # Next byte indicates data length (for small data < 76 bytes)
        idx = 2
        if script_bytes[idx] < 0x4c:  # Direct push
            length = script_bytes[idx]
            idx += 1
        elif script_bytes[idx] == 0x4c:  # OP_PUSHDATA1
            length = script_bytes[idx + 1]
            idx += 2
        
        extracted_data = script_bytes[idx:idx + length]
        
        assert extracted_data == original_data
        assert extracted_data.decode('utf-8') == "Seth is cool"
    
    def test_metadata_serialization(self):
        """Test metadata serialization for storage."""
        from bsv_llm.storage import DataMetadata, DataType
        
        metadata = DataMetadata(
            name="test_data",
            data_type=DataType.TEXT,
            description="Test data: Seth is cool",
            size_bytes=len(self.TEST_DATA),
            data_hash=self.TEST_DATA_HASH
        )
        
        # Serialize to dict
        metadata_dict = metadata.to_dict()
        assert metadata_dict["name"] == "test_data"
        assert metadata_dict["data_type"] == "text"
        assert metadata_dict["data_hash"] == self.TEST_DATA_HASH
        
        # Serialize to JSON
        metadata_json = metadata.to_json()
        assert "Seth is cool" in metadata_json
        
        # Deserialize
        restored = DataMetadata.from_dict(json.loads(metadata_json))
        assert restored.name == metadata.name
        assert restored.data_hash == metadata.data_hash
    
    @pytest.mark.asyncio
    async def test_client_rpc_call(self, rpc_auth):
        """Test BSVClient RPC functionality against live node."""
        from bsv_llm.client import BSVClient
        from bsv_llm.config import Config, TeranodeConfig
        
        config = Config(
            teranode=TeranodeConfig(
                rpc_host="localhost",
                rpc_port=9292,
                rpc_user=TERANODE_RPC_USER,
                rpc_password=TERANODE_RPC_PASSWORD
            )
        )
        
        async with BSVClient(config) as client:
            # Test getinfo
            info = await client.rpc_call("getblockchaininfo")
            assert info is not None
            assert info.get("chain") == "teratestnet"
    
    @pytest.mark.asyncio
    async def test_storage_payload_creation(self):
        """Test creating a complete storage payload."""
        from bsv_llm.storage import DatasetStorage, DataMetadata, DataType
        from bsv_llm.config import Config, TeranodeConfig
        
        config = Config(
            teranode=TeranodeConfig(
                rpc_host="localhost",
                rpc_port=9292,
                rpc_user=TERANODE_RPC_USER,
                rpc_password=TERANODE_RPC_PASSWORD
            )
        )
        
        storage = DatasetStorage(config=config)
        
        # Create payload for "Seth is cool"
        metadata = DataMetadata(
            name="seth_message",
            data_type=DataType.TEXT,
            description="A cool message",
            size_bytes=len(self.TEST_DATA),
            data_hash=self.TEST_DATA_HASH
        )
        
        payload = storage._create_payload(self.TEST_DATA, metadata)
        
        # Verify payload structure
        assert payload.startswith(DatasetStorage.PROTOCOL_PREFIX)
        assert self.TEST_DATA in payload
        
        # Verify we can parse it back
        parsed_metadata, parsed_data = storage._parse_payload(payload)
        assert parsed_data == self.TEST_DATA
        assert parsed_metadata.name == "seth_message"
        assert parsed_metadata.data_hash == self.TEST_DATA_HASH


class TestFullRoundTrip:
    """Test complete store and retrieve cycle (simulated without real funds)."""
    
    TEST_MESSAGE = "Seth is cool"
    
    @pytest.fixture
    def rpc_auth(self):
        """RPC authentication tuple."""
        return (TERANODE_RPC_USER, TERANODE_RPC_PASSWORD)
    
    @pytest.mark.asyncio
    async def test_simulated_store_and_retrieve(self, rpc_auth):
        """
        Test the full store/retrieve cycle with simulated transaction.
        
        Since we don't have funded UTXOs on the testnet, we simulate
        the transaction creation and parsing to verify the logic works.
        """
        from bsv_llm.storage import DatasetStorage, DataMetadata, DataType
        from bsv_llm.retrieval import DatasetRetrieval
        from bsv_llm.config import Config, TeranodeConfig
        
        config = Config(
            teranode=TeranodeConfig(
                rpc_host="localhost",
                rpc_port=9292,
                rpc_user=TERANODE_RPC_USER,
                rpc_password=TERANODE_RPC_PASSWORD
            )
        )
        
        # Create storage instance
        storage = DatasetStorage(config=config)
        
        # Prepare the data
        data = self.TEST_MESSAGE.encode('utf-8')
        data_hash = hashlib.sha256(data).hexdigest()
        
        metadata = DataMetadata(
            name="seth_message",
            data_type=DataType.TEXT,
            description="Test message for integration test",
            size_bytes=len(data),
            data_hash=data_hash
        )
        
        # Create the payload (what would go into OP_RETURN)
        payload = storage._create_payload(data, metadata)
        
        # Verify payload contains our data
        assert data in payload
        
        # Parse the payload back (simulating retrieval)
        retrieved_metadata, retrieved_data = storage._parse_payload(payload)
        
        # Verify retrieved data matches original
        assert retrieved_data == data
        assert retrieved_data.decode('utf-8') == self.TEST_MESSAGE
        assert retrieved_metadata.name == "seth_message"
        assert retrieved_metadata.data_hash == data_hash
        
        # Verify hash
        computed_hash = hashlib.sha256(retrieved_data).hexdigest()
        assert computed_hash == data_hash
    
    @pytest.mark.asyncio
    async def test_node_is_syncing(self, rpc_auth):
        """Verify the node is connected to the network."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                TERANODE_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getblockchaininfo",
                    "params": []
                },
                auth=rpc_auth,
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            result = data.get("result", {})
            
            # Node should be on teratestnet
            assert result.get("chain") == "teratestnet"
            
            # Best block hash should exist
            assert "bestblockhash" in result
            assert len(result["bestblockhash"]) == 64  # 32 bytes hex


class TestDataIntegrity:
    """Test data integrity features."""
    
    def test_hash_verification_success(self):
        """Test that valid data passes hash verification."""
        data = b"Seth is cool"
        data_hash = hashlib.sha256(data).hexdigest()
        
        # Verify
        computed = hashlib.sha256(data).hexdigest()
        assert computed == data_hash
    
    def test_hash_verification_failure(self):
        """Test that tampered data fails hash verification."""
        original_data = b"Seth is cool"
        tampered_data = b"Seth is not cool"
        
        original_hash = hashlib.sha256(original_data).hexdigest()
        tampered_hash = hashlib.sha256(tampered_data).hexdigest()
        
        assert original_hash != tampered_hash
    
    def test_compression_roundtrip(self):
        """Test data compression and decompression."""
        import zlib
        
        data = b"Seth is cool " * 100  # Repetitive data compresses well
        
        compressed = zlib.compress(data)
        decompressed = zlib.decompress(compressed)
        
        assert decompressed == data
        assert len(compressed) < len(data)  # Should be smaller


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
