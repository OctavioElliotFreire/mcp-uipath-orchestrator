# Standard library
import asyncio
import json
import logging
import re
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import xml.etree.ElementTree as ET

# Third-party
import httpx

logger = logging.getLogger(__name__)


    # =============================================================================
    # Configuration Models
    # =============================================================================

from dataclasses import dataclass
from typing import Dict
from enum import Enum


@dataclass(frozen=True)
class AuthConfig:
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class TenantConfig:
    libraries_feed_id: str


@dataclass(frozen=True)

class AccountConfig:
    base_url: str
    auth: AuthConfig
    download_dir: str
    tenants: Dict[str, TenantConfig]


@dataclass(frozen=True)
class Config:
    accounts: Dict[str, AccountConfig]

    # =============================================================================
    # Enums
    # =============================================================================

class QueueItemStatus(str, Enum):
    New = "New"
    InProgress = "InProgress"
    Failed = "Failed"
    Successful = "Successful"
    Retried = "Retried"
    Abandoned = "Abandoned"
    Deleted = "Deleted"


class ResourceTypes(str, Enum):
    assets = "assets"
    queues = "queues"
    processes = "processes"
    triggers = "triggers"
    storage_buckets = "storage_buckets"
    business_rules = "business_rules"

    @property
    def is_linkable(self) -> bool:
        return self.value in LINKABLE_RESOURCE_VALUES


class PackageType(str, Enum):
    library = "library"
    process = "process"

    @property
    def upload_suffix(self) -> str:
        return "Libraries" if self is PackageType.library else "Processes"


    # =============================================================================
    # Resource Configuration
    # =============================================================================

@dataclass(frozen=True)
class ResourceConfig:
    create_endpoint: str
    share_endpoint: str
    id_field: str
    payload_builder: str


class LinkableResourceTypes(str, Enum):
    assets = "assets"
    queues = "queues"
    storage_buckets = "storage_buckets"
    business_rules = "business_rules"

    @property
    def config(self) -> ResourceConfig:
        return LINKABLE_RESOURCE_CONFIGS[self]

    def to_resource_type(self) -> ResourceTypes:
        return ResourceTypes(self.value)


# Central registry (defined once, not rebuilt every call)
LINKABLE_RESOURCE_CONFIGS: Dict[LinkableResourceTypes, ResourceConfig] = {
    LinkableResourceTypes.assets: ResourceConfig(
        create_endpoint="odata/Assets",
        share_endpoint="odata/Assets/UiPath.Server.Configuration.OData.ShareToFolders",
        id_field="AssetIds",
        payload_builder="_build_asset_payload",
    ),
    LinkableResourceTypes.queues: ResourceConfig(
        create_endpoint="odata/QueueDefinitions",
        share_endpoint="odata/QueueDefinitions/UiPath.Server.Configuration.OData.ShareToFolders",
        id_field="QueueIds",
        payload_builder="_build_queue_payload",
    ),
    LinkableResourceTypes.storage_buckets: ResourceConfig(
        create_endpoint="odata/Buckets",
        share_endpoint="odata/Buckets/UiPath.Server.Configuration.OData.ShareToFolders",
        id_field="BucketIds",
        payload_builder="_build_storage_bucket_payload",
    ),
    LinkableResourceTypes.business_rules: ResourceConfig(
        create_endpoint="odata/BusinessRules",
        share_endpoint="odata/BusinessRules/UiPath.Server.Configuration.OData.ShareToFolders",
        id_field="BusinessRuleIds",
        payload_builder="_build_business_rule_payload",
    ),
}

LINKABLE_RESOURCE_VALUES = {rt.value for rt in LinkableResourceTypes}


# =============================================================================
# Client Settings
# =============================================================================

@dataclass(frozen=True)
class OrchestratorClientSettings:
    max_internal_return: int = 100
    uipath_page_size: int = 100
    max_retries: int = 2
    retry_backoff_base: float = 0.5

# -----------------------------------------------------------------------------
# Global configuration
# -----------------------------------------------------------------------------

def load_config() -> Config:
    """Load multi-orchestrator configuration from config.json"""
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config" / "config.json"

    if not config_path.exists():
        raise RuntimeError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise RuntimeError("Config must be a JSON object")

    return {"accounts": data}


CONFIG = load_config()


def get_available_accounts(config: dict) -> list[str]:
    return list(config["accounts"].keys())


def get_available_tenants(config: dict, account: str) -> list[str]:
    account_cfg = config["accounts"].get(account)
    if not account_cfg:
        return []
    return list(account_cfg.get("tenants", {}).keys())


# -----------------------------------------------------------------------------
# Orchestrator Client
# -----------------------------------------------------------------------------

