"""
BSV LLM - Blockchain-based LLM Training and Hosting

This package provides modules for storing datasets on BSV blockchain,
retrieving data, and running applications that consume blockchain data.
"""

from .client import BSVClient
from .config import Config, get_config

__version__ = "0.1.0"
__all__ = ["BSVClient", "Config", "get_config"]
