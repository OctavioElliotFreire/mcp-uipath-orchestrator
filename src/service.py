import os
import json
import httpx
from pathlib import Path
from typing import TypedDict

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

# -----------------------------------------------------------------------------
# Global configuration
# -----------------------------------------------------------------------------



def load_config() -> Config:
    """Load multi-orchestrator configuration from config.json"""
    # service.py is in src/, so we need parent.parent to get to project root
    project_root = Path(__file__).resolve().parent.parent  # ← Add second .parent
    config_path = project_root / "config" / "config.json"
    
    # ... rest stays the same
    
    if not config_path.exists():
        raise RuntimeError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in config file: {e}")
    
    # Validate structure
    if not isinstance(data, dict):
        raise RuntimeError("Config must be a JSON object")
    
    for account_name, account_config in data.items():
        required_fields = ["base_url", "auth", "download_dir", "tenants"]
        for field in required_fields:
            if field not in account_config:
                raise RuntimeError(
                    f"Account '{account_name}' missing required field '{field}'"
                )
        
        # Validate auth
        if "client_id" not in account_config["auth"]:
            raise RuntimeError(
                f"Account '{account_name}' missing 'client_id' in auth"
            )
        if "client_secret" not in account_config["auth"]:
            raise RuntimeError(
                f"Account '{account_name}' missing 'client_secret' in auth"
            )
        
        # Validate tenants
        if not account_config["tenants"]:
            raise RuntimeError(
                f"Account '{account_name}' has no tenants configured"
            )
        
        for tenant_name, tenant_config in account_config["tenants"].items():
            if "libraries_feed_id" not in tenant_config:
                raise RuntimeError(
                    f"Tenant '{tenant_name}' in account '{account_name}' "
                    f"missing 'libraries_feed_id'"
                )
    
    return {"accounts": data}

# Load configuration at module level
CONFIG = load_config()


# -----------------------------------------------------------------------------
# Orchestrator Client
# -----------------------------------------------------------------------------

