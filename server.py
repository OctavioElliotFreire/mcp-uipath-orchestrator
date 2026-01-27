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
from src.service import OrchestratorClient

# -----------------------------------------------------------------------------
# Client cache (one client per tenant, shared token)
# -----------------------------------------------------------------------------

_CLIENTS: dict[str, OrchestratorClient] = {}


async def get_client(tenant: str) -> OrchestratorClient:
    """
    Get or create an OrchestratorClient for a specific tenant.
    Clients are cached per tenant.
    """
    if tenant not in _CLIENTS:
        client = OrchestratorClient(tenant=tenant)
        await client.authenticate()
        _CLIENTS[tenant] = client

    return _CLIENTS[tenant]


# -----------------------------------------------------------------------------
# MCP Server
# -----------------------------------------------------------------------------

mcp = FastMCP("uipath-orchestrator")


# -----------------------------------------------------------------------------
# Primitive tools (single-tenant, cheap, reliable)
# -----------------------------------------------------------------------------

@mcp.tool()
async def list_folders(tenant: str) -> str:
    """
    List folders for a specific UiPath tenant.

    Args:
        tenant: UiPath tenant name (must be listed in TENANTS env var)
    """
    client = await get_client(tenant)
    folders = await client.get_folders()
    return json.dumps(folders, indent=2)


@mcp.tool()
async def list_assets(tenant: str, folder_id: int) -> str:
    """
    List assets in a folder for a specific UiPath tenant.

    Args:
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(tenant)
    assets = await client.get_assets(folder_id)
    return json.dumps(assets, indent=2)

@mcp.tool()
async def list_queues(tenant: str, folder_id: int) -> str:
    """
    List queues in a folder for a specific UiPath tenant.

    Args:
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(tenant)
    queues = await client.get_queues(folder_id)
    return json.dumps(queues, indent=2)

@mcp.tool()
async def list_storage_buckets(tenant: str, folder_id: int) -> str:
    """
    List storage buckets in a folder for a specific UiPath tenant.

    Args:
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(tenant)
    buckets = await client.get_storage_buckets(folder_id)
    return json.dumps(buckets, indent=2)

@mcp.tool()
async def list_processes(tenant: str, folder_id: int) -> str:
    """
    List processes (releases) in a folder for a specific UiPath tenant.

    Args:
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(tenant)
    processes = await client.get_processes(folder_id)
    return json.dumps(processes, indent=2)



@mcp.tool()
async def list_triggers(tenant: str, folder_id: int) -> str:
    """
    List triggers (time and queue) in a folder for a specific UiPath tenant.

    Args:
        tenant: UiPath tenant name
        folder_id: Folder ID
    """
    client = await get_client(tenant)
    triggersets = await client.get_triggers(folder_id)
    return json.dumps(triggersets, indent=2)

@mcp.tool()
async def list_libraries(tenant: str, search: str | None = None) -> list[str]:
    """
    List available UiPath library package names.

    Args:
        tenant: UiPath tenant name
        search: Optional substring to narrow results
    """
    client = await get_client(tenant)
    return await client.list_libraries(search)

@mcp.tool()
async def list_library_versions(tenant: str, package_id: str) -> list[str]:
    """
    List available versions for a UiPath library.
    """
    client = await get_client(tenant)
    return await client.list_library_versions(package_id)



# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