class OrchestratorClient:
    """
    UiPath Orchestrator client (multi-account, multi-tenant).

    - OAuth (client credentials)
    - Normalizes OData responses
    - Returns clean domain objects
    """

    # =========================================================================
    # Constructor
    # =========================================================================


    def __init__(self, account: str, tenant: str):  
        if account not in CONFIG["accounts"]:
            raise RuntimeError(f"Account '{account}' not found")

        account_cfg = CONFIG["accounts"][account]

        if tenant not in account_cfg["tenants"]:
            raise RuntimeError(f"Tenant '{tenant}' not found in account '{account}'")

        self.account = account
        self.tenant = tenant
        self.settings = OrchestratorClientSettings()
        self.base_url = account_cfg["base_url"]
        self.download_dir = account_cfg["download_dir"]
        self.client_id = account_cfg["auth"]["client_id"]
        self.client_secret = account_cfg["auth"]["client_secret"]
        self.libraries_feed_id = account_cfg["tenants"][tenant]["libraries_feed_id"]
        self._credential_defaults = {
            "username": "mcp_default_user",
            "password": "DefaultPassword123!"
        }
        
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None


        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False,
        )


    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def authenticate(self, force: bool = False) -> str:
        now = datetime.now(timezone.utc)

        # If token exists and is still valid, reuse it
        if (
            not force
            and self._access_token
            and self._token_expiry
            and now < self._token_expiry
        ):
            return self._access_token

        auth_url = f"{self.base_url}identity_/connect/token"

        r = await self.client.post(
            auth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        r.raise_for_status()

        data = r.json()

        self._access_token = data["access_token"]

        expires_in = data.get("expires_in", 3600)

        # Add 60-second safety buffer
        self._token_expiry = (
            datetime.now(timezone.utc)
            + timedelta(seconds=expires_in - 60)
        )

        return self._access_token


    # =========================================================================
    # Transport Layer
    # =========================================================================

    def _headers(self, folder_id: int | None = None, multipart: bool = False) -> dict:
        if not self._access_token:
            raise RuntimeError("Client not authenticated")

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "X-UIPATH-TenantName": self.tenant,
        }

        # Multipart uploads must NOT have Content-Type set —
        # httpx sets it automatically with the correct boundary
        if not multipart:
            headers["Content-Type"] = "application/json"

        if folder_id is not None:
            headers["X-UIPATH-OrganizationUnitId"] = str(folder_id)

        return headers

    def _build_url(self, endpoint: str) -> str:
        return (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

    async def _ensure_authenticated(self):
        await self.authenticate()

    async def _request(self, method: str, endpoint: str, *, folder_id: int | None = None, json: dict | None = None, files=None, params: dict | None = None, multipart: bool = False):
        await self._ensure_authenticated()

        url = self._build_url(endpoint)
        attempt = 0

        while True:
            start = time.perf_counter()

            try:
                response = await self.client.request(
                    method,
                    url,
                    headers=self._headers(folder_id, multipart=multipart),
                    json=json,
                    files=files,
                    params=params,
                )
            except httpx.RequestError as e:
                # Network-level failure
                if attempt >= self.settings.max_retries:
                    raise

                delay = self.settings.retry_backoff_base * (2 ** attempt)
                logger.warning("Network error on %s %s. Retrying in %.2fs (attempt %s)", method, endpoint, delay, attempt + 1)
                await asyncio.sleep(delay)
                attempt += 1
                continue

            # 401 retry (token refresh)
            if response.status_code == 401:
                logger.warning("401 received. Refreshing token and retrying once: %s %s", method, endpoint)
                await self.authenticate(force=True)
                attempt += 1
                continue

            # Retry on transient status codes
            if response.status_code in (429, 502, 503, 504):
                if attempt >= self.settings.max_retries:
                    response.raise_for_status()

                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = float(retry_after)
                else:
                    delay = self.settings.retry_backoff_base * (2 ** attempt)

                logger.warning(
                    "Transient HTTP %s on %s %s. Retrying in %.2fs (attempt %s)",
                    response.status_code,
                    method,
                    endpoint,
                    delay,
                    attempt + 1,
                )

                await asyncio.sleep(delay)
                attempt += 1
                continue

            # Normal exit
            duration_ms = (time.perf_counter() - start) * 1000
            logger.debug("HTTP %s %s -> %s (%.1f ms)", method, endpoint, response.status_code, duration_ms)

            response.raise_for_status()

            if not response.content:
                return {}

            content_type = response.headers.get("Content-Type", "")

            if "application/json" in content_type:
                return response.json()

            return response
        
    async def get(self, endpoint: str, folder_id: int | None = None) -> dict:
        return await self._request("GET", endpoint, folder_id=folder_id)

    async def post(self, endpoint: str, payload: dict, folder_id: int | None = None) -> dict:
        return await self._request("POST", endpoint, folder_id=folder_id, json=payload)

    async def put(self, endpoint: str, payload: dict, folder_id: int | None = None) -> dict:
        return await self._request("PUT", endpoint, folder_id=folder_id, json=payload)
    
    # -------------------------------------------------------------------------
    # OData normalization
    # -------------------------------------------------------------------------

    @staticmethod
    def _unwrap_odata(response):
        """
        Normalize UiPath OData responses.
        - If response has a 'value' key, return it
        - Otherwise return response unchanged
        """
        if isinstance(response, dict) and "value" in response:
            return response["value"]
        return response

    def _to_uipath_datetime(self, dt: datetime) -> str:
        """
        Convert datetime to UiPath OData v4 accepted format:
        yyyy-MM-ddTHH:mm:ssZ
        - UTC timezone indicated by Z suffix
        - No microseconds
        - No datetime'' wrapper (that's OData v3)
        """
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)

        dt = dt.replace(microsecond=0)

        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # =========================================================================
    # Folder Management
    # =========================================================================
    
    async def get_folders(self) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Folders"))

    async def resolve_folder_path(self, path: str) -> dict:
        """
        Resolve a folder path without creating it.

        Raises RuntimeError if path does not exist.
        """

        if not path or not path.strip():
            raise ValueError("path cannot be empty")

        segments = [seg.strip() for seg in path.split("/") if seg.strip()]
        if not segments:
            raise ValueError("Invalid folder path")

        folders = await self.get_folders()

        index = {
            (f.get("ParentId"), f["DisplayName"]): f
            for f in folders
        }

        current_parent_id = None
        current_folder = None

        for segment in segments:
            key = (current_parent_id, segment)

            if key not in index:
                raise RuntimeError(f"Folder path not found: {path}")

            current_folder = index[key]
            current_parent_id = current_folder["Id"]

        return current_folder

    async def create_folder(self,new_folder_name: str,parent_id: int | None = None,description: str | None = None) -> dict:
        """
        Create a modern folder in the current tenant.

        Supports nested folders via parent_id.
        """

        name = (new_folder_name or "").strip()
        if not name:
            raise ValueError("new_folder_name cannot be empty")

        payload = {
            "DisplayName": name,
            "Description": description or "",
            "ProvisionType": "Automatic",
            "ParentId": parent_id,
        }

        return await self.post("odata/Folders", payload)
   
    async def ensure_folder_path(self, path: str) -> dict:
        """
        Ensure that a nested folder path exists.
        Creates missing segments.
        Returns final folder.
        """

        if not path or not path.strip():
            raise ValueError("path cannot be empty")

        segments = [seg.strip() for seg in path.split("/") if seg.strip()]
        if not segments:
            raise ValueError("Invalid folder path")

        folders = await self.get_folders()

        index = {
            (f.get("ParentId"), f["DisplayName"]): f
            for f in folders
        }

        current_parent_id = None
        current_folder = None

        for segment in segments:
            key = (current_parent_id, segment)

            if key in index:
                current_folder = index[key]
                current_parent_id = current_folder["Id"]
            else:
                new_folder = await self.create_folder(
                    new_folder_name=segment,
                    parent_id=current_parent_id
                )

                current_folder = new_folder
                current_parent_id = new_folder["Id"]

                # Update index for next segment resolution
                index[(new_folder.get("ParentId"), new_folder["DisplayName"])] = new_folder

        return current_folder
    
    @staticmethod
    def _build_folder_tree(folders: list[dict]) -> list[dict]:
        """
        Convert flat UiPath folder list into nested tree structure.
        Preserves all original fields and adds 'children'.
        This should help the llm to "understand" the structure in a more natural way
        """

        # Create copy of folders indexed by Id
        by_id: dict[int, dict] = {}

        for folder in folders:
            folder_copy = dict(folder)  # avoid mutating original
            folder_copy["children"] = []
            by_id[folder["Id"]] = folder_copy

        root_nodes: list[dict] = []

        for folder in by_id.values():
            parent_id = folder.get("ParentId")

            if parent_id and parent_id in by_id:
                by_id[parent_id]["children"].append(folder)
            else:
                root_nodes.append(folder)

        return root_nodes
    
    async def get_folders_tree(self) -> dict:
        """
        Return folders as nested JSON tree.
        Output format:
        {
            "result": [ ...tree... ]
        }
        """
        folders = await self.get_folders()
        return self._build_folder_tree(folders)
    
    async def _resolve_folder_from_queue(self, queue_id: int) -> int:
        """
        Resolve folder_id from queue_id by scanning folders.
        Required in modern folder tenants where QueueDefinitions is folder-scoped.
        """

        folders = await self.get_folders()

        for folder in folders:
            folder_id = folder["Id"]

            try:
                queues = await self.get_queues(folder_id)
            except Exception:
                continue

            for q in queues:
                if q["Id"] == queue_id:
                    return folder_id
    
    
    # =========================================================================
    # Resource Operations
    # =========================================================================

    
    async def get_assets(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Assets", folder_id))

    async def get_queues(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/QueueDefinitions", folder_id))
    
    async def get_business_rules(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/BusinessRules", folder_id))

    async def get_storage_buckets(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Buckets", folder_id))  
    
    async def get_triggers(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/ProcessSchedules", folder_id))
    
    async def get_queue_items(self,queue_id: int,skip: int = 0,start_time: Optional[datetime] = None,end_time: Optional[datetime] = None,statuses: Optional[List[QueueItemStatus]] = None,reference: Optional[str] = None) -> Dict:

        if not queue_id:
            raise ValueError("queue_id is required")

        max_internal = self.settings.max_internal_return
        page_size = self.settings.uipath_page_size

        folder_id = await self._resolve_folder_from_queue(queue_id)

        # Default 30-day window
        if not start_time and not end_time:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=30)

        filters = [f"QueueDefinitionId eq {queue_id}"]

        if start_time:
            filters.append(
                f"CreationTime ge {self._to_uipath_datetime(start_time)}"
            )

        if end_time:
            filters.append(
                f"CreationTime lt {self._to_uipath_datetime(end_time)}"
            )

        if statuses:
            if len(statuses) == 1:
                filters.append(f"Status eq '{statuses[0].value}'")
            else:
                status_filter = " or ".join(
                    f"Status eq '{s.value}'" for s in statuses
                )
                filters.append(f"({status_filter})")

        if reference:
            filters.append(f"Reference eq '{reference}'")

        filter_query = " and ".join(filters)

        collected: List[Dict] = []
        internal_skip = skip
        total_available: Optional[int] = None

        # -----------------------------------------
        # Internal pagination (UiPath side)
        # -----------------------------------------
        while len(collected) < max_internal:

            remaining = max_internal - len(collected)
            top = min(page_size, remaining)

            endpoint = (
                f"odata/QueueItems"
                f"?$top={top}"
                f"&$skip={internal_skip}"
                f"&$count=true"
                f"&$filter={filter_query}"
            )

            response = await self.get(endpoint, folder_id=folder_id)

            if total_available is None:
                total_available = response.get("@odata.count")

            items = self._unwrap_odata(response)

            if not items:
                break

            collected.extend(items)
            internal_skip += len(items)

            # If searching by reference, only one result expected
            if reference:
                break

            # Stop if UiPath returned fewer than requested
            if len(items) < top:
                break

        returned = len(collected)
        next_skip = skip + returned

        has_more = (
            total_available is not None and next_skip < total_available
        )

        return {
            "total_available": total_available,
            "returned": returned,
            "skip": skip,
            "next_skip": next_skip if has_more else None,
            "has_more": has_more,
            "limit": max_internal,
            "items": collected,
        }
    
    async def get_processes(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Releases", folder_id))
    
    async def get_storage_files(self,folder_id: int,bucket_id: int) -> list[dict]:
        """
        List all files inside a storage bucket.
        
        Args:
            folder_id: Folder containing the bucket
            bucket_id: ID of the storage bucket
            directory: Directory path to list (default: "/" for root)
            recursive: Whether to list files recursively in subdirectories
        
        Returns:
            List of file objects with properties:
            - FullPath: Full path/name of the file in the bucket
            - ContentType: MIME type (e.g., "application/json")
            - Size: File size in bytes
            - IsDirectory: Whether this is a directory (bool or null)
            - Id: File ID (appears to be null in API response)
            
        Note: Files have FullPath but no separate Name property.
            Use FullPath.split('/')[-1] to extract just the filename.
        """
        endpoint = (
            f"odata/Buckets({bucket_id})/"
            f"UiPath.Server.Configuration.OData.GetFiles"
            f"?directory=/&recursive={'true'}"
        )
        
        data = await self.get(endpoint, folder_id=folder_id)
        return self._unwrap_odata(data)

    async def get_resources(self,resource_types: list[ResourceTypes],folder_id: int) -> dict[str, list | dict]:

        if not resource_types:
            raise ValueError("resource_types cannot be empty")

        tasks = {
            rt: self._resource_getters[rt](folder_id)
            for rt in resource_types
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        response: dict[str, list | dict] = {}

        for resource_type, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                response[resource_type.value] = {"error": str(result)}
                continue

            items = result or []

            if resource_type.is_linkable:
                items = await self._attach_linked_folders(items, resource_type.value)

            response[resource_type.value] = items

        return response

    @property
    def _resource_getters(self) -> dict[ResourceTypes, callable]:
        return {
            ResourceTypes.assets: self.get_assets,
            ResourceTypes.queues: self.get_queues,
            ResourceTypes.processes: self.get_processes,
            ResourceTypes.triggers: self.get_triggers,
            ResourceTypes.storage_buckets: self.get_storage_buckets,
            ResourceTypes.business_rules: self.get_business_rules,
            
        }

    async def download_storage_file(self,folder_id: int,bucket_id: int,file_path: str) -> Path:
        """
        Download a storage file using the two-step Cloud API pattern:
        1. GET a signed download URI from Orchestrator
        2. GET the actual file bytes from that URI
        """

        if not self._access_token:
            await self.authenticate()

        # Step 1: Get the signed download URI from Orchestrator
        # This is a GET with query params, NOT a POST with a body
        endpoint = (
            f"odata/Buckets({bucket_id})"
            f"/UiPath.Server.Configuration.OData.GetReadUri"
        )

        url = (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

        params = {"path": file_path}
        headers = self._headers(folder_id)

        r = await self.client.get(url, headers=headers, params=params)
        r.raise_for_status()

        data = r.json()
        download_uri = data["Uri"]

        # Step 2: Fetch the actual file bytes from the signed URI
        # No auth headers needed — it's a pre-signed blob URL
        file_response = await self.client.get(download_uri)
        file_response.raise_for_status()

        # Write to disk
        base = Path(self.download_dir)
        base.mkdir(parents=True, exist_ok=True)

        filename = file_path.split("/")[-1]
        path = base / filename
        path.write_bytes(file_response.content)

        return path


    # =========================================================================
    # Linking Operations
    # =========================================================================

    async def link_resource_to_folder(self,linkable_resource_type: LinkableResourceTypes,resource_name: str,candidate_folder_paths: list[str],target_folder_path: str,expected_value_type: Optional[str] = None) -> dict:
        """
        Link an existing shared resource into a target folder.

        This tool searches the provided candidate folders in order and links
        the first matching resource into the target folder.

        It does NOT create resources.
        If no matching resource is found, nothing is linked.

        Matching behavior:
        - Resource is matched by Name.
        - If linkable_resource_type == "assets" and expected_value_type is provided,
        ValueType must also match.
        - Stops after the first successful match.

        Returns:
        {
            "status": "linked" | "not_linked",
            "resource_id": int | null,
            "linked_to": str | null,
            "reason": str | null
        }
        """

        config = linkable_resource_type.config
        getter = self._resource_getters[linkable_resource_type.to_resource_type()]

        # Resolve target folder
        try:
            target_folder = await self.ensure_folder_path(target_folder_path)
        except Exception:
            return {
                "status": "not_linked",
                "resource_id": None,
                "linked_to": None,
                "reason": "target_folder_not_found",
            }

        target_folder_id = target_folder["Id"]

        # Search candidate folders in order
        for folder_path in candidate_folder_paths:
            try:
                folder = await self.resolve_folder_path(folder_path)
            except Exception:
                continue

            resources = await getter(folder["Id"])

            for resource in resources:

                # Match by Name
                if resource.get("Name") != resource_name:
                    continue

                # If assets and expected_value_type provided, validate ValueType
                if linkable_resource_type == LinkableResourceTypes.assets and expected_value_type:
                    if resource.get("ValueType") != expected_value_type:
                        continue

                payload = {
                    config.id_field: [resource["Id"]],
                    "toAddFolderIds": [target_folder_id],
                    "toRemoveFolderIds": [],
                }

                try:
                    await self.post(config.share_endpoint, payload)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code != 409:
                        raise

                return {
                    "status": "linked",
                    "resource_id": resource["Id"],
                    "linked_to": target_folder_path,
                    "reason": None,
                }

        return {
            "status": "not_linked",
            "resource_id": None,
            "linked_to": None,
            "reason": "no_matching_candidate_folder",
        }  
    
    async def ensure_resource_in_folder(self,linkable_resource_type: LinkableResourceTypes, folder_path: str, resource_spec: dict) -> dict:

        name = resource_spec.get("Name")
        if not name:
            raise ValueError("resource_spec must include 'Name'")

        config = linkable_resource_type.config
        getter = self._resource_getters[linkable_resource_type.to_resource_type()]

        
             
        # Resolve folder
        folder = await self.ensure_folder_path(folder_path)
        folder_id = folder["Id"]

        # Get existing resources
        existing_items = await getter(folder_id)

        existing = next(
            (r for r in existing_items if r["Name"] == name),
            None
        )

        if existing:
            return existing

        # Build payload dynamically
        builder = getattr(self, config.payload_builder)
        payload = await builder(resource_spec)

        # Create resource
        return await self.post(
            config.create_endpoint,
            payload,
            folder_id=folder_id,
        )
    
    async def _attach_linked_folders(self,items: List[dict],linkable_resource_type: LinkableResourceTypes) -> List[dict]:
        """
        Optimized version:
        - Fetch folder items concurrently
        - Precompute folder paths once
        - Only track relevant resource IDs
        """

        if not items:
            return items

        getter = self._resource_getters[ResourceTypes(linkable_resource_type)]

        # --------------------------------------------------
        # Step 1: Fetch folders and build folder lookup
        # --------------------------------------------------
        all_folders = await self.get_folders()
        by_id = {f["Id"]: f for f in all_folders}

        def build_path(fid: int) -> str:
            parts = []
            current = by_id.get(fid)
            while current:
                parts.append(current["DisplayName"])
                current = by_id.get(current.get("ParentId"))
            return "/".join(reversed(parts))

        folder_paths = {
            f["Id"]: build_path(f["Id"])
            for f in all_folders
        }

        # --------------------------------------------------
        # Step 2: Concurrently fetch items in all folders
        # --------------------------------------------------
        folder_ids = [f["Id"] for f in all_folders]
        results = await asyncio.gather(
            *[getter(fid) for fid in folder_ids],
            return_exceptions=True
        )

        target_ids: Set[int] = {item["Id"] for item in items}
        links: Dict[int, Set[str]] = {}

        for fid, folder_items in zip(folder_ids, results):
            if isinstance(folder_items, Exception):
                continue

            path = folder_paths[fid]

            for item in folder_items:
                rid = item["Id"]
                if rid in target_ids:
                    links.setdefault(rid, set()).add(path)

        # --------------------------------------------------
        # Step 3: Attach LinkedFolders
        # --------------------------------------------------
        return [
            {**item, "LinkedFolders": sorted(links.get(item["Id"], []))}
            for item in items
        ]
   


    # -------------------------------------------------------------------------
    # Payload builders
    # -------------------------------------------------------------------------

    async def _build_asset_payload(self, asset_spec: dict) -> dict:

        name = asset_spec.get("Name")
        value_type = asset_spec.get("ValueType")
        value = asset_spec.get("Value")

        if not value_type:
            raise ValueError("Asset spec must include 'ValueType'")

        payload = {
            "Name": name,
            "ValueType": value_type,
            "ValueScope": "Global",
        }

        if value_type == "Text":
            payload["StringValue"] = value

        elif value_type == "Bool":
            payload["BoolValue"] = value

        elif value_type == "Integer":
            payload["IntValue"] = value

        elif value_type == "Credential":
            payload["CredentialUsername"] = self._credential_defaults["username"]
            payload["CredentialPassword"] = self._credential_defaults["password"]

        else:
            raise ValueError(f"Unsupported ValueType: {value_type}")

        return payload
    async def _build_queue_payload(self, queue_spec: dict) -> dict:

        name = queue_spec.get("Name")
        if not name:
            raise ValueError("Queue spec must include 'Name'")

        return {
            "Name": name,
            "Description": queue_spec.get("Description", ""),
            "MaxNumberOfRetries": queue_spec.get("MaxNumberOfRetries", 0),
            "AcceptAutomaticallyRetry": queue_spec.get("AcceptAutomaticallyRetry", False),
        }
    async def _build_storage_bucket_payload(self, bucket_spec: dict) -> dict:
       
        name = bucket_spec.get("Name")
        if not name:
            raise ValueError("Bucket spec must include 'Name'")
        
        # Generate UUID for Identifier (REQUIRED by API)
        identifier = str(uuid.uuid4())
        
        return {
            "Name": name,
            "Identifier": identifier,  # THIS IS THE FIX!
            "Description": bucket_spec.get("Description", ""),
        }


   
    
    # -------------------------------------------------------------------------
    # Package / NuGet Operations
    # -------------------------------------------------------------------------

    async def list_libraries(self) -> list[str]:
        data = await self.get("odata/Libraries")
        return sorted(
            lib["Id"]
            for lib in self._unwrap_odata(data)
            if lib.get("Id")
        )
    
    async def list_library_versions(self, package_id: str) -> list[str]:
        if not self._access_token:
            await self.authenticate()

        index_url = (
            f"{self.base_url}{self.account}/{self.tenant}"
            f"/orchestrator_/nuget/v3/{self.libraries_feed_id}/index.json"
        )

        headers = {"Authorization": f"Bearer {self._access_token}"}

        index = (await self.client.get(index_url, headers=headers)).json()

        base_addr = next(
            (
                r["@id"]
                for r in index.get("resources", [])
                if "PackageBaseAddress/3.0.0" in (
                    r.get("@type", []) if isinstance(r.get("@type"), list) else [r.get("@type")]
                )
            ),
            None,
        )

        if not base_addr:
            raise RuntimeError("PackageBaseAddress/3.0.0 not found")

        versions_url = f"{base_addr.rstrip('/')}/{package_id.lower()}/index.json"
        versions = (await self.client.get(versions_url, headers=headers)).json().get("versions", [])

        return sorted(versions)

    async def download_library_version(self, package_id: str, version: str) -> Path:
        if not self._access_token:
            await self.authenticate()

        index_url = (
            f"{self.base_url}{self.account}/{self.tenant}"
            f"/orchestrator_/nuget/v3/{self.libraries_feed_id}/index.json"
        )

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        # 1) Get NuGet service index
        r = await self.client.get(index_url, headers=headers)
        r.raise_for_status()
        index = r.json()

        # 2) Find PackageBaseAddress
        base_addr = next(
            (
                res["@id"]
                for res in index.get("resources", [])
                if "PackageBaseAddress/3.0.0" in (
                    res.get("@type", [])
                    if isinstance(res.get("@type"), list)
                    else [res.get("@type")]
                )
            ),
            None,
        )

        if not base_addr:
            raise RuntimeError("PackageBaseAddress/3.0.0 not found")

        # 3) Build flat-container URL
        pkg = package_id.lower()
        ver = version.lower()

        download_url = (
            f"{base_addr.rstrip('/')}/{pkg}/{ver}/{pkg}.{ver}.nupkg"
        )

        # 4) Download
        base = Path(self.download_dir)
        base.mkdir(parents=True, exist_ok=True)

        r = await self.client.get(download_url, headers=headers)
        r.raise_for_status()

        path = base / f"{package_id}.{version}.nupkg"
        path.write_bytes(r.content)

        return path

    async def download_package_odata(self,package_name: str,version: str,folder_id: int) -> Path:
        if not package_name or not version:
            raise ValueError("package_name and version are required")

        if not self._access_token:
            await self.authenticate()

        # Step 1: Confirm release exists
        releases = self._unwrap_odata(
            await self.get("odata/Releases", folder_id=folder_id)
        )

        release = next(
            (r for r in releases
            if r.get("ProcessKey") == package_name
            and r.get("ProcessVersion") == version),
            None,
        )

        if not release:
            available = [(r.get("ProcessKey"), r.get("ProcessVersion")) for r in releases]
            raise RuntimeError(
                f"Release not found: {package_name} v{version} in folder {folder_id}. "
                f"Available: {available}"
            )

        # Step 2: Download
        url = (
            f"{self.base_url}{self.account}/{self.tenant}/orchestrator_"
            f"/odata/Processes"
            f"/UiPath.Server.Configuration.OData.DownloadPackage"
            f"(key='{package_name}:{version}')"
        )

        r = await self.client.get(url, headers=self._headers(folder_id))
        r.raise_for_status()

        # Step 3: Save to disk
        base_path = Path(self.download_dir)
        base_path.mkdir(parents=True, exist_ok=True)
        path = base_path / f"{package_name}.{version}.nupkg"
        path.write_bytes(r.content)

        return path
    
    async def upload_package_odata(self,package_path: Path | str,folder_id: int,package_type :str,overwrite: bool = False) -> dict:
        if not self._access_token:
            await self.authenticate()

        package_path = Path(package_path)

        if not package_path.exists():
            raise FileNotFoundError(f"Package not found: {package_path}")
        if package_path.suffix != ".nupkg":
            raise ValueError(f"File must be a .nupkg: {package_path}")

        url = (
            f"{self.base_url}{self.account}/{self.tenant}/orchestrator_"
            f"/odata/{package_type}/UiPath.Server.Configuration.OData.UploadPackage"
        )

        with open(package_path, "rb") as f:
            r = await self.client.post(
                url,
                headers=self._headers(folder_id, multipart=True),
                files={"file": (package_path.name, f, "application/octet-stream")},
            )

        if r.status_code == 409:
            if overwrite:
                raise RuntimeError(
                    f"Cannot overwrite {package_path.name} — "
                    "UiPath does not allow overwriting existing package versions."
                )
            return {"status": "already_exists", "package": package_path.name}

        r.raise_for_status()

        if r.status_code == 204 or not r.text.strip():
            return {"status": "uploaded", "package": package_path.name}

        return r.json()
    
    async def upload_single_package(self,local_path: Path | str,folder_id: int,overwrite: bool = False) -> dict:

        local_path = Path(local_path)

        if not local_path.exists():
            return {
                "status": "error",
                "error": f"File not found: {local_path}"
            }

        try:
            metadata = self.parse_nupkg_metadata(local_path)
            pkg_type_str = metadata.get("packageType", "library")
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to parse nupkg: {e}"
            }

        try:
            pkg_type = PackageType(pkg_type_str)
        except Exception:
            pkg_type = PackageType.library

        try:
            result = await self.upload_package_odata(
                package_path=local_path,
                folder_id=folder_id,
                package_type=pkg_type.upload_suffix,
                overwrite=overwrite
            )
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

        if isinstance(result, dict) and result.get("status") == "already_exists":
            return {
                "status": "already_exists",
                "package": local_path.name
            }

        return {
            "status": "uploaded",
            "package": local_path.name
        }

    @staticmethod
    def parse_nupkg_metadata(nupkg_path: Path | str) -> dict:
        """
        Parse .nuspec inside a .nupkg and return metadata and dependency info.

        Returns:
        {
            "id": "<package id>",
            "version": "<version>",
            "description": "...",
            "authors": "...",
            "tags": "...",
            "packageType": "library"|"process"|"unknown",
            "dependencies": [
                {"id": "...", "version": "...", "versionConstraint": "exact"|"minimum", "targetFramework": "...", "source": "internal"|"uipath_official"},
                ...
            ]
        }
        """
        nupkg_path = Path(nupkg_path)

        if not nupkg_path.exists():
            raise FileNotFoundError(f"Package not found: {nupkg_path}")

        with zipfile.ZipFile(nupkg_path) as zf:
            nuspec_name = next((n for n in zf.namelist() if n.endswith(".nuspec")), None)
            if not nuspec_name:
                raise RuntimeError(f"No .nuspec found in {nupkg_path.name}")
            nuspec_content = zf.read(nuspec_name).decode("utf-8")

        root = ET.fromstring(nuspec_content)
        ns = {"n": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {"n": ""}

        def get_text(tag: str) -> str:
            el = root.find(f".//n:{tag}", ns)
            return el.text.strip() if el is not None and el.text else ""

        def classify_source(dep_id: str) -> str:
            if dep_id and dep_id.startswith(("UiPath.", "UiPathTeam.")):
                return "uipath_official"
            return "internal"

        def extract_package_type() -> str:
            """
            Heuristic extraction of package type from <tags>.
            Keeps parity with your prior logic but is a single, local function now.
            """
            tags_lower = get_text("tags").lower()

            if "uipathstudioprocess" in tags_lower:
                return "process"
            if "uipathstudiolibrary" in tags_lower:
                return "library"
            if "library" in tags_lower:
                return "library"

            # fallback
            logger.debug("Unable to determine packageType from tags for %s; defaulting to unknown", nupkg_path.name)
            return "unknown"

        tags = get_text("tags")
        dependencies = []

        # Find dependency groups
        for group in root.findall(".//n:dependencies/n:group", ns):
            framework = group.get("targetFramework", "any")

            for dep in group.findall("n:dependency", ns):
                raw_version = dep.get("version", "")
                exact = raw_version.startswith("[") and raw_version.endswith("]")
                dep_id = dep.get("id")

                dependencies.append({
                    "id": dep_id,
                    "version": re.sub(r"[\[\]]", "", raw_version),
                    "versionConstraint": "exact" if exact else "minimum",
                    "targetFramework": framework,
                    "source": classify_source(dep_id),
                })

        return {
            "id": get_text("id"),
            "version": get_text("version"),
            "description": get_text("description"),
            "authors": get_text("authors"),
            "tags": tags,
            "packageType": extract_package_type(),
            "dependencies": dependencies,
        }

    async def download_package_with_dependencies(self,package_name: str,version: str,source_folder_id: int) -> Dict:
        """
        Download root package and all internal dependencies.

        Returns:
            {"packages": ["/tmp/LibA.nupkg", "/tmp/MyProcess.nupkg"], "cycles_detected": [...]}
        """

        if not package_name or not version:
            raise ValueError("package_name and version are required")

        artifacts_by_key: dict[str, dict] = {}
        ordered_keys: List[str] = []
        cycles_detected: List[str] = []
        visiting: Set[str] = set()

        async def _download_and_recurse(pkg_id: str, pkg_version: str, is_root: bool = False):
            key = f"{pkg_id}@{pkg_version}"

            if key in visiting:
                cycles_detected.append(key)
                logger.warning("Cycle detected while resolving %s", key)
                return

            if key in artifacts_by_key:
                return

            visiting.add(key)
            try:
                # Download (root vs library)
                if is_root:
                    pkg_path = await self.download_package_odata(
                        package_name=pkg_id, version=pkg_version, folder_id=source_folder_id
                    )
                else:
                    pkg_path = await self.download_library_version(package_id=pkg_id, version=pkg_version)

                # Parse metadata via utility
                metadata = self.parse_nupkg_metadata(pkg_path)
                pkg_type = metadata.get("packageType", "library")

                # Recurse internal deps
                for dep in metadata.get("dependencies", []):
                    dep_id = dep.get("id")
                    dep_version = dep.get("version")
                    dep_source = dep.get("source", "internal")

                    if dep_source == "uipath_official":
                        logger.debug("Skipping official UiPath dependency %s@%s", dep_id, dep_version)
                        continue

                    if not dep_id or not dep_version:
                        logger.warning("Skipping dependency with missing id/version in %s: %s", key, dep)
                        continue

                    await _download_and_recurse(dep_id, dep_version, is_root=False)

                artifacts_by_key[key] = {
                    "id": pkg_id,
                    "version": pkg_version,
                    "packageType": pkg_type,
                    "local_path": str(pkg_path),
                }
                ordered_keys.append(key)

            finally:
                visiting.remove(key)

        # Start recursion
        await _download_and_recurse(package_name, version, is_root=True)

        packages: List[str] = [artifacts_by_key[k]["local_path"] for k in ordered_keys]

        return {"packages": packages, "cycles_detected": cycles_detected}
  
  
    # -------------------------------------------------------------------------
    # Release Management
    # -------------------------------------------------------------------------


    async def create_release(self, folder_id: int, process_key: str, version: str, release_name: Optional[str] = None, entry_point: str = "Main.xaml") -> dict:
        """
        Create a Release (Process) in a specific folder.
        Equivalent to POST odata/Releases
        """

        if not process_key:
            raise ValueError("process_key is required")

        if not version:
            raise ValueError("version is required")

        payload = {
            "Name": release_name or f"{process_key}_{version}",
            "ProcessKey": process_key,
            "ProcessVersion": version,
            "EntryPointPath": entry_point,
        }

        return await self.post("odata/Releases", payload, folder_id=folder_id)

    async def ensure_release(self, folder_id: int, process_key: str, version: str, release_name: Optional[str] = None, entry_point: Optional[str] =None) -> dict:
        """
        Idempotent release creation.

        - If release exists → returns it
        - If not → creates it
        - Always returns consistent response structure
        """

        if not process_key:
            raise ValueError("process_key is required")

        if not version:
            raise ValueError("version is required")

        release_name = release_name or f"{process_key}_{version}"

        # Check existence by Name (unique per folder)
        endpoint = f"odata/Releases?$filter=Name eq '{release_name}'"
        
        entry_point = entry_point or "Main.xaml"
        
        existing = self._unwrap_odata(
            await self.get(endpoint, folder_id=folder_id)
        )

        if existing:
            return {
                "status": "already_exists",
                "release": existing[0],
            }

        try:
            created = await self.create_release(
                folder_id=folder_id,
                process_key=process_key,
                version=version,
                release_name=release_name,
                entry_point=entry_point,
            )

            return {
                "status": "created",
                "release": created,
            }

        except httpx.HTTPStatusError as e:
            # Race-condition safe: if another call created it simultaneously
            if e.response.status_code == 409:
                existing = self._unwrap_odata(
                    await self.get(endpoint, folder_id=folder_id)
                )
                if existing:
                    return {
                        "status": "already_exists",
                        "release": existing[0],
                    }
            raise


    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------



    async def close(self):
        await self.client.aclose()
    

# ==========================================================
# Cross-Tenant Deployment Layer
# ==========================================================


class PackageDeploymentService:

    def __init__(self, source: OrchestratorClient, target: OrchestratorClient, dry_run: bool = False):
        self.source = source
        self.target = target
        self.dry_run = dry_run