class OrchestratorClient:
    """
    UiPath Orchestrator client (multi-tenant, multi-account).

    - Reads configuration from CONFIG (loaded from config.json)
    - OAuth (Secure Deployment) only
    - Supports multiple accounts and tenants per account
    - Each instance maintains its own authentication token
    """

    # DO NOT add _access_token here as a class variable!

    def __init__(self, account: str, tenant: str):
        """
        Initialize Orchestrator client for a specific account and tenant.
        
        Args:
            account: Account logical name (e.g., "billiysusldx")
            tenant: Tenant name within the account (e.g., "DEV", "PROD")
        """
        # Validate account exists
        if account not in CONFIG["accounts"]:
            available = list(CONFIG["accounts"].keys())
            raise RuntimeError(
                f"Account '{account}' not found in config. "
                f"Available accounts: {available}"
            )
        
        account_config = CONFIG["accounts"][account]
        
        # Validate tenant exists in account
        if tenant not in account_config["tenants"]:
            available = list(account_config["tenants"].keys())
            raise RuntimeError(
                f"Tenant '{tenant}' not found in account '{account}'. "
                f"Available tenants: {available}"
            )
        
        # Store configuration
        self.account = account
        self.tenant = tenant
        self.base_url = account_config["base_url"]
        self.download_dir = account_config["download_dir"]
        self.client_id = account_config["auth"]["client_id"]
        self.client_secret = account_config["auth"]["client_secret"]
        self.libraries_feed_id = account_config["tenants"][tenant]["libraries_feed_id"]
        
        # Instance-level token (CRITICAL: each instance gets its own token)
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

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        r = await self.client.post(auth_url, data=data)
        r.raise_for_status()

        self._access_token = r.json()["access_token"]
        return self._access_token

    # -------------------------------------------------------------------------
    # Headers
    # -------------------------------------------------------------------------

    def _orchestrator_headers(self, folder_id: int | None = None) -> dict:
        if not self._access_token:
            raise RuntimeError("Client not authenticated")

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-TenantName": self.tenant,
        }

        if folder_id is not None:
            headers["X-UIPATH-OrganizationUnitId"] = str(folder_id)
        else:
            headers["X-UIPATH-OrganizationUnitId"] = self.account

        return headers

    # -------------------------------------------------------------------------
    # REST helpers
    # -------------------------------------------------------------------------

    async def get(self, endpoint: str, folder_id: int | None = None):
        if not self._access_token:
            await self.authenticate()

        url = (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

        r = await self.client.get(
            url,
            headers=self._orchestrator_headers(folder_id),
        )
        r.raise_for_status()
        return r.json()

    # -------------------------------------------------------------------------
    # Domain methods (Orchestrator)
    # -------------------------------------------------------------------------

    async def get_folders(self):
        return await self.get("odata/Folders")

    async def get_assets(self, folder_id: int):
        return await self.get("odata/Assets", folder_id)

    async def get_queues(self, folder_id: int):
        return await self.get("odata/QueueDefinitions", folder_id)

    async def get_triggers(self, folder_id: int):
        return await self.get("odata/ProcessSchedules", folder_id)

    async def get_processes(self, folder_id: int):
        return await self.get("odata/Releases", folder_id)

    async def get_storage_buckets(self, folder_id: int):
        return await self.get("odata/BucketDefinitions", folder_id)

    async def list_libraries(self) -> list[str]:
        data = await self.get("odata/Libraries")
        return sorted(
            lib["Id"]
            for lib in data.get("value", [])
            if lib.get("Id")
        )

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

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        # 1) NuGet service index
        r = await self.client.get(index_url, headers=headers)
        r.raise_for_status()
        index = r.json()

        # 2) Find PackageBaseAddress
        base_addr = None
        for res in index.get("resources", []):
            t = res.get("@type")
            if t == "PackageBaseAddress/3.0.0" or (
                isinstance(t, list) and "PackageBaseAddress/3.0.0" in t
            ):
                base_addr = res["@id"]
                break

        if not base_addr:
            raise RuntimeError("PackageBaseAddress/3.0.0 not found")

        # 3) Fetch versions
        pkg = package_id.lower()
        versions_url = f"{base_addr.rstrip('/')}/{pkg}/index.json"

        vr = await self.client.get(versions_url, headers=headers)
        vr.raise_for_status()

        versions = vr.json().get("versions", [])
        if not versions:
            raise RuntimeError(f"No versions found for '{package_id}'")

        return sorted(versions)

    async def download_library_version(
        self,
        package_id: str,
        version: str
    ) -> Path:
        """
        Download a specific version of a UiPath library (.nupkg)
        from the tenant-scoped Orchestrator NuGet feed.

        Returns the path to the downloaded file.
        """
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

        # 1) Fetch NuGet service index
        r = await self.client.get(index_url, headers=headers)
        r.raise_for_status()
        index = r.json()

        # 2) Locate PackageBaseAddress
        base_addr = None
        for res in index.get("resources", []):
            t = res.get("@type")
            if t == "PackageBaseAddress/3.0.0" or (
                isinstance(t, list) and "PackageBaseAddress/3.0.0" in t
            ):
                base_addr = res["@id"]
                break

        if not base_addr:
            raise RuntimeError("PackageBaseAddress/3.0.0 not found in NuGet index")

        # 3) Build download URL
        pkg = package_id.lower()
        ver = version.lower()

        download_url = f"{base_addr.rstrip('/')}/{pkg}/{ver}/{pkg}.{ver}.nupkg"

        # 4) Download file
        output_dir = Path(self.download_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{package_id}.{version}.nupkg"
        resp = await self.client.get(download_url, headers=headers)
        resp.raise_for_status()

        output_path.write_bytes(resp.content)

        return output_path

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()