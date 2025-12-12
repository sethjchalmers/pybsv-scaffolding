"""
Example: Run BSV Applications with Provenance

This example demonstrates how to create and run applications
that consume blockchain data with full provenance tracking.

Prerequisites:
1. Teranode testnet running (docker compose up -d)
2. .env configured with RPC credentials
3. Input data already stored on-chain
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bsv_llm import get_config
from bsv_llm.executor import (
    BSVApp,
    ExecutionInput,
    ExecutionOutput,
    ExecutionRecord,
    SimpleFunctionApp,
)
from bsv_llm.storage import DataType


# Example 1: Simple function-based app
def word_count_processor(inputs: dict[str, bytes], params: dict) -> bytes:
    """
    Simple word count processor.

    Takes text input and returns word count statistics.
    """
    text = inputs.get("text", b"").decode("utf-8")

    # Process
    words = text.split()
    word_count = len(words)
    char_count = len(text)
    unique_words = len(set(words))

    # Return result as JSON
    result = {
        "word_count": word_count,
        "char_count": char_count,
        "unique_words": unique_words,
        "avg_word_length": round(char_count / word_count, 2) if word_count > 0 else 0,
    }

    return json.dumps(result).encode("utf-8")


# Example 2: Custom BSV application class
class DataTransformApp(BSVApp[dict]):
    """
    Custom data transformation application.

    Demonstrates a more complex application with multiple
    inputs and outputs.
    """

    def __init__(self):
        super().__init__(
            name="DataTransformApp",
            version="1.0.0",
            code_url="https://github.com/yourrepo/transform_app",
        )

    async def process(self, inputs: dict[str, bytes], parameters: dict) -> dict:
        """
        Process input data according to transformation rules.
        """
        results = {}

        # Get transformation mode
        mode = parameters.get("mode", "uppercase")

        for name, data in inputs.items():
            try:
                text = data.decode("utf-8")

                if mode == "uppercase":
                    results[name] = text.upper()
                elif mode == "lowercase":
                    results[name] = text.lower()
                elif mode == "reverse":
                    results[name] = text[::-1]
                elif mode == "hash":
                    results[name] = hashlib.sha256(data).hexdigest()
                else:
                    results[name] = text

            except Exception as e:
                results[name] = f"Error: {e!s}"

        return results

    def prepare_output(self, result: dict) -> list[ExecutionOutput]:
        """
        Prepare transformation results as outputs.
        """
        outputs = []

        for name, value in result.items():
            if isinstance(value, str):
                data = value.encode("utf-8")
            else:
                data = json.dumps(value).encode("utf-8")

            outputs.append(
                ExecutionOutput(
                    name=f"transformed_{name}",
                    data=data,
                    data_type=DataType.TEXT,
                )
            )

        return outputs


async def demo_simple_app():
    """Demo the simple function-based app."""
    print("\n=== Demo: Simple Function App ===\n")

    # Create the app
    app = SimpleFunctionApp(
        name="WordCounter",
        version="1.0.0",
        func=word_count_processor,
        output_type=DataType.JSON,
    )

    print(f"App: {app.name} v{app.version}")

    # In a real scenario, inputs would come from blockchain
    # Here we simulate the execution
    sample_text = """
    The BSV blockchain enables applications to store and process
    data with full transparency and traceability. Every piece of
    data, every computation, and every result can be verified
    independently by anyone.
    """.strip()

    print("\nSample input text:")
    print(f"  {sample_text[:100]}...")

    # Process directly (without blockchain storage)
    result = word_count_processor({"text": sample_text.encode("utf-8")}, {})

    print("\nProcessing result:")
    print(json.dumps(json.loads(result), indent=2))

    print("\n⚠️  To run with full provenance:")
    print("""
    # Define inputs from blockchain
    inputs = [
        ExecutionInput(
            name="text",
            txid="your_input_txid",
            data_type=DataType.TEXT,
        )
    ]

    # Run with provenance tracking
    record = await app.run(
        inputs=inputs,
        parameters={},
        source_utxo=utxo,  # For storing outputs
        store_outputs=True,
        store_record=True,
    )

    print(f"Execution ID: {record.execution_id}")
    print(f"Output TXID: {record.outputs[0].txid}")
    print(f"Record TXID: {record.record_txid}")
    """)


async def demo_custom_app():
    """Demo the custom application class."""
    print("\n=== Demo: Custom Transform App ===\n")

    # Create the app
    app = DataTransformApp()

    print(f"App: {app.name} v{app.version}")
    print(f"Code URL: {app.code_url}")

    # Simulate processing
    inputs = {
        "document1": b"Hello BSV Blockchain!",
        "document2": b"Data provenance matters.",
    }

    parameters = {"mode": "uppercase"}

    print("\nInputs:")
    for name, data in inputs.items():
        print(f"  {name}: {data.decode()}")

    print(f"\nParameters: {parameters}")

    # Process
    result = await app.process(inputs, parameters)

    print("\nTransformation result:")
    for name, value in result.items():
        print(f"  {name}: {value}")

    # Prepare outputs
    outputs = app.prepare_output(result)

    print("\nPrepared outputs:")
    for output in outputs:
        print(f"  {output.name}:")
        print(f"    Type: {output.data_type.value}")
        print(f"    Hash: {output.data_hash}")


async def demo_execution_record():
    """Demo the execution record structure."""
    print("\n=== Demo: Execution Record ===\n")

    # Create a sample execution record
    from bsv_llm.executor import ExecutionStatus

    record = ExecutionRecord(
        execution_id="exec_12345",
        app_name="DataProcessor",
        app_version="1.0.0",
        status=ExecutionStatus.COMPLETED,
        started_at="2024-01-15T10:00:00Z",
        completed_at="2024-01-15T10:00:05Z",
        inputs=[
            ExecutionInput(
                name="training_data",
                txid="abc123...",
                data_type=DataType.DATASET,
                data_hash="sha256:def456...",
            )
        ],
        outputs=[
            ExecutionOutput(
                name="processed_data",
                data=b"sample output",
                data_type=DataType.JSON,
                txid="ghi789...",
            )
        ],
        parameters={
            "batch_size": 32,
            "epochs": 10,
        },
        code_hash="sha256:abc...",
        code_url="https://github.com/repo/app",
    )

    print("Execution Record (stored on-chain for provenance):")
    print(record.to_json())

    print("\nThis record captures:")
    print("  • What inputs were used (with txids)")
    print("  • What parameters were set")
    print("  • What outputs were produced")
    print("  • What code version ran")
    print("  • When it ran")
    print("\nAnyone can verify the entire pipeline!")


async def main():
    """Run application examples."""
    print("=" * 60)
    print("BSV Application Execution Examples")
    print("=" * 60)

    # Check configuration
    config = get_config()
    errors = config.validate()

    if errors:
        print("\n⚠️  Configuration warnings:")
        for error in errors:
            print(f"   - {error}")
        print("\nCopy .env.example to .env and configure your settings.")

    await demo_simple_app()
    await demo_custom_app()
    await demo_execution_record()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nKey concepts demonstrated:")
    print("  1. Simple function wrapping with SimpleFunctionApp")
    print("  2. Custom applications by extending BSVApp")
    print("  3. Execution records for full provenance")
    print("\nAll executions create an auditable trail on the blockchain!")


if __name__ == "__main__":
    asyncio.run(main())
