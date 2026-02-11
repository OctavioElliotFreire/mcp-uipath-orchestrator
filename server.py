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
from src.service import (OrchestratorClient,CONFIG,get_available_accounts,get_available_tenants)

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
async def list_folders_tree(account: str, tenant: str) -> list[dict]:
    """
    Returns the full folder hierarchy for a UiPath Orchestrator tenant.

    The result is a nested tree structure where each folder includes a
    "children" field containing its subfolders.

    This tool is read-only and intended for structure discovery,
    hierarchy inspection, and reasoning about existing folder layouts.

    Important:
    - Folders are tenant-scoped (not folder-scoped).
    - No changes are made to the Orchestrator.
    """
    client = await get_client(account, tenant)
    return await client.get_folders_tree()


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
async def get_folder_resources(resource_types: list[str], account: str, tenant: str, folder_id: int) -> str:
    """
    Fetch one or more UiPath Orchestrator resource types from a folder.

    This tool intentionally returns a JSON object where:
      - list  => successful fetch
      - dict with "error" => failure

    The response shape itself signals success vs failure, which:
      - avoids redundant wrappers (items, error: null)
      - reduces token usage
      - is easier for LLMs to reason about
      - supports partial success naturally

    Example response:
    {
        "assets": [...],
        "queues": [...],
        "triggers": { "error": "403 Forbidden" }
    }
    """
    client = await get_client(account, tenant)
    result = await client.get_resources(
        resource_types=resource_types,
        folder_id=folder_id
    )

    # MCP tools must return strings; JSON is returned verbatim so the LLM
    # can reason directly over the response structure.
    return json.dumps(result, indent=2)


@mcp.tool()
async def download_library_version(account: str,tenant: str,package_id: str,version: str) -> str:
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
# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
