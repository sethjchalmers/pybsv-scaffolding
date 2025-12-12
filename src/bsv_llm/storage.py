"""
Dataset Storage Module for BSV Blockchain.

Provides functionality to store datasets and associated metadata
on the BSV blockchain for full traceability and provenance.
"""

import hashlib
import json
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .client import BSVClient, UTXOInfo
from .config import Config, get_config


class DataType(Enum):
    """Supported data types for storage."""

    RAW = "raw"  # Raw binary data
    JSON = "json"  # JSON data
    CSV = "csv"  # CSV data
    TEXT = "text"  # Plain text
    MODEL_WEIGHTS = "model_weights"  # ML model weights
    DATASET = "dataset"  # Training/inference dataset


@dataclass
class DataMetadata:
    """Metadata for stored data."""

    name: str
    data_type: DataType
    description: str = ""
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Data properties
    size_bytes: int = 0
    compressed: bool = False
    chunk_index: int | None = None
    total_chunks: int | None = None

    # Hash for verification
    data_hash: str = ""

    # Custom metadata
    custom: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "data_type": self.data_type.value,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "compressed": self.compressed,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "data_hash": self.data_hash,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataMetadata":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            data_type=DataType(data["data_type"]),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            size_bytes=data.get("size_bytes", 0),
            compressed=data.get("compressed", False),
            chunk_index=data.get("chunk_index"),
            total_chunks=data.get("total_chunks"),
            data_hash=data.get("data_hash", ""),
            custom=data.get("custom", {}),
        )

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class StorageResult:
    """Result of a storage operation."""

    success: bool
    txid: str | None = None
    metadata_txid: str | None = None
    chunk_txids: list[str] = field(default_factory=list)
    error: str | None = None
    data_hash: str = ""

    @property
    def all_txids(self) -> list[str]:
        """Get all transaction IDs involved in storage."""
        txids = []
        if self.metadata_txid:
            txids.append(self.metadata_txid)
        if self.txid:
            txids.append(self.txid)
        txids.extend(self.chunk_txids)
        return txids


