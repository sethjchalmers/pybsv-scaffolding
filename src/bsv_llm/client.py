"""
BSV Client wrapper for interacting with the blockchain.

Provides a high-level interface for BSV operations including
transaction creation, signing, and broadcasting.
"""

import asyncio
import hashlib
from typing import Optional, Any
from dataclasses import dataclass

import httpx
from bsv import PrivateKey, P2PKH, Transaction, TransactionInput, TransactionOutput

from .config import Config, get_config


@dataclass
class UTXOInfo:
    """Information about an unspent transaction output."""
    txid: str
    output_index: int
    satoshis: int
    script: str
    
    @property
    def outpoint(self) -> str:
        """Get outpoint in txid:vout format."""
        return f"{self.txid}:{self.output_index}"


class BSVClient:
    """
    High-level BSV blockchain client.
    
    Wraps the BSV SDK with configuration management and
    Teranode-specific functionality.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize BSV client.
        
        Args:
            config: Configuration instance. If not provided, uses global config.
        """
        self.config = config or get_config()
        self._private_key: Optional[PrivateKey] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def private_key(self) -> Optional[PrivateKey]:
        """Get the private key instance, loading from config if needed."""
        if self._private_key is None and self.config.private_key:
            self._private_key = PrivateKey(self.config.private_key)
        return self._private_key
    
    @property
    def address(self) -> Optional[str]:
        """Get the address associated with the private key."""
        if self.private_key:
            return self.private_key.address()
        return None
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for RPC calls."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def rpc_call(self, method: str, params: list = None) -> Any:
        """
        Make an RPC call to Teranode.
        
        Args:
            method: RPC method name
            params: Method parameters
        
        Returns:
            RPC result data
        
        Raises:
            Exception: If RPC call fails
        """
        params = params or []
        client = await self._get_http_client()
        
        response = await client.post(
            self.config.teranode.rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params
            },
            auth=(
                self.config.teranode.rpc_user,
                self.config.teranode.rpc_password
            ),
            headers={"Content-Type": "application/json"}
        )
        
        response.raise_for_status()
        data = response.json()
        
        if "error" in data and data["error"]:
            raise Exception(f"RPC Error: {data['error']}")
        
        return data.get("result")
    
    async def get_info(self) -> dict:
        """
        Get node information.
        
        Returns:
            Node info dict with version, blocks, etc.
        """
        return await self.rpc_call("getinfo")
    
    async def get_block_count(self) -> int:
        """
        Get current block height.
        
        Returns:
            Block count/height
        """
        return await self.rpc_call("getblockcount")
    
    async def get_raw_transaction(self, txid: str, verbose: bool = False) -> Any:
        """
        Get a raw transaction by ID.
        
        Args:
            txid: Transaction ID
            verbose: If True, return decoded transaction
        
        Returns:
            Raw transaction hex or decoded dict
        """
        return await self.rpc_call("getrawtransaction", [txid, verbose])
    
    async def send_raw_transaction(self, tx_hex: str) -> str:
        """
        Broadcast a raw transaction.
        
        Args:
            tx_hex: Transaction in hex format
        
        Returns:
            Transaction ID
        """
        return await self.rpc_call("sendrawtransaction", [tx_hex])
    
    async def get_utxos(self, address: str = None) -> list[UTXOInfo]:
        """
        Get unspent transaction outputs for an address.
        
        Args:
            address: Address to query. If not provided, uses client's address.
        
        Returns:
            List of UTXOInfo objects
        
        Note:
            This is a placeholder - actual implementation depends on
            available RPC methods or indexer services.
        """
        address = address or self.address
        if not address:
            raise ValueError("No address provided and no private key configured")
        
        # TODO: Implement actual UTXO lookup
        # This might require:
        # 1. Using an indexer service
        # 2. Using specific Teranode RPC methods
        # 3. Using the Asset server API
        
        # For now, return empty list - user should fund manually
        return []
    
    def create_op_return_output(self, data: bytes) -> TransactionOutput:
        """
        Create an OP_RETURN output for storing data.
        
        Args:
            data: Data to embed in the output
        
        Returns:
            TransactionOutput with OP_RETURN script
        """
        from bsv import Script, OpCode
        
        # Build OP_RETURN script: OP_FALSE OP_RETURN <data>
        script = Script()
        script.write_op_code(OpCode.OP_FALSE)
        script.write_op_code(OpCode.OP_RETURN)
        script.write_push_data(data)
        
        return TransactionOutput(
            locking_script=script,
            satoshis=0
        )
    
    async def store_data(
        self,
        data: bytes,
        source_utxo: UTXOInfo,
        change_address: str = None
    ) -> str:
        """
        Store data on the blockchain using OP_RETURN.
        
        Args:
            data: Data to store (max ~100KB per output)
            source_utxo: UTXO to spend for transaction fees
            change_address: Address for change. If not provided, uses client's address.
        
        Returns:
            Transaction ID
        
        Raises:
            ValueError: If no private key or insufficient funds
        """
        if not self.private_key:
            raise ValueError("Private key required to sign transactions")
        
        change_address = change_address or self.address
        
        # Get source transaction
        source_tx_hex = await self.get_raw_transaction(source_utxo.txid)
        source_tx = Transaction.from_hex(source_tx_hex)
        
        # Create input
        tx_input = TransactionInput(
            source_transaction=source_tx,
            source_txid=source_utxo.txid,
            source_output_index=source_utxo.output_index,
            unlocking_script_template=P2PKH().unlock(self.private_key),
        )
        
        # Create outputs
        outputs = []
        
        # OP_RETURN output with data
        outputs.append(self.create_op_return_output(data))
        
        # Change output
        outputs.append(TransactionOutput(
            locking_script=P2PKH().lock(change_address),
            change=True
        ))
        
        # Build transaction
        tx = Transaction([tx_input], outputs, version=1)
        
        # Calculate fee and sign
        tx.fee()
        tx.sign()
        
        # Broadcast
        txid = await self.send_raw_transaction(tx.hex())
        
        return txid
    
    @staticmethod
    def hash_data(data: bytes) -> str:
        """
        Calculate SHA256 hash of data.
        
        Useful for creating data references that can be stored
        on-chain while data is stored elsewhere.
        
        Args:
            data: Data to hash
        
        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(data).hexdigest()
