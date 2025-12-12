"""
BSV LLM - Blockchain-based LLM Training and Hosting

This package provides modules for storing datasets on BSV blockchain,
retrieving data, and running applications that consume blockchain data.
"""

from .config import Config, get_config
from .client import BSVClient

__version__ = "0.1.0"
__all__ = ["Config", "get_config", "BSVClient"]
