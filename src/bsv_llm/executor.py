"""
Application Executor Module for BSV Blockchain.

Provides a framework for running applications that consume
data from the BSV blockchain, with full provenance tracking.
"""

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, Callable, TypeVar, Generic
from enum import Enum

from .client import BSVClient, UTXOInfo
from .storage import DatasetStorage, DataType, StorageResult
from .retrieval import DatasetRetrieval, RetrievalResult
from .config import Config, get_config


class ExecutionStatus(Enum):
    """Status of an execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionInput:
    """Input specification for an execution."""
    name: str
    txid: str  # Transaction ID containing input data
    data_type: DataType
    data_hash: Optional[str] = None  # For verification
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "txid": self.txid,
            "data_type": self.data_type.value,
            "data_hash": self.data_hash,
        }


@dataclass
class ExecutionOutput:
    """Output from an execution."""
    name: str
    data: bytes
    data_type: DataType
    txid: Optional[str] = None  # Populated after storing on-chain
    data_hash: str = ""
    
    def __post_init__(self):
        if not self.data_hash and self.data:
            self.data_hash = hashlib.sha256(self.data).hexdigest()
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "data_type": self.data_type.value,
            "txid": self.txid,
            "data_hash": self.data_hash,
            "size_bytes": len(self.data) if self.data else 0,
        }


@dataclass
class ExecutionRecord:
    """
    Complete record of an execution for provenance tracking.
    
    This captures all information needed to reproduce or verify
    an execution: inputs, outputs, code version, parameters, etc.
    """
    execution_id: str
    app_name: str
    app_version: str
    status: ExecutionStatus
    
    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Inputs and outputs
    inputs: list[ExecutionInput] = field(default_factory=list)
    outputs: list[ExecutionOutput] = field(default_factory=list)
    
    # Execution parameters
    parameters: dict = field(default_factory=dict)
    
    # Code reference (for reproducibility)
    code_hash: Optional[str] = None
    code_url: Optional[str] = None
    
    # Errors
    error: Optional[str] = None
    
    # Transaction ID of this record on-chain
    record_txid: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "parameters": self.parameters,
            "code_hash": self.code_hash,
            "code_url": self.code_url,
            "error": self.error,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


T = TypeVar('T')  # Output type


class BSVApp(ABC, Generic[T]):
    """
    Base class for BSV blockchain applications.
    
    Extend this class to create applications that:
    - Consume data from the blockchain
    - Process data with full provenance tracking
    - Store results back to the blockchain
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        config: Optional[Config] = None,
        code_url: Optional[str] = None,
    ):
        """
        Initialize a BSV application.
        
        Args:
            name: Application name
            version: Application version
            config: Configuration (uses global if not provided)
            code_url: URL to application source code (for provenance)
        """
        self.name = name
        self.version = version
        self.config = config or get_config()
        self.code_url = code_url
        
        self.client = BSVClient(self.config)
        self.storage = DatasetStorage(self.client, self.config)
        self.retrieval = DatasetRetrieval(self.client, self.config)
        
        self._execution_record: Optional[ExecutionRecord] = None
    
    @property
    def code_hash(self) -> Optional[str]:
        """
        Get hash of the application code for reproducibility.
        
        Override this to provide actual code hashing.
        """
        return None
    
    @abstractmethod
    async def process(self, inputs: dict[str, bytes], parameters: dict) -> T:
        """
        Process inputs and return result.
        
        This is the main processing logic. Override this method
        to implement your application.
        
        Args:
            inputs: Dictionary of input name -> data bytes
            parameters: Processing parameters
        
        Returns:
            Processing result (type depends on application)
        """
        pass
    
    @abstractmethod
    def prepare_output(self, result: T) -> list[ExecutionOutput]:
        """
        Prepare result for storage.
        
        Convert the processing result into outputs that can
        be stored on the blockchain.
        
        Args:
            result: Processing result
        
        Returns:
            List of outputs to store
        """
        pass
    
    async def load_inputs(
        self,
        input_specs: list[ExecutionInput]
    ) -> dict[str, bytes]:
        """
        Load input data from the blockchain.
        
        Args:
            input_specs: List of input specifications
        
        Returns:
            Dictionary of input name -> data bytes
        
        Raises:
            Exception: If any input fails to load or verify
        """
        inputs = {}
        
        for spec in input_specs:
            result = await self.retrieval.get(spec.txid, verify=True)
            
            if not result.success:
                raise Exception(f"Failed to load input '{spec.name}': {result.error}")
            
            # Verify hash if provided
            if spec.data_hash and result.data:
                actual_hash = hashlib.sha256(result.data).hexdigest()
                if actual_hash != spec.data_hash:
                    raise Exception(
                        f"Input '{spec.name}' hash mismatch: "
                        f"expected {spec.data_hash}, got {actual_hash}"
                    )
            
            inputs[spec.name] = result.data
        
        return inputs
    
    async def store_outputs(
        self,
        outputs: list[ExecutionOutput],
        source_utxo: UTXOInfo,
    ) -> list[ExecutionOutput]:
        """
        Store outputs to the blockchain.
        
        Args:
            outputs: Outputs to store
            source_utxo: UTXO to fund transactions
        
        Returns:
            Updated outputs with transaction IDs
        """
        stored_outputs = []
        
        for output in outputs:
            result = await self.storage.store(
                data=output.data,
                name=f"{self.name}/{output.name}",
                data_type=output.data_type,
                description=f"Output from {self.name} v{self.version}",
                source_utxo=source_utxo,
                custom_metadata={
                    "app_name": self.name,
                    "app_version": self.version,
                    "execution_id": self._execution_record.execution_id if self._execution_record else None,
                }
            )
            
            if result.success:
                output.txid = result.txid or (result.chunk_txids[0] if result.chunk_txids else None)
            else:
                raise Exception(f"Failed to store output '{output.name}': {result.error}")
            
            stored_outputs.append(output)
        
        return stored_outputs
    
    async def run(
        self,
        inputs: list[ExecutionInput],
        parameters: dict = None,
        source_utxo: Optional[UTXOInfo] = None,
        store_outputs: bool = True,
        store_record: bool = True,
    ) -> ExecutionRecord:
        """
        Run the application with full provenance tracking.
        
        Args:
            inputs: Input specifications
            parameters: Processing parameters
            source_utxo: UTXO for storing outputs (required if store_outputs=True)
            store_outputs: Whether to store outputs on-chain
            store_record: Whether to store execution record on-chain
        
        Returns:
            Execution record with all provenance information
        """
        import uuid
        
        parameters = parameters or {}
        
        # Initialize execution record
        self._execution_record = ExecutionRecord(
            execution_id=str(uuid.uuid4()),
            app_name=self.name,
            app_version=self.version,
            status=ExecutionStatus.PENDING,
            inputs=inputs,
            parameters=parameters,
            code_hash=self.code_hash,
            code_url=self.code_url,
        )
        
        try:
            # Start execution
            self._execution_record.status = ExecutionStatus.RUNNING
            self._execution_record.started_at = datetime.utcnow().isoformat()
            
            # Load inputs
            input_data = await self.load_inputs(inputs)
            
            # Process
            result = await self.process(input_data, parameters)
            
            # Prepare outputs
            outputs = self.prepare_output(result)
            
            # Store outputs if requested
            if store_outputs and source_utxo:
                outputs = await self.store_outputs(outputs, source_utxo)
            
            self._execution_record.outputs = outputs
            self._execution_record.status = ExecutionStatus.COMPLETED
            self._execution_record.completed_at = datetime.utcnow().isoformat()
            
            # Store execution record if requested
            if store_record and source_utxo:
                record_result = await self.storage.store(
                    data=self._execution_record.to_json(),
                    name=f"{self.name}/execution/{self._execution_record.execution_id}",
                    data_type=DataType.JSON,
                    description="Execution record",
                    source_utxo=source_utxo,
                )
                if record_result.success:
                    self._execution_record.record_txid = record_result.txid
            
        except Exception as e:
            self._execution_record.status = ExecutionStatus.FAILED
            self._execution_record.error = str(e)
            self._execution_record.completed_at = datetime.utcnow().isoformat()
        
        return self._execution_record


class SimpleFunctionApp(BSVApp[bytes]):
    """
    Simple function-based BSV application.
    
    Wraps a simple function as a BSV application with
    provenance tracking.
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        func: Callable[[dict[str, bytes], dict], bytes],
        output_type: DataType = DataType.RAW,
        **kwargs
    ):
        """
        Initialize a simple function app.
        
        Args:
            name: Application name
            version: Application version
            func: Processing function (inputs, params) -> bytes
            output_type: Type of output data
            **kwargs: Additional arguments for BSVApp
        """
        super().__init__(name, version, **kwargs)
        self.func = func
        self.output_type = output_type
    
    async def process(self, inputs: dict[str, bytes], parameters: dict) -> bytes:
        """Run the wrapped function."""
        result = self.func(inputs, parameters)
        
        # Handle async functions
        if asyncio.iscoroutine(result):
            result = await result
        
        return result
    
    def prepare_output(self, result: bytes) -> list[ExecutionOutput]:
        """Wrap result as single output."""
        return [
            ExecutionOutput(
                name="result",
                data=result,
                data_type=self.output_type,
            )
        ]
