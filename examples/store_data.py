"""
Example: Store Data on BSV Blockchain

This example demonstrates how to store data on the BSV blockchain
using the bsv_llm storage module.

Prerequisites:
1. Teranode testnet running (docker compose up -d)
2. .env configured with RPC credentials
3. Funded wallet with testnet coins
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bsv_llm import BSVClient, get_config
from bsv_llm.storage import DatasetStorage, DataType
from bsv_llm.client import UTXOInfo


async def store_simple_data():
    """Example: Store simple text data."""
    print("\n=== Store Simple Text Data ===\n")
    
    config = get_config()
    storage = DatasetStorage()
    
    # Sample data to store
    data = "Hello, BSV Blockchain! This is a test message for the LLM training project."
    
    print(f"Data to store: {data}")
    print(f"Data size: {len(data)} bytes")
    print(f"Data hash: {BSVClient.hash_data(data.encode())}")
    
    # Note: In production, you would get a real UTXO from your wallet
    # For this demo, we'll show what the call would look like
    print("\n⚠️  To actually store data, you need:")
    print("   1. A funded testnet wallet")
    print("   2. A UTXO to spend for transaction fees")
    print("\nExample UTXO usage:")
    print("""
    utxo = UTXOInfo(
        txid="your_previous_txid",
        output_index=0,
        satoshis=10000,
        script="your_locking_script"
    )
    
    result = await storage.store(
        data=data,
        name="test_message_001",
        data_type=DataType.TEXT,
        description="Test message for BSV LLM project",
        source_utxo=utxo,
    )
    
    if result.success:
        print(f"Stored! TXID: {result.txid}")
    """)


async def store_json_data():
    """Example: Store JSON dataset metadata."""
    print("\n=== Store JSON Data ===\n")
    
    storage = DatasetStorage()
    
    # Sample dataset metadata
    dataset_info = {
        "name": "training_dataset_v1",
        "description": "Sample training data for language model",
        "version": "1.0.0",
        "records": 10000,
        "features": ["text", "label", "timestamp"],
        "created_by": "data_pipeline_001",
        "checksum": "sha256:abc123...",
    }
    
    print("Dataset metadata:")
    print(json.dumps(dataset_info, indent=2))
    
    print("\n⚠️  Call storage.store() with source_utxo to store on-chain")


async def store_model_weights_reference():
    """Example: Store a reference to model weights stored off-chain."""
    print("\n=== Store Model Weights Reference ===\n")
    
    storage = DatasetStorage()
    
    # For large files like model weights, store a hash reference
    # The actual weights can be stored on IPFS, S3, or other storage
    
    # Simulate model weights hash
    fake_weights = b"pretend these are 100MB of model weights..."
    weights_hash = BSVClient.hash_data(fake_weights)
    
    print(f"Model weights hash: {weights_hash}")
    print("External storage URL: ipfs://QmXxx...")
    
    print("\nExample reference storage:")
    print("""
    result = await storage.store_reference(
        data_hash=weights_hash,
        name="gpt_mini_v1_weights",
        data_type=DataType.MODEL_WEIGHTS,
        external_url="ipfs://QmXxxYyyZzz",
        source_utxo=utxo,
        description="GPT-Mini model weights v1.0",
        custom_metadata={
            "model_type": "transformer",
            "parameters": "125M",
            "training_data_txid": "abc123..."
        }
    )
    """)


async def main():
    """Run all examples."""
    print("=" * 60)
    print("BSV Data Storage Examples")
    print("=" * 60)
    
    # Check configuration
    config = get_config()
    errors = config.validate()
    
    if errors:
        print("\n⚠️  Configuration warnings:")
        for error in errors:
            print(f"   - {error}")
        print("\nCopy .env.example to .env and configure your settings.")
    
    await store_simple_data()
    await store_json_data()
    await store_model_weights_reference()
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Get testnet coins from a BSV testnet faucet")
    print("2. Configure your private key in .env")
    print("3. Run with actual UTXOs to store data on-chain")


if __name__ == "__main__":
    asyncio.run(main())
