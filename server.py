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
from src.service import (
    OrchestratorClient,
    CONFIG,
    get_available_accounts,
    get_available_tenants,
)

# -----------------------------------------------------------------------------
# Client cache (one client per account/tenant, shared token)
# -----------------------------------------------------------------------------

_CLIENTS: dict[str, OrchestratorClient] = {}


async def get_client(account: str, tenant: str) -> OrchestratorClient:
    """
    Get or create an authenticated OrchestratorClient for an account/tenant.
    """
    key = f"{account}/{tenant}"

    if key not in _CLIENTS:
        client = OrchestratorClient(account=account, tenant=tenant)
        await client.authenticate()
        _CLIENTS[key] = client

    return _CLIENTS[key]


# -----------------------------------------------------------------------------
# MCP Server
# -----------------------------------------------------------------------------

mcp = FastMCP("uipath-orchestrator")

# -----------------------------------------------------------------------------
# DISCOVERY TOOLS (READ-ONLY, AUTHORITATIVE)
# -----------------------------------------------------------------------------

@mcp.tool()
async def list_accounts() -> list[dict]:
    """
    Lists all configured UiPath Orchestrator accounts.

    READ-ONLY DISCOVERY TOOL.
    """
    accounts = get_available_accounts(CONFIG)

    return [
        {
            "account": account,
            "base_url": CONFIG["accounts"][account]["base_url"],
            "download_dir": CONFIG["accounts"][account]["download_dir"],
        }
        for account in accounts
    ]


@mcp.tool()
async def list_tenants(account: str) -> list[dict]:
    """
    Lists all tenants under a UiPath Orchestrator account.

    READ-ONLY DISCOVERY TOOL.
    Tenants are ACCOUNT-SCOPED.
    """
    tenants = get_available_tenants(CONFIG, account)

    return [
        {
            "tenant": tenant,
            "libraries_feed_id": CONFIG["accounts"][account]["tenants"][tenant][
                "libraries_feed_id"
            ],
        }
        for tenant in tenants
    ]


@mcp.tool()
async def list_folders(account: str, tenant: str) -> list[dict]:
    """
    Lists all folders in a UiPath Orchestrator tenant.

    READ-ONLY DISCOVERY TOOL.
    Folders are TENANT-SCOPED (not folder-scoped).
    """
    client = await get_client(account, tenant)
    return await client.get_folders()


@mcp.tool()
async def list_libraries(account: str, tenant: str) -> list[str]:
    """
    Lists all UiPath library package IDs in a tenant.

    READ-ONLY DISCOVERY TOOL.
    Libraries are TENANT-SCOPED.
    """
    client = await get_client(account, tenant)
    return await client.list_libraries()


@mcp.tool()
async def list_library_versions( account: str, tenant: str, package_id: str) -> list[str]:
    """
    Lists all available versions for a UiPath library package.

    READ-ONLY DISCOVERY TOOL.
    Library versions are TENANT-SCOPED.
    """
    client = await get_client(account, tenant)
    return await client.list_library_versions(package_id)


# -----------------------------------------------------------------------------
# FOLDER-SCOPED OPERATIONAL TOOLS
# -----------------------------------------------------------------------------

@mcp.tool()
async def get_folder_resources(
    resource_types: list[str],
    account: str,
    tenant: str,
    folder_id: int,
) -> str:
    """
    Fetches folder-scoped UiPath Orchestrator resources such as:
    - assets
    - queues
    - triggers
    - environments

    OPERATIONAL TOOL.

    RULES:
    - Requires a valid folder_id
    - ONLY for folder-scoped entities
    - NOT for folders, libraries, tenants, or accounts
    """
    client = await get_client(account, tenant)
    result = await client.get_resources(
        resource_types=resource_types,
        folder_id=folder_id,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def download_library_version(
    account: str,
    tenant: str,
    package_id: str,
    version: str,) -> str:
    """
    Downloads a specific version of a UiPath library (.nupkg).

    OPERATIONAL TOOL.
    Performs I/O and has side effects.
    """
    client = await get_client(account, tenant)
    path = await client.download_library_version(
        package_id=package_id,
        version=version,
    )
    return str(path)


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
