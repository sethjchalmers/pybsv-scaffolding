"""
Tests for configuration module.
"""

import os
import pytest
from pathlib import Path


def test_config_from_env(monkeypatch):
    """Test loading configuration from environment."""
    # Set environment variables
    monkeypatch.setenv("TERANODE_RPC_HOST", "testhost")
    monkeypatch.setenv("TERANODE_RPC_PORT", "1234")
    monkeypatch.setenv("TERANODE_RPC_USER", "testuser")
    monkeypatch.setenv("TERANODE_RPC_PASSWORD", "testpass")
    monkeypatch.setenv("BSV_NETWORK", "testnet")
    
    # Import after setting env vars
    from bsv_llm.config import Config, reset_config
    
    reset_config()  # Clear any cached config
    
    config = Config.from_env()
    
    assert config.teranode.rpc_host == "testhost"
    assert config.teranode.rpc_port == 1234
    assert config.teranode.rpc_user == "testuser"
    assert config.teranode.rpc_password == "testpass"
    assert config.network == "testnet"


def test_config_validation():
    """Test configuration validation."""
    from bsv_llm.config import Config, TeranodeConfig
    
    # Config with missing credentials
    config = Config(
        teranode=TeranodeConfig(
            rpc_user="",
            rpc_password="",
        )
    )
    
    errors = config.validate()
    assert len(errors) == 2
    assert any("RPC_USER" in e for e in errors)
    assert any("RPC_PASSWORD" in e for e in errors)
    
    # Valid config
    config = Config(
        teranode=TeranodeConfig(
            rpc_user="user",
            rpc_password="pass",
        )
    )
    
    errors = config.validate()
    assert len(errors) == 0


def test_teranode_config_urls():
    """Test Teranode URL generation."""
    from bsv_llm.config import TeranodeConfig
    
    config = TeranodeConfig(
        rpc_host="localhost",
        rpc_port=9292,
        asset_host="localhost",
        asset_port=8000,
    )
    
    assert config.rpc_url == "http://localhost:9292"
    assert config.asset_url == "http://localhost:8000"
