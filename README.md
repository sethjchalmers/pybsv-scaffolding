# PyBSV Scaffolding

A starter project for building Python applications on the BSV blockchain using Teranode. Get up and running quickly with a pre-configured development environment.

## 🎯 Goals

- Provide a ready-to-use Python + BSV development environment
- Simplify local Teranode setup for testing and development
- Demonstrate common BSV patterns: storing and retrieving data on-chain
- Offer reusable modules for BSV client interactions

## 📋 Prerequisites

### Required
- **Python 3.10+** - [Download](https://python.org/)
- **Docker & Docker Compose** - [Download](https://docker.com/get-started)
- **Git** - [Download](https://git-scm.com/)

### Optional (for public node access)
- **ngrok** - [Setup Guide](https://ngrok.com/download)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Navigate to project
cd pybsv-scaffolding

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
copy .env.example .env

# Edit .env with your settings
# - Set RPC credentials
# - Add your private key (for testnet only!)
```

### 3. Start Teranode Teratestnet

```bash
# Clone Teratestnet helper (if not already done)
git clone https://github.com/bsv-blockchain/teranode-teratestnet.git

# Navigate and run setup
cd teranode-teratestnet
./start-teratestnet.sh  # Linux/Mac
# or on Windows with WSL2:
wsl ./start-teratestnet.sh
```

See [Teranode Setup](#teranode-setup) section for detailed instructions.

## 📁 Project Structure

```
pybsv-scaffolding/
├── src/
│   └── bsv_llm/
│       ├── __init__.py
│       ├── config.py          # Configuration management
│       ├── client.py          # BSV client wrapper
│       ├── storage.py         # Dataset storage on BSV
│       ├── retrieval.py       # Data retrieval from BSV
│       └── executor.py        # App execution framework
├── examples/
│   ├── store_data.py          # Example: Store data on BSV
│   ├── retrieve_data.py       # Example: Retrieve data from BSV
│   └── run_app.py             # Example: Run app consuming BSV data
├── tests/
│   └── ...
├── scripts/
│   ├── setup_teranode.ps1     # Windows setup script
│   └── check_node.py          # Node health check
├── teranode-teratestnet/      # Teranode Docker setup (cloned)
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

## 🔧 Teranode Setup

### Hardware Requirements
- **RAM:** 32GB+ (recommended)
- **Disk:** 40GB+ available space
- **OS:** Linux, macOS, or Windows with WSL2

### Setup Options

#### Option A: Using ngrok (No public IP required)

1. **Install ngrok:**
   ```bash
   # Download from https://ngrok.com/download
   # Authenticate with your token
   ngrok config add-authtoken YOUR_TOKEN
   ```

2. **Run setup script:**
   ```bash
   cd teranode-teratestnet
   ./start-teratestnet.sh
   ```

3. **Follow prompts:**
   - Enter your ngrok domain
   - Set RPC username/password
   - Optionally set a Miner Tag

#### Option B: Custom Domain (Public IP required)

```bash
cd teranode-teratestnet
./start-teratestnet.sh --no-ngrok
```

### Service Endpoints

| Service | Port | Description |
|---------|------|-------------|
| RPC | 9292 | JSON-RPC interface |
| Asset API | 8000 | Asset service API |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Monitoring dashboard |

### Useful Commands

```bash
# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop services
docker compose down

# Reset (start fresh)
./reset-data.sh
```

## 🔌 BSV Python SDK Usage

### Basic Transaction Example

```python
import asyncio
from bsv import PrivateKey, P2PKH, Transaction, TransactionInput, TransactionOutput

async def create_transaction():
    # Create a private key
    priv_key = PrivateKey('your_wif_key_here')
    
    # Build transaction
    tx = Transaction(
        inputs=[...],
        outputs=[...],
        version=1
    )
    
    tx.sign()
    await tx.broadcast()
    print(f"TX ID: {tx.txid()}")

asyncio.run(create_transaction())
```

### Store Data on BSV

```python
from bsv_llm.storage import DatasetStorage

storage = DatasetStorage()
txid = await storage.store_data(
    data=my_dataset_bytes,
    metadata={"name": "training_set_v1", "rows": 10000}
)
print(f"Stored with TXID: {txid}")
```

### Retrieve Data from BSV

```python
from bsv_llm.retrieval import DatasetRetrieval

retrieval = DatasetRetrieval()
data = await retrieval.get_data(txid="your_transaction_id")
```

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_storage.py
```

## 📚 Resources

- [BSV Python SDK Documentation](https://docs.bsvblockchain.org/guides/sdks/py)
- [Teranode Documentation](https://bsv-blockchain.github.io/teranode/)
- [Teratestnet Repository](https://github.com/bsv-blockchain/teranode-teratestnet)
- [BSV Discord](https://discord.com/invite/bsv)
- [Teratestnet Telegram](https://t.me/+FIcJEMznX0xiMzlk)

## 📝 License

MIT License - See LICENSE file for details.
