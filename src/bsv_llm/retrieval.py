"""
Data Retrieval Module for BSV Blockchain.

Provides functionality to retrieve and verify data stored
on the BSV blockchain.
"""

import hashlib
import json
import zlib
from dataclasses import dataclass
from typing import Any

from .client import BSVClient
from .config import Config, get_config
from .storage import DataMetadata, DatasetStorage


@dataclass
class RetrievalResult:
    """Result of a data retrieval operation."""

    success: bool
    data: bytes | None = None
    metadata: DataMetadata | None = None
    error: str | None = None
    verified: bool = False

    def as_string(self) -> str | None:
        """Get data as UTF-8 string."""
        if self.data:
            return self.data.decode("utf-8")
        return None

    def as_json(self) -> Any | None:
        """Get data as parsed JSON."""
        if self.data:
            return json.loads(self.data.decode("utf-8"))
        return None


class DatasetRetrieval:
    """
    Retrieve datasets from the BSV blockchain.

    Supports:
    - Single transaction retrieval
    - Chunked data reassembly
    - Data verification via hash
    - Automatic decompression
    """

    def __init__(self, client: BSVClient | None = None, config: Config | None = None):
        """
        Initialize retrieval module.

        Args:
            client: BSV client instance. If not provided, creates one.
            config: Configuration. If not provided, uses global config.
        """
        self.config = config or get_config()
        self.client = client or BSVClient(self.config)

    def _parse_payload(self, payload: bytes) -> tuple[DataMetadata, bytes]:
        """
        Parse a storage payload.

        Args:
            payload: Raw payload from OP_RETURN

        Returns:
            Tuple of (metadata, data)

        Raises:
            ValueError: If payload format is invalid
        """
        # Check protocol prefix
        if not payload.startswith(DatasetStorage.PROTOCOL_PREFIX):
            raise ValueError("Invalid payload: missing protocol prefix")

        offset = len(DatasetStorage.PROTOCOL_PREFIX)

        # Read metadata length
        metadata_length = int.from_bytes(payload[offset : offset + 2], "big")
        offset += 2

        # Read metadata
        metadata_bytes = payload[offset : offset + metadata_length]
        metadata_dict = json.loads(metadata_bytes.decode("utf-8"))
        metadata = DataMetadata.from_dict(metadata_dict)
        offset += metadata_length

        # Rest is data
        data = payload[offset:]

        return metadata, data

    def _extract_op_return_data(self, tx_data: dict) -> bytes | None:
        """
        Extract OP_RETURN data from a transaction.

        Args:
            tx_data: Decoded transaction data

        Returns:
            OP_RETURN payload bytes, or None if not found
        """
        for vout in tx_data.get("vout", []):
            script_pub_key = vout.get("scriptPubKey", {})
            asm = script_pub_key.get("asm", "")

            # Look for OP_FALSE OP_RETURN pattern
            if "OP_FALSE OP_RETURN" in asm or asm.startswith("0 OP_RETURN"):
                # Extract hex data
                hex_data = script_pub_key.get("hex", "")
                if hex_data:
                    # Skip OP_FALSE (00) OP_RETURN (6a) and pushdata opcodes
                    # This is simplified - production code should parse properly
                    raw_bytes = bytes.fromhex(hex_data)
                    # Find the actual data after opcodes
                    # OP_FALSE = 0x00, OP_RETURN = 0x6a
                    if len(raw_bytes) > 2 and raw_bytes[0] == 0x00 and raw_bytes[1] == 0x6A:
                        # Next byte(s) are pushdata length
                        idx = 2
                        if raw_bytes[idx] < 0x4C:  # OP_PUSHDATA1
                            length = raw_bytes[idx]
                            idx += 1
                        elif raw_bytes[idx] == 0x4C:  # OP_PUSHDATA1
                            length = raw_bytes[idx + 1]
                            idx += 2
                        elif raw_bytes[idx] == 0x4D:  # OP_PUSHDATA2
                            length = int.from_bytes(raw_bytes[idx + 1 : idx + 3], "little")
                            idx += 3
                        elif raw_bytes[idx] == 0x4E:  # OP_PUSHDATA4
                            length = int.from_bytes(raw_bytes[idx + 1 : idx + 5], "little")
                            idx += 5
                        else:
                            continue

                        return raw_bytes[idx : idx + length]

        return None

    async def get(self, txid: str, verify: bool = True) -> RetrievalResult:
        """
        Retrieve data from a transaction.

        Args:
            txid: Transaction ID containing the data
            verify: Whether to verify data hash

        Returns:
            RetrievalResult with data and metadata
        """
        try:
            # Get the transaction
            tx_data = await self.client.get_raw_transaction(txid, verbose=True)

            # Extract OP_RETURN data
            payload = self._extract_op_return_data(tx_data)
            if not payload:
                return RetrievalResult(
                    success=False, error="No OP_RETURN data found in transaction"
                )

            # Parse payload
            try:
                metadata, data = self._parse_payload(payload)
            except ValueError as e:
                return RetrievalResult(success=False, error=f"Failed to parse payload: {e!s}")

            # Decompress if needed
            if metadata.compressed:
                try:
                    data = zlib.decompress(data)
                except zlib.error as e:
                    return RetrievalResult(success=False, error=f"Decompression failed: {e!s}")

            # Verify hash if requested
            verified = False
            if verify and metadata.data_hash:
                computed_hash = hashlib.sha256(data).hexdigest()
                verified = computed_hash == metadata.data_hash

                if not verified:
                    return RetrievalResult(
                        success=False,
                        data=data,
                        metadata=metadata,
                        error="Data hash verification failed",
                        verified=False,
                    )

            return RetrievalResult(success=True, data=data, metadata=metadata, verified=verified)

        except Exception as e:
            return RetrievalResult(success=False, error=str(e))

    async def get_chunked(self, chunk_txids: list[str], verify: bool = True) -> RetrievalResult:
        """
        Retrieve and reassemble chunked data.

        Args:
            chunk_txids: List of transaction IDs containing chunks (in order)
            verify: Whether to verify the final data hash

        Returns:
            RetrievalResult with reassembled data
        """
        chunks = []
        metadata = None
        expected_hash = None

        for i, txid in enumerate(chunk_txids):
            result = await self.get(txid, verify=False)

            if not result.success:
                return RetrievalResult(
                    success=False, error=f"Failed to retrieve chunk {i + 1}: {result.error}"
                )

            # Store metadata from first chunk
            if metadata is None:
                metadata = result.metadata
                expected_hash = result.metadata.data_hash if result.metadata else None

            chunks.append(result.data)

        # Reassemble data
        reassembled = b"".join(chunks)

        # Verify hash
        verified = False
        if verify and expected_hash:
            computed_hash = hashlib.sha256(reassembled).hexdigest()
            verified = computed_hash == expected_hash

            if not verified:
                return RetrievalResult(
                    success=False,
                    data=reassembled,
                    metadata=metadata,
                    error="Reassembled data hash verification failed",
                    verified=False,
                )

        return RetrievalResult(success=True, data=reassembled, metadata=metadata, verified=verified)

    async def get_by_hash(self, data_hash: str) -> RetrievalResult:
        """
        Retrieve data by its content hash.

        Note: This requires an indexing service to map hashes to txids.
        Currently returns an error - to be implemented with indexer.

        Args:
            data_hash: SHA256 hash of the data

        Returns:
            RetrievalResult
        """
        # TODO: Implement with indexer service
        return RetrievalResult(
            success=False, error="Hash-based lookup not yet implemented. Use txid instead."
        )

    async def verify(self, txid: str, expected_hash: str) -> bool:
        """
        Verify that data in a transaction matches expected hash.

        Args:
            txid: Transaction ID
            expected_hash: Expected SHA256 hash of data

        Returns:
            True if verification passes
        """
        result = await self.get(txid, verify=False)

        if not result.success or not result.data:
            return False

        computed_hash = hashlib.sha256(result.data).hexdigest()
        return computed_hash == expected_hash