class DatasetStorage:
    """
    Store datasets on the BSV blockchain.

    Supports:
    - Single transaction storage for small data
    - Chunked storage for larger datasets
    - Metadata storage for searchability
    - Compression for efficiency
    """

    # Protocol prefix for identifying our data
    PROTOCOL_PREFIX = b"BSVLLM"

    # Maximum data size per OP_RETURN output (~100KB is safe)
    MAX_CHUNK_SIZE = 90_000  # Leave room for overhead

    def __init__(self, client: BSVClient | None = None, config: Config | None = None):
        """
        Initialize storage module.

        Args:
            client: BSV client instance. If not provided, creates one.
            config: Configuration. If not provided, uses global config.
        """
        self.config = config or get_config()
        self.client = client or BSVClient(self.config)

    def _prepare_data(
        self, data: bytes | str | dict, data_type: DataType, compress: bool = True
    ) -> tuple[bytes, bool]:
        """
        Prepare data for storage.

        Args:
            data: Data to prepare
            data_type: Type of data
            compress: Whether to compress

        Returns:
            Tuple of (prepared bytes, was_compressed)
        """
        # Convert to bytes
        if isinstance(data, str):
            data_bytes = data.encode("utf-8")
        elif isinstance(data, dict):
            data_bytes = json.dumps(data).encode("utf-8")
        else:
            data_bytes = data

        # Compress if requested and beneficial
        if compress and len(data_bytes) > 1000:
            compressed = zlib.compress(data_bytes, level=9)
            if len(compressed) < len(data_bytes) * 0.9:  # Only if 10%+ savings
                return compressed, True

        return data_bytes, False

    def _create_storage_payload(self, data: bytes, metadata: DataMetadata) -> bytes:
        """
        Create the full payload for storage.

        Format: PROTOCOL_PREFIX | metadata_length(2 bytes) | metadata_json | data
        """
        metadata_bytes = metadata.to_json().encode("utf-8")
        metadata_length = len(metadata_bytes).to_bytes(2, "big")

        return self.PROTOCOL_PREFIX + metadata_length + metadata_bytes + data

    # Aliases for consistency
    _create_payload = _create_storage_payload

    def _parse_payload(self, payload: bytes) -> tuple[DataMetadata, bytes]:
        """
        Parse a storage payload back into metadata and data.

        Args:
            payload: Raw payload from OP_RETURN

        Returns:
            Tuple of (metadata, data)

        Raises:
            ValueError: If payload format is invalid
        """
        # Check protocol prefix
        if not payload.startswith(self.PROTOCOL_PREFIX):
            raise ValueError("Invalid payload: missing protocol prefix")

        offset = len(self.PROTOCOL_PREFIX)

        # Read metadata length (2 bytes, big endian)
        metadata_length = int.from_bytes(payload[offset : offset + 2], "big")
        offset += 2

        # Read metadata JSON
        metadata_bytes = payload[offset : offset + metadata_length]
        metadata_dict = json.loads(metadata_bytes.decode("utf-8"))
        metadata = DataMetadata.from_dict(metadata_dict)
        offset += metadata_length

        # Rest is data
        data = payload[offset:]

        return metadata, data

    def _chunk_data(self, data: bytes) -> list[bytes]:
        """
        Split data into chunks for multi-transaction storage.

        Args:
            data: Data to chunk

        Returns:
            List of data chunks
        """
        chunks = []
        for i in range(0, len(data), self.MAX_CHUNK_SIZE):
            chunks.append(data[i : i + self.MAX_CHUNK_SIZE])
        return chunks

    async def store(
        self,
        data: bytes | str | dict,
        name: str,
        data_type: DataType = DataType.RAW,
        description: str = "",
        source_utxo: UTXOInfo | None = None,
        compress: bool = True,
        custom_metadata: dict | None = None,
    ) -> StorageResult:
        """
        Store data on the BSV blockchain.

        Args:
            data: Data to store
            name: Name/identifier for the data
            data_type: Type of data being stored
            description: Human-readable description
            source_utxo: UTXO to fund the transaction(s)
            compress: Whether to compress data
            custom_metadata: Additional metadata to include

        Returns:
            StorageResult with transaction IDs and status
        """
        try:
            # Prepare the data
            prepared_data, was_compressed = self._prepare_data(data, data_type, compress)

            # Calculate hash of original data
            if isinstance(data, bytes):
                original_data = data
            elif isinstance(data, str):
                original_data = data.encode("utf-8")
            else:
                original_data = json.dumps(data).encode("utf-8")
            data_hash = hashlib.sha256(original_data).hexdigest()

            # Create metadata
            metadata = DataMetadata(
                name=name,
                data_type=data_type,
                description=description,
                size_bytes=len(original_data),
                compressed=was_compressed,
                data_hash=data_hash,
                custom=custom_metadata or {},
            )

            # Create full payload
            payload = self._create_storage_payload(prepared_data, metadata)

            # Check if chunking is needed
            if len(payload) <= self.MAX_CHUNK_SIZE:
                # Single transaction storage
                if source_utxo is None:
                    return StorageResult(
                        success=False,
                        error="Source UTXO required for transaction. Please fund your wallet.",
                        data_hash=data_hash,
                    )

                txid = await self.client.store_data(payload, source_utxo)

                return StorageResult(
                    success=True,
                    txid=txid,
                    data_hash=data_hash,
                )
            else:
                # Multi-transaction (chunked) storage
                return await self._store_chunked(prepared_data, metadata, source_utxo, data_hash)

        except Exception as e:
            return StorageResult(
                success=False,
                error=str(e),
            )

    async def _store_chunked(
        self,
        data: bytes,
        metadata: DataMetadata,
        source_utxo: UTXOInfo | None,
        data_hash: str,
    ) -> StorageResult:
        """
        Store large data across multiple transactions.

        Args:
            data: Prepared data to store
            metadata: Base metadata
            source_utxo: Initial funding UTXO
            data_hash: Hash of original data

        Returns:
            StorageResult with all transaction IDs
        """
        if source_utxo is None:
            return StorageResult(
                success=False,
                error="Source UTXO required for chunked storage",
                data_hash=data_hash,
            )

        chunks = self._chunk_data(data)
        total_chunks = len(chunks)
        chunk_txids = []

        # Update metadata for chunked storage
        metadata.total_chunks = total_chunks

        # Store each chunk
        # Note: In production, you'd chain UTXOs from previous transactions
        for i, chunk in enumerate(chunks):
            chunk_metadata = DataMetadata(
                name=metadata.name,
                data_type=metadata.data_type,
                description=f"Chunk {i+1}/{total_chunks}",
                size_bytes=len(chunk),
                compressed=metadata.compressed,
                chunk_index=i,
                total_chunks=total_chunks,
                data_hash=data_hash,
                custom=metadata.custom,
            )

            chunk_payload = self._create_storage_payload(chunk, chunk_metadata)

            # For now, we need a UTXO for each chunk
            # In production, use the change output from previous tx
            try:
                txid = await self.client.store_data(chunk_payload, source_utxo)
                chunk_txids.append(txid)
            except Exception as e:
                return StorageResult(
                    success=False,
                    chunk_txids=chunk_txids,
                    error=f"Failed on chunk {i+1}: {e!s}",
                    data_hash=data_hash,
                )

        return StorageResult(
            success=True,
            chunk_txids=chunk_txids,
            data_hash=data_hash,
        )

    async def store_reference(
        self,
        data_hash: str,
        name: str,
        data_type: DataType,
        external_url: str,
        source_utxo: UTXOInfo,
        description: str = "",
        custom_metadata: dict | None = None,
    ) -> StorageResult:
        """
        Store a reference to data stored elsewhere.

        Useful for large datasets that can't be stored on-chain.
        The hash ensures data integrity can be verified.

        Args:
            data_hash: SHA256 hash of the data
            name: Name/identifier
            data_type: Type of referenced data
            external_url: URL where data is stored
            source_utxo: UTXO to fund transaction
            description: Description
            custom_metadata: Additional metadata

        Returns:
            StorageResult with transaction ID
        """
        reference_data = {
            "type": "reference",
            "hash": data_hash,
            "url": external_url,
        }

        custom = custom_metadata or {}
        custom["reference"] = True
        custom["external_url"] = external_url

        return await self.store(
            data=json.dumps(reference_data),
            name=name,
            data_type=data_type,
            description=description,
            source_utxo=source_utxo,
            compress=False,
            custom_metadata=custom,
        )
