"""
Example: Retrieve Data from BSV Blockchain

This example demonstrates how to retrieve and verify data
stored on the BSV blockchain using the bsv_llm retrieval module.

Prerequisites:
1. Teranode testnet running (docker compose up -d)
2. .env configured with RPC credentials
3. Valid transaction ID containing stored data
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bsv_llm import get_config
from bsv_llm.retrieval import DatasetRetrieval


async def retrieve_by_txid(txid: str):
    """Example: Retrieve data by transaction ID."""
    print("\n=== Retrieve Data by TXID ===\n")
    print(f"Transaction ID: {txid}")

    retrieval = DatasetRetrieval()

    # Retrieve data
    result = await retrieval.get(txid, verify=True)

    if result.success:
        print("\n✓ Data retrieved successfully!")
        print(f"  Verified: {result.verified}")

        if result.metadata:
            print("\nMetadata:")
            print(f"  Name: {result.metadata.name}")
            print(f"  Type: {result.metadata.data_type.value}")
            print(f"  Size: {result.metadata.size_bytes} bytes")
            print(f"  Compressed: {result.metadata.compressed}")
            print(f"  Hash: {result.metadata.data_hash}")

            if result.metadata.custom:
                print(f"  Custom: {result.metadata.custom}")

        if result.data:
            print("\nData preview (first 200 chars):")
            try:
                text = result.data.decode("utf-8")[:200]
                print(f"  {text}...")
            except UnicodeDecodeError:
                print(f"  [Binary data: {len(result.data)} bytes]")
    else:
        print(f"\n✗ Retrieval failed: {result.error}")

    return result


async def verify_data_integrity(txid: str, expected_hash: str):
    """Example: Verify data integrity by hash."""
    print("\n=== Verify Data Integrity ===\n")
    print(f"Transaction ID: {txid}")
    print(f"Expected hash: {expected_hash}")

    retrieval = DatasetRetrieval()

    is_valid = await retrieval.verify(txid, expected_hash)

    if is_valid:
        print("\n✓ Data integrity verified!")
    else:
        print("\n✗ Data integrity check failed!")

    return is_valid


async def retrieve_chunked_data(chunk_txids: list[str]):
    """Example: Retrieve and reassemble chunked data."""
    print("\n=== Retrieve Chunked Data ===\n")
    print(f"Number of chunks: {len(chunk_txids)}")

    retrieval = DatasetRetrieval()

    result = await retrieval.get_chunked(chunk_txids, verify=True)

    if result.success:
        print("\n✓ Chunked data reassembled successfully!")
        print(f"  Total size: {len(result.data)} bytes")
        print(f"  Verified: {result.verified}")
    else:
        print(f"\n✗ Chunk retrieval failed: {result.error}")

    return result


async def demo_retrieval_flow():
    """Demo the retrieval flow with mock data."""
    print("\n=== Demo Retrieval Flow ===\n")

    # In a real scenario, you would use actual txids from stored data
    print("To retrieve real data, you need:")
    print("1. A transaction ID from a previous store operation")
    print("2. The Teranode testnet running and synced")
    print()
    print("Example usage:")
    print("""
    # Single transaction retrieval
    result = await retrieval.get("your_txid_here")

    if result.success:
        # Access raw data
        raw_data = result.data

        # Or as string
        text = result.as_string()

        # Or as JSON
        json_data = result.as_json()

        # Check metadata
        print(f"Name: {result.metadata.name}")
        print(f"Hash: {result.metadata.data_hash}")

    # Chunked data retrieval
    result = await retrieval.get_chunked([
        "chunk1_txid",
        "chunk2_txid",
        "chunk3_txid",
    ])

    # Verify specific data
    is_valid = await retrieval.verify(
        "txid",
        "expected_sha256_hash"
    )
    """)


async def main():
    """Run retrieval examples."""
    print("=" * 60)
    print("BSV Data Retrieval Examples")
    print("=" * 60)

    # Check configuration
    config = get_config()
    errors = config.validate()

    if errors:
        print("\n⚠️  Configuration warnings:")
        for error in errors:
            print(f"   - {error}")
        print("\nCopy .env.example to .env and configure your settings.")

    # Demo the flow
    await demo_retrieval_flow()

    # If you have actual txids, uncomment these:
    # await retrieve_by_txid("your_actual_txid")
    # await verify_data_integrity("your_txid", "expected_hash")
    # await retrieve_chunked_data(["chunk1_txid", "chunk2_txid"])

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
