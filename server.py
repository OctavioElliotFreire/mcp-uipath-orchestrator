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
    Clients are cached per account/tenant combination to reuse tokens.
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
# Discovery tools
# -----------------------------------------------------------------------------

@mcp.tool()
async def list_accounts() -> list[str]:
    """
    List all configured UiPath Orchestrator accounts.
    """
    return get_available_accounts()


@mcp.tool()
async def list_tenants(account: str) -> list[str]:
    """
    List all configured tenants for a specific account.
    """
    return get_available_tenants(account)


@mcp.tool()
async def list_folders(account: str, tenant: str) -> str:
    """
    List folders for a specific UiPath account and tenant.
    """
    client = await get_client(account, tenant)
    folders = await client.get_folders()
    return json.dumps(folders, indent=2)


# -----------------------------------------------------------------------------
# Core resource tool (LLM-optimized)
# -----------------------------------------------------------------------------

@mcp.tool()
async def get_resources(
    resource_types: list[str],
    account: str,
    tenant: str,
    folder_id: int
) -> str:
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


# -----------------------------------------------------------------------------
# Library tools
# -----------------------------------------------------------------------------

@mcp.tool()
async def list_libraries(account: str, tenant: str) -> list[str]:
    """
    List available UiPath library package names.
    """
    client = await get_client(account, tenant)
    return await client.list_libraries()


@mcp.tool()
async def list_library_versions(account: str, tenant: str, package_id: str) -> list[str]:
    """
    List available versions for a UiPath library.
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
    Download a specific version of a UiPath library (.nupkg).
    """
    client = await get_client(account, tenant)
    path = await clien
