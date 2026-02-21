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
from src.service import (OrchestratorClient,CONFIG,get_available_accounts,get_available_tenants,QueueItemStatus,ResourceTypes,LinkableResourceTypes)
from typing import  Dict,Optional,Any,List
from dateutil import parser as dateutil_parser




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


@mcp.tool()
async def list_folders(account: str, tenant: str) -> str:
    """
    Retrieve the full nested folder tree for a UiPath tenant.

    READ-ONLY DISCOVERY TOOL.
    Folders are TENANT-SCOPED.

    Returns:
      {
        "status": "ok",
        "folders": [...]
      }

    On failure:
      {
        "status": "error",
        "message": "..."
      }
    """

    client = await get_client(account, tenant)

    try:
        tree = await client.get_folders_tree()

        return json.dumps({
            "status": "ok",
            "folders": tree
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)
# -----------------------------------------------------------------------------
# FOLDER-SCOPED OPERATIONAL TOOLS
# -----------------------------------------------------------------------------

@mcp.tool()
async def get_folder_resources(resource_types: list[ResourceTypes], account: str, tenant: str, folder_id: int) -> str:
    """
    Fetch one or more UiPath Orchestrator resource types from a folder.

    Allowed resource_types: "assets", "queues", "processes", "triggers", "storage_buckets"

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

@mcp.tool()
async def ensure_folder_path(account: str, tenant: str, folder_path: str) -> str:
    """
    Ensure that a nested folder path exists in UiPath Orchestrator.

    This tool is idempotent:
      - If the folder path already exists, it is returned unchanged.
      - If any segment is missing, it is created.
      - No existing folders are modified.

    Use this tool when:
      - You need to guarantee folder structure before provisioning resources.
      - You are performing declarative environment setup.

    Parameters:
      - account: Orchestrator account name.
      - tenant: Orchestrator tenant name.
      - folder_path: Folder path (e.g. "Finance/Prod/Invoices").

    Returns:
      {
        "status": "ok" | "error",
        "folder": {...},        # when successful
        "message": "..."        # when error
      }
    """

    client = await get_client(account, tenant)

    try:
        folder = await client.ensure_folder_path(folder_path)

        return json.dumps({
            "status": "ok",
            "folder": folder
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)



@mcp.tool()
async def ensure_resource_in_folder(resource_type:str,folder_path: str,resource_spec: Dict[str, Any],account: str,tenant: str) -> str:
    """
    Ensure that a resource exists inside a specific folder.

    Allowed resource_types: "assets", "queues", "processes", "triggers", "storage_buckets"

    This tool follows a create-only, idempotent policy:
      - If a resource with the same Name already exists in the folder,
        it is returned unchanged.
      - If it does not exist, it is created.
      - Existing resources are never updated or overwritten.
    """
    linkable_resource_type = LinkableResourceTypes(resource_type)
    client = await get_client(account, tenant)


    
    
    try:
        resource = await client.ensure_resource_in_folder(
            linkable_resource_type=linkable_resource_type,
            folder_path=folder_path,
            resource_spec=resource_spec,
        )

        return json.dumps({
            "status": "ok",
            "resource": resource
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)
    
@mcp.tool()
async def link_resource_to_folder(resource_type: str,resource_name: str,candidate_folder_paths: list[str],target_folder_path: str,account: str,tenant: str,expected_value_type: Optional[str] = None) -> str:
    """
    Link an existing shared resource into a target folder.

    This tool searches the provided candidate folders in order and links
    the first matching resource into the target folder.

    It does NOT create resources.
    If no matching resource is found, nothing is linked.

    Use this tool when:
      - A resource already exists elsewhere.
      - You want to reuse or share it.
      - You want to avoid duplicating resources.

    Matching behavior:
      - Resource is matched by Name.
      - If linkable_resource_type == LinkableResourceTypes.assets and expected_value_type is provided,
        ValueType must also match.
      - Stops after the first successful match.

    Parameters:
      - linkable_resource_type: allowed values: "assets", "queues", "storage_buckets"
      - resource_name: Name of the resource to locate.
      - candidate_folder_paths: Ordered list of folders to search.
      - target_folder_path: Folder to link the resource into.
      - account: Orchestrator account name.
      - tenant: Orchestrator tenant name.
      - expected_value_type: Optional (assets only). Example: "Text", "Bool", "Integer"

    Returns:
      {
        "status": "linked" | "not_linked",
        "resource_id": int | null,
        "linked_to": str | null,
        "reason": str | null
      }
    """
    linkable_resource_type = LinkableResourceTypes(resource_type)

    client = await get_client(account, tenant)

    result = await client.link_resource_to_folder(
        linkable_resource_type=linkable_resource_type,
        resource_name=resource_name,
        candidate_folder_paths=candidate_folder_paths,
        target_folder_path=target_folder_path,
        expected_value_type=expected_value_type,
    )

    return json.dumps(result, indent=2)

@mcp.tool()
async def get_queue_items(account: str,tenant: str,queue_id: int,start_time: Optional[str] = None,end_time: Optional[str] = None,statuses: Optional[List[QueueItemStatus]] = None,reference: Optional[str] = None) -> str:
    """
    Retrieve queue items for a specific UiPath queue.

    This tool automatically resolves the folder from the queue ID.
    Folder ID is NOT required.

    Args:
      - account: UiPath account name
      - tenant: UiPath tenant name
      - queue_id: ID of the queue to retrieve items from
      - start_time: filter items created after this date (any format, e.g. "2025-01-01", "01/01/2025", "2025-01-01T00:00:00Z")
      - end_time: filter items created before this date (any format, e.g. "2025-12-31", "31/12/2025", "2025-12-31T23:59:59Z")
      - statuses: filter by status. Allowed values: "New", "InProgress", "Failed", "Successful", "Abandoned", "Retried"
      - reference: filter by exact reference match

    Returns:
      {
        "status": "ok",
        "queue_id": int,
        "count": int,
        "items": [...]
      }

    On failure:
      {
        "status": "error",
        "message": "..."
      }
    """

    client = await get_client(account, tenant)

    try:
        parsed_start = dateutil_parser.parse(start_time) if start_time else None
        parsed_end = dateutil_parser.parse(end_time) if end_time else None

        parsed_statuses = (
            [QueueItemStatus(s) for s in statuses]
            if statuses else None
        )

        items = await client.get_queue_items(
            queue_id=queue_id,
            start_time=parsed_start,
            end_time=parsed_end,
            statuses=parsed_statuses,
            reference=reference,
        )

        return json.dumps({
            "status": "ok",
            "queue_id": queue_id,
            "count": len(items),
            "items": items
        }, indent=2, default=str)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)
# -----------------------------------------------------------------------------
# ACTION-SCOPED OPERATIONAL TOOLS
# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
