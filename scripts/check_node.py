"""
Node Health Check Script

Verifies connectivity to Teranode services and displays status.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

console = Console()


async def check_rpc_service(host: str, port: int, user: str, password: str) -> dict:
    """Check RPC service health."""
    result = {"name": "RPC Service", "port": port, "status": "Unknown", "details": ""}
    
    try:
        url = f"http://{host}:{port}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try a simple RPC call
            response = await client.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getinfo",
                    "params": []
                },
                auth=(user, password),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result["status"] = "✓ Connected"
                data = response.json()
                if "result" in data:
                    result["details"] = f"Block height: {data['result'].get('blocks', 'N/A')}"
                elif "error" in data:
                    result["status"] = "⚠ Error"
                    result["details"] = data["error"].get("message", "Unknown error")
            elif response.status_code == 401:
                result["status"] = "✗ Auth Failed"
                result["details"] = "Invalid RPC credentials"
            else:
                result["status"] = f"⚠ HTTP {response.status_code}"
                
    except httpx.ConnectError:
        result["status"] = "✗ Not Running"
        result["details"] = "Connection refused"
    except httpx.TimeoutException:
        result["status"] = "✗ Timeout"
        result["details"] = "Service not responding"
    except Exception as e:
        result["status"] = "✗ Error"
        result["details"] = str(e)
    
    return result


async def check_asset_service(host: str, port: int) -> dict:
    """Check Asset service health."""
    result = {"name": "Asset Service", "port": port, "status": "Unknown", "details": ""}
    
    try:
        url = f"http://{host}:{port}/api/v1/health"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                result["status"] = "✓ Connected"
                result["details"] = "Healthy"
            elif response.status_code == 404:
                # Try base URL
                response = await client.get(f"http://{host}:{port}/")
                if response.status_code in [200, 404]:
                    result["status"] = "⚠ Running"
                    result["details"] = "Service active (no health endpoint)"
            else:
                result["status"] = f"⚠ HTTP {response.status_code}"
                
    except httpx.ConnectError:
        result["status"] = "✗ Not Running"
        result["details"] = "Connection refused"
    except httpx.TimeoutException:
        result["status"] = "✗ Timeout"
        result["details"] = "Service not responding"
    except Exception as e:
        result["status"] = "✗ Error"
        result["details"] = str(e)
    
    return result


async def check_prometheus(host: str, port: int = 9090) -> dict:
    """Check Prometheus metrics service."""
    result = {"name": "Prometheus", "port": port, "status": "Unknown", "details": ""}
    
    try:
        url = f"http://{host}:{port}/-/healthy"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                result["status"] = "✓ Connected"
                result["details"] = "Healthy"
            else:
                result["status"] = f"⚠ HTTP {response.status_code}"
                
    except httpx.ConnectError:
        result["status"] = "✗ Not Running"
        result["details"] = "Connection refused"
    except Exception as e:
        result["status"] = "✗ Error"
        result["details"] = str(e)
    
    return result


async def check_grafana(host: str, port: int = 3005) -> dict:
    """Check Grafana dashboard service."""
    result = {"name": "Grafana", "port": port, "status": "Unknown", "details": ""}
    
    try:
        url = f"http://{host}:{port}/api/health"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                result["status"] = "✓ Connected"
                data = response.json()
                result["details"] = f"Database: {data.get('database', 'N/A')}"
            else:
                result["status"] = f"⚠ HTTP {response.status_code}"
                
    except httpx.ConnectError:
        result["status"] = "✗ Not Running"
        result["details"] = "Connection refused"
    except Exception as e:
        result["status"] = "✗ Error"
        result["details"] = str(e)
    
    return result


async def main():
    """Run all health checks."""
    console.print(Panel.fit(
        "[bold cyan]BSV Teranode Health Check[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # Get configuration from environment
    host = os.getenv("TERANODE_RPC_HOST", "localhost")
    rpc_port = int(os.getenv("TERANODE_RPC_PORT", "9292"))
    rpc_user = os.getenv("TERANODE_RPC_USER", "")
    rpc_pass = os.getenv("TERANODE_RPC_PASSWORD", "")
    asset_port = int(os.getenv("TERANODE_ASSET_PORT", "8000"))
    
    console.print(f"[dim]Checking services at: {host}[/dim]")
    console.print()
    
    # Run all checks
    results = await asyncio.gather(
        check_rpc_service(host, rpc_port, rpc_user, rpc_pass),
        check_asset_service(host, asset_port),
        check_prometheus(host),
        check_grafana(host),
    )
    
    # Display results in a table
    table = Table(title="Service Status", show_header=True, header_style="bold magenta")
    table.add_column("Service", style="cyan")
    table.add_column("Port", justify="right")
    table.add_column("Status")
    table.add_column("Details", style="dim")
    
    all_ok = True
    for result in results:
        status_style = "green" if "✓" in result["status"] else "yellow" if "⚠" in result["status"] else "red"
        if "✗" in result["status"]:
            all_ok = False
        table.add_row(
            result["name"],
            str(result["port"]),
            f"[{status_style}]{result['status']}[/{status_style}]",
            result["details"]
        )
    
    console.print(table)
    console.print()
    
    # Summary
    if all_ok:
        console.print("[bold green]✓ All services are running![/bold green]")
    else:
        console.print("[bold yellow]⚠ Some services are not available.[/bold yellow]")
        console.print()
        console.print("[dim]Tips:[/dim]")
        console.print("  • Make sure Docker containers are running: docker compose ps")
        console.print("  • Check container logs: docker compose logs")
        console.print("  • Verify .env file has correct settings")
    
    # Check if .env exists and has credentials
    if not rpc_user or not rpc_pass:
        console.print()
        console.print("[bold red]⚠ RPC credentials not configured![/bold red]")
        console.print("  Copy .env.example to .env and set TERANODE_RPC_USER and TERANODE_RPC_PASSWORD")


if __name__ == "__main__":
    asyncio.run(main())
