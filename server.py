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

    Clients are cached per (account, tenant) to:
    - reuse access tokens
    - avoid redundant authentication
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
# Discovery MCP resources (AUTHORITATIVE, READ-ONLY)
# -----------------------------------------------------------------------------

@mcp.resource("uipath://orchestrator/accounts")
async def orchestrator_accounts() -> list[dict]:
    """
    Lists all configured UiPath Orchestrator accounts.

    AUTHORITATIVE RESOURCE.
    Use this resource for discovery. Do NOT use tools to infer accounts.
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


@mcp.resource("uipath://orchestrator/accounts/{account}/tenants")
async def orchestrator_tenants(account: str) -> list[dict]:
    """
    Lists all tenants available under a UiPath Orchestrator account.

    AUTHORITATIVE RESOURCE.
    Tenants are account-scoped metadata and are NOT folder-scoped.
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


@mcp.resource("uipath://orchestrator/accounts/{account}/tenants/{tenant}/folders")
async def orchestrator_folders(account: str, tenant: str) -> list[dict]:
    """
    Lists ALL UiPath Orchestrator folders in the specified tenant.

    AUTHORITATIVE RESOURCE.

    IMPORTANT:
    - Folders are TENANT-SCOPED metadata
    - This is the ONLY correct way to list folders
    - Tools must NEVER be used to infer or list folders
    """
    client = await get_client(account, tenant)
    return await client.get_folders()


@mcp.resource("uipath://orchestrator/accounts/{account}/tenants/{tenant}/libraries")
async def orchestrator_libraries(account: str, tenant: str) -> list[str]:
    """
    Lists all available UiPath library package IDs in the tenant.

    AUTHORITATIVE RESOURCE.

    IMPORTANT:
    - Libraries are TENANT-SCOPED
    - Libraries do NOT belong to folders
    - No folder_id is required or valid
    - Tools must NOT be used to list libraries
    """
    client = await get_client(account, tenant)
    return await client.list_libraries()


@mcp.resource("uipath://orchestrator/accounts/{account}/tenants/{tenant}/libraries/{package_id}/versions")
async def orchestrator_library_versions(account: str, tenant: str, package_id: str) -> list[str]:
    """
    Lists all available versions for a specific UiPath library package.

    AUTHORITATIVE RESOURCE.

    IMPORTANT:
    - Library versions are TENANT-SCOPED
    - They are NOT folder-scoped
    - Do NOT use tools to retrieve versions
    """
    client = await get_client(account, tenant)
    return await client.list_library_versions(package_id)


# -----------------------------------------------------------------------------
# Operational tools (ACTIONS / COMPOSITE OPERATIONS ONLY)
# -----------------------------------------------------------------------------

@mcp.tool()
async def get_folder_resources(resource_types: list[str],account: str,tenant: str,folder_id: int) -> str:
    """
    Fetches folder-scoped UiPath Orchestrator resources such as:
    - assets
    - queues
    - triggers
    - environments

    OPERATIONAL TOOL — NOT A DISCOVERY MECHANISM.

    NOT SUPPORTED BY THIS TOOL:
    - folders
    - libraries
    - library versions
    - tenants
    - accounts

    RULES:
    - This tool REQUIRES a valid folder_id
    - Folder discovery MUST use the /folders MCP resource
    - Library discovery MUST use /libraries resources

    Response contract:
    - success  => list
    - failure  => { "error": "<message>" }
    """
    client = await get_client(account, tenant)
    result = await client.get_resources(
        resource_types=resource_types,
        folder_id=folder_id,
    )

    return json.dumps(result, indent=2)


@mcp.tool()
async def download_library_version(account: str,tenant: str,package_id: str,version: str) -> str:
    """
    Downloads a specific version of a UiPath library (.nupkg).

    OPERATIONAL TOOL.
    This tool performs I/O and has side effects.

    Discovery of libraries and versions MUST use MCP resources.
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