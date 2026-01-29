# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp>=1.0.0",
#     "httpx>=0.27.0",
#     "python-dotenv>=1.0.0",
# ]
# ///

import json
from mcp.server.fastmcp import FastMCP
from src.service import OrchestratorClient, CONFIG

# -----------------------------------------------------------------------------
# Client cache (one client per account/tenant, shared token)
# -----------------------------------------------------------------------------

_CLIENTS: dict[str, OrchestratorClient] = {}


async def get_client(account: str, tenant: str) -> OrchestratorClient:
    """
    Get or create an OrchestratorClient for a specific account/tenant.
    Clients are cached per account/tenant combination.
    """
    key = f"{account}/{tenant}"
    
    if key not in _CLIENTS:
        client = OrchestratorClient(account=account, tenant=tenant)
        await client.authenticate()
        _CLIENTS[key] = client

    return _CLIENTS[key]


def get_available_accounts() -> list[str]:
    """Get list of configured account names"""
    return list(CONFIG["accounts"].keys())


def get_available_tenants(account: str) -> list[str]:
    """Get list of configured tenants for an account"""
    if account not in CONFIG["accounts"]:
        return []
    return list(CONFIG["accounts"][account]["tenants"].keys())


# -----------------------------------------------------------------------------
# MCP Server
# -----------------------------------------------------------------------------

mcp = FastMCP("uipath-orchestrator")


# -----------------------------------------------------------------------------
# Primitive tools (multi-account, multi-tenant)
# -----------------------------------------------------------------------------

@mcp.tool()
async def list_folders(account: str, tenant: str) -> str:
    """
    List folders for a specific UiPath account and tenant.

    Args:
        account: UiPath account logical name (e.g., "billiysusldx", "octavioorg")
        tenant: UiPath tenant name (e.g., "DEV", "PROD", "DefaultTenant")
    """
    client = await get_client(account, tenant)
    folders = await client.get_folders()
    return json.dumps(folders, indent=2)


@mcp.tool()
async def list_assets(account: str, tenant: str, folder_id: int) -> str:
    """
    List assets in a folder for a specific UiPath account and tenant.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(account, tenant)
    assets = await client.get_assets(folder_id)
    return json.dumps(assets, indent=2)


@mcp.tool()
async def list_queues(account: str, tenant: str, folder_id: int) -> str:
    """
    List queues in a folder for a specific UiPath account and tenant.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(account, tenant)
    queues = await client.get_queues(folder_id)
    return json.dumps(queues, indent=2)


@mcp.tool()
async def list_storage_buckets(account: str, tenant: str, folder_id: int) -> str:
    """
    List storage buckets in a folder for a specific UiPath account and tenant.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(account, tenant)
    buckets = await client.get_storage_buckets(folder_id)
    return json.dumps(buckets, indent=2)


@mcp.tool()
async def list_processes(account: str, tenant: str, folder_id: int) -> str:
    """
    List processes (releases) in a folder for a specific UiPath account and tenant.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(account, tenant)
    processes = await client.get_processes(folder_id)
    return json.dumps(processes, indent=2)


@mcp.tool()
async def list_triggers(account: str, tenant: str, folder_id: int) -> str:
    """
    List triggers (time and queue) in a folder for a specific UiPath account and tenant.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(account, tenant)
    triggersets = await client.get_triggers(folder_id)
    return json.dumps(triggersets, indent=2)


@mcp.tool()
async def list_libraries(account: str, tenant: str) -> list[str]:
    """
    List available UiPath library package names.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
    """
    client = await get_client(account, tenant)
    return await client.list_libraries()


@mcp.tool()
async def list_library_versions(account: str, tenant: str, package_id: str) -> list[str]:
    """
    List available versions for a UiPath library.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
        package_id: Library package ID
    """
    client = await get_client(account, tenant)
    return await client.list_library_versions(package_id)


@mcp.tool()
async def download_library_version(
    account: str,
    tenant: str,
    package_id: str,
    version: str
) -> str:
    """
    Download a specific version of a UiPath library (.nupkg)
    using the configured download directory.

    Args:
        account: UiPath account logical name
        tenant: UiPath tenant name
        package_id: Library package ID
        version: Version string (e.g., "1.0.5")

    Returns:
        The local file path where the library was downloaded
    """
    client = await get_client(account, tenant)
    path = await client.download_library_version(
        package_id=package_id,
        version=version
    )
    return str(path)


@mcp.tool()
async def list_accounts() -> list[str]:
    """
    List all configured UiPath Orchestrator accounts.

    Returns:
        List of account logical names (e.g., ["billiysusldx", "octavioorg"])
    """
    return get_available_accounts()


@mcp.tool()
async def list_tenants(account: str) -> list[str]:
    """
    List all configured tenants for a specific account.

    Args:
        account: UiPath account logical name

    Returns:
        List of tenant names for that account
    """
    return get_available_tenants(account)


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")