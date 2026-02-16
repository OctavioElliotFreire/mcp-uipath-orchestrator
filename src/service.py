import os
import json
import httpx
from pathlib import Path
from typing import TypedDict
import asyncio
import asyncio
from typing import List, Dict, Set,Optional
import uuid 


# -----------------------------------------------------------------------------
# Configuration Types
# -----------------------------------------------------------------------------

class AuthConfig(TypedDict):
    client_id: str
    client_secret: str


class TenantConfig(TypedDict):
    libraries_feed_id: str


class AccountConfig(TypedDict):
    base_url: str
    auth: AuthConfig
    download_dir: str
    tenants: dict[str, TenantConfig]


class Config(TypedDict):
    accounts: dict[str, AccountConfig]


# -------------------------------------------------------------------------
# Central Resource Registry
# -------------------------------------------------------------------------



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
    RESOURCE_REGISTRY = {
        "assets": {
            "getter": "get_assets",
            "create_endpoint": "odata/Assets",
            "share_endpoint": "odata/Assets/UiPath.Server.Configuration.OData.ShareToFolders",
            "id_field": "AssetIds",
            "payload_builder": "_build_asset_payload",
        },
            "queues": {
                "getter": "get_queues",
                "create_endpoint": "odata/QueueDefinitions",
                "share_endpoint": "odata/QueueDefinitions/UiPath.Server.Configuration.OData.ShareToFolders",
                "id_field": "QueueIds",
                "payload_builder": "_build_queue_payload",
            },
        "storage_buckets": {
            "getter": "get_storage_buckets",
            "create_endpoint": "odata/Buckets",
            "share_endpoint": "odata/Buckets/UiPath.Server.Configuration.OData.ShareToFolders",
            "id_field": "BucketIds",
            "payload_builder": "_build_storage_bucket_payload",
        },
}

    def __init__(self, account: str, tenant: str):
        if account not in CONFIG["accounts"]:
            raise RuntimeError(f"Account '{account}' not found")

        account_cfg = CONFIG["accounts"][account]

        if tenant not in account_cfg["tenants"]:
            raise RuntimeError(f"Tenant '{tenant}' not found in account '{account}'")

        self.account = account
        self.tenant = tenant
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

        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False,
        )


    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def authenticate(self) -> str:
        if self._access_token:
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

        self._access_token = r.json()["access_token"]
        return self._access_token

    # -------------------------------------------------------------------------
    # Headers
    # -------------------------------------------------------------------------

    def _headers(self, folder_id: int | None = None) -> dict:
        if not self._access_token:
            raise RuntimeError("Client not authenticated")

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-TenantName": self.tenant,
        }

        if folder_id is not None:
            headers["X-UIPATH-OrganizationUnitId"] = str(folder_id)

        return headers

    # -------------------------------------------------------------------------
    # REST helpers (transport layer)
    # -------------------------------------------------------------------------

    async def get(self, endpoint: str, folder_id: int | None = None) -> dict:
        if not self._access_token:
            await self.authenticate()

        url = (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

        r = await self.client.get(url, headers=self._headers(folder_id))
        r.raise_for_status()
        return r.json()

    async def post(self, endpoint: str,payload: dict, folder_id: int | None = None ) -> dict:
        if not self._access_token:
            await self.authenticate()

        url = (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

        r = await self.client.post(
            url,
            headers=self._headers(folder_id),
            json=payload,
        )
        r.raise_for_status()
        
        # Handle empty responses (204 No Content, etc.)
        if r.status_code == 204 or not r.text.strip():
            return {}
        
        return r.json()
    
    async def put(self, endpoint: str, payload: dict, folder_id: int | None = None) -> dict:
        if not self._access_token:
            await self.authenticate()

        url = (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

        r = await self.client.put(
            url,
            headers=self._headers(folder_id),
            json=payload,
        )

        r.raise_for_status()

        # handle 204 / empty body
        if not r.content:
            return {}

        return r.json()
        
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

    # -------------------------------------------------------------------------
    # Domain methods (collections return lists)
    # -------------------------------------------------------------------------

    async def get_folders(self) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Folders"))

    async def get_assets(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Assets", folder_id))

    async def get_queues(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/QueueDefinitions", folder_id))

    async def get_triggers(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/ProcessSchedules", folder_id))

    async def get_processes(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Releases", folder_id))
    
    async def get_storage_buckets(self, folder_id: int) -> list[dict]:
        return self._unwrap_odata(await self.get("odata/Buckets", folder_id))  
    
    async def list_libraries(self) -> list[str]:
        data = await self.get("odata/Libraries")
        return sorted(
            lib["Id"]
            for lib in self._unwrap_odata(data)
            if lib.get("Id")
        )
    
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
# Folder tree builder
# -------------------------------------------------------------------------

    @staticmethod

    def _build_folder_tree(folders: list[dict]) -> list[dict]:
        """
        Convert flat UiPath folder list into nested tree structure.
        Preserves all original fields and adds 'children'.
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

    
    
    # -------------------------------------------------------------------------
    # Consolidated folder-scoped resource fetch
    # -------------------------------------------------------------------------

    async def get_resources(self,resource_types: list[str],folder_id: int) -> dict[str, list | dict]:

        VALID_RESOURCE_TYPES = {
            "assets": self.get_assets,
            "queues": self.get_queues,
            "processes": self.get_processes,
            "triggers": self.get_triggers,
            "storage_buckets": self.get_storage_buckets,
        }

        LINKABLE_TYPES = {"assets", "queues", "storage_buckets"}

        if not resource_types:
            raise ValueError("resource_types cannot be empty")

        invalid = [rt for rt in resource_types if rt not in VALID_RESOURCE_TYPES]
        if invalid:
            raise ValueError(f"Invalid resource_types: {invalid}")

        # Step 1: Fetch requested resources
        tasks = {
            rt: VALID_RESOURCE_TYPES[rt](folder_id)
            for rt in resource_types
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        response: dict[str, list | dict] = {}

        for resource_type, result in zip(tasks.keys(), results):

            if isinstance(result, Exception):
                response[resource_type] = {"error": str(result)}
                continue

            items = result or []

            # Automatically attach linked folders
            if resource_type in LINKABLE_TYPES:
                items = await self._attach_linked_folders(
                    items,
                    resource_type
                )

            response[resource_type] = items

        return response



# -------------------------------------------------------------------------
# Generic cross-folder linker
# -------------------------------------------------------------------------

    async def link_resource_to_folder(
        self,
        resource_type: str,
        resource_name: str,
        candidate_folder_paths: list[str],
        target_folder_path: str,
        expected_value_type: Optional[str] = None,
    ) -> dict:
        """
        Link an existing shared resource into a target folder.

        This tool searches the provided candidate folders in order and links
        the first matching resource into the target folder.

        It does NOT create resources.
        If no matching resource is found, nothing is linked.

        Matching behavior:
        - Resource is matched by Name.
        - If resource_type == "assets" and expected_value_type is provided,
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

        if resource_type not in self.RESOURCE_REGISTRY:
            raise ValueError(f"Unsupported resource_type: {resource_type}")

        if not resource_name:
            raise ValueError("resource_name is required")

        if not candidate_folder_paths:
            raise ValueError("candidate_folder_paths cannot be empty")

        config = self.RESOURCE_REGISTRY[resource_type]

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
        getter = getattr(self, config["getter"])

        # Search candidate folders in order
        for folder_path in candidate_folder_paths:

            try:
                folder = await self.resolve_folder_path(folder_path)
            except Exception:
                continue

            resources = await getter(folder["Id"])

            for resource in resources:

                # 1️⃣ Match by Name
                if resource.get("Name") != resource_name:
                    continue

                # 2️⃣ If assets and expected_value_type provided, validate ValueType
                if resource_type == "assets" and expected_value_type:
                    if resource.get("ValueType") != expected_value_type:
                        continue

                payload = {
                    config["id_field"]: [resource["Id"]],
                    "toAddFolderIds": [target_folder_id],
                    "toRemoveFolderIds": [],
                }

                try:
                    await self.post(config["share_endpoint"], payload)
                except httpx.HTTPStatusError as e:
                    # 409 = already linked (safe to ignore)
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

    # -------------------------------------------------------------------------
    # Folder management
    # -------------------------------------------------------------------------
    
    
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
    
    
    # -------------------------------------------------------------------------
# Ensure resource exists (create-only policy)
# -------------------------------------------------------------------------

    async def ensure_resource_in_folder(self,resource_type: str,folder_path: str,resource_spec: dict) -> dict:

        if resource_type not in self.RESOURCE_REGISTRY:
            raise ValueError(f"Unsupported resource_type: {resource_type}")

        config = self.RESOURCE_REGISTRY[resource_type]

        name = resource_spec.get("Name")
        if not name:
            raise ValueError("resource_spec must include 'Name'")

        # Resolve folder
        folder = await self.ensure_folder_path(folder_path)
        folder_id = folder["Id"]

        # Get existing resources
        getter = getattr(self, config["getter"])
        existing_items = await getter(folder_id)

        existing = next(
            (r for r in existing_items if r["Name"] == name),
            None
        )

        if existing:
            return existing

        # Build payload dynamically
        builder = getattr(self, config["payload_builder"])
        payload = await builder(resource_spec)

        # Create resource
        return await self.post(
            config["create_endpoint"],
            payload,
            folder_id=folder_id,
        )
    

    async def _attach_linked_folders(self,items: List[dict],resource_type: str) -> List[dict]:
        """
        Optimized version:
        - Fetch folder items concurrently
        - Precompute folder paths once
        - Only track relevant resource IDs
        """

        if not items:
            return items

        RESOURCE_GETTERS = {
            "assets": self.get_assets,
            "queues": self.get_queues,
            "storage_buckets": self.get_storage_buckets,
        }

        if resource_type not in RESOURCE_GETTERS:
            raise ValueError(f"Unsupported resource_type: {resource_type}")

        getter = RESOURCE_GETTERS[resource_type]

        # --------------------------------------------------
        # Step 1: Fetch folders and build folder lookup
        # --------------------------------------------------
        all_folders = await self.get_folders()
        by_id = {f["Id"]: f for f in all_folders}

        # Precompute folder paths (avoid rebuilding repeatedly)
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
        tasks = [getter(fid) for fid in folder_ids]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Only track IDs we actually care about
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
        enhanced = []

        for item in items:
            rid = item.get("Id")

            enhanced_item = dict(item)
            enhanced_item["LinkedFolders"] = sorted(
                links.get(rid, [])
            )

            enhanced.append(enhanced_item)

        return enhanced

    # -------------------------------------------------------------------------
    # NuGet helpers
    # -------------------------------------------------------------------------

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


    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()
