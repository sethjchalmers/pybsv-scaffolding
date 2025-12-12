"""
Configuration management for BSV LLM.

Handles loading configuration from environment variables and .env files.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class TeranodeConfig:
    """Configuration for Teranode RPC and services."""
    rpc_host: str = "localhost"
    rpc_port: int = 9292
    rpc_user: str = ""
    rpc_password: str = ""
    asset_host: str = "localhost"
    asset_port: int = 8000
    
    @property
    def rpc_url(self) -> str:
        """Get the full RPC URL."""
        return f"http://{self.rpc_host}:{self.rpc_port}"
    
    @property
    def asset_url(self) -> str:
        """Get the full Asset service URL."""
        return f"http://{self.asset_host}:{self.asset_port}"


@dataclass
class Config:
    """Main configuration class for BSV LLM."""
    
    # Network configuration
    network: str = "teratestnet"  # teratestnet, testnet, mainnet
    
    # Teranode configuration
    teranode: TeranodeConfig = field(default_factory=TeranodeConfig)
    
    # Wallet configuration
    private_key: Optional[str] = None  # WIF format
    
    # Application settings
    debug: bool = False
    
    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Config":
        """
        Load configuration from environment variables.
        
        Args:
            env_file: Optional path to .env file. If not provided,
                     looks for .env in current directory and parents.
        
        Returns:
            Config instance with values from environment.
        """
        # Load .env file if specified or find one
        if env_file:
            load_dotenv(env_file)
        else:
            # Try to find .env file
            current = Path.cwd()
            while current != current.parent:
                env_path = current / ".env"
                if env_path.exists():
                    load_dotenv(env_path)
                    break
                current = current.parent
        
        # Build Teranode config
        teranode = TeranodeConfig(
            rpc_host=os.getenv("TERANODE_RPC_HOST", "localhost"),
            rpc_port=int(os.getenv("TERANODE_RPC_PORT", "9292")),
            rpc_user=os.getenv("TERANODE_RPC_USER", ""),
            rpc_password=os.getenv("TERANODE_RPC_PASSWORD", ""),
            asset_host=os.getenv("TERANODE_ASSET_HOST", "localhost"),
            asset_port=int(os.getenv("TERANODE_ASSET_PORT", "8000")),
        )
        
        # Build main config
        return cls(
            network=os.getenv("BSV_NETWORK", "teratestnet"),
            teranode=teranode,
            private_key=os.getenv("BSV_PRIVATE_KEY"),
            debug=os.getenv("DEBUG", "").lower() in ("true", "1", "yes"),
        )
    
    def validate(self) -> list[str]:
        """
        Validate the configuration.
        
        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []
        
        if not self.teranode.rpc_user:
            errors.append("TERANODE_RPC_USER is not set")
        
        if not self.teranode.rpc_password:
            errors.append("TERANODE_RPC_PASSWORD is not set")
        
        if self.network not in ("teratestnet", "testnet", "mainnet"):
            errors.append(f"Invalid network: {self.network}")
        
        return errors


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Loads from environment on first call.
    
    Returns:
        Config instance.
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
