import os
import json
import httpx
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# -----------------------------------------------------------------------------
# Global configuration
# -----------------------------------------------------------------------------

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCOUNT_LOGICAL_NAME = os.getenv("ACCOUNT_LOGICAL_NAME")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR")

TENANTS = [
    t.strip().upper()
    for t in os.getenv("TENANTS", "").split(",")
    if t.strip()
]


def _require(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"Required configuration '{name}' is not set")
    return value


# -----------------------------------------------------------------------------
# Orchestrator Client
# -----------------------------------------------------------------------------

class OrchestratorClient:
    """
    UiPath Orchestrator client (multi-tenant).

    - TENANTS is an allow-list
    - LIBRARIES_FEED_ID_MAP provides tenant → feed mapping
    - OAuth (Secure Deployment) only
    """

    _access_token: str | None = None

    def __init__(self, tenant: str | None = None):
        self.base_url = _require(ORCHESTRATOR_URL, "ORCHESTRATOR_URL")
        self.account = _require(ACCOUNT_LOGICAL_NAME, "ACCOUNT_LOGICAL_NAME")
        self.donwload_dir = DOWNLOAD_DIR

        if not TENANTS:
            raise RuntimeError("TENANTS is empty")

        tenant = tenant.upper() if tenant else TENANTS[0]

        if tenant not in TENANTS:
            raise RuntimeError(
                f"Tenant '{tenant}' is not allowed. Allowed tenants: {TENANTS}"
            )

        self.tenant = tenant

        # NOTE:
        # Do NOT validate NuGet here.
        # NuGet is only required for list_library_versions.

        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False,
        )

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def authenticate(self) -> str:
        if OrchestratorClient._access_token:
            return OrchestratorClient._access_token

        auth_url = f"{self.base_url}identity_/connect/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": _require(CLIENT_ID, "CLIENT_ID"),
            "client_secret": _require(CLIENT_SECRET, "CLIENT_SECRET"),
        }

        r = await self.client.post(auth_url, data=data)
        r.raise_for_status()

        OrchestratorClient._access_token = r.json()["access_token"]
        return OrchestratorClient._access_token

    # -------------------------------------------------------------------------
    # Headers
    # -------------------------------------------------------------------------

    def _orchestrator_headers(self, folder_id: int | None = None) -> dict:
        if not OrchestratorClient._access_token:
            raise RuntimeError("Client not authenticated")

        headers = {
            "Authorization": f"Bearer {OrchestratorClient._access_token}",
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
        if not OrchestratorClient._access_token:
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

    def _get_libraries_feed_id(self) -> str:
        raw = os.getenv("LIBRARIES_FEED_ID_MAP")

        if not raw:
            raise RuntimeError("LIBRARIES_FEED_ID_MAP is not set")

        try:
            mapping = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"LIBRARIES_FEED_ID_MAP contains invalid JSON: {e}"
            )

        
        feed_id = mapping.get(self.tenant)
        if not feed_id:
            raise RuntimeError(
                f"No Libraries feed ID configured for tenant '{self.tenant}'"
            )

       

        return feed_id


    async def list_library_versions(self, package_id: str) -> list[str]:
        if not OrchestratorClient._access_token:
            await self.authenticate()

        feed_id = self._get_libraries_feed_id()

        index_url = (
            f"{self.base_url}{self.account}/{self.tenant}"
            f"/orchestrator_/nuget/v3/{feed_id}/index.json"
        )

        headers = {
            "Authorization": f"Bearer {OrchestratorClient._access_token}",
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
        if not OrchestratorClient._access_token:
            await self.authenticate()

        feed_id = self._get_libraries_feed_id()

        index_url = (
            f"{self.base_url}{self.account}/{self.tenant}"
            f"/orchestrator_/nuget/v3/{feed_id}/index.json"
        )

        headers = {
            "Authorization": f"Bearer {OrchestratorClient._access_token}",
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
        
        output_dir = Path(self.donwload_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{package_id}.{version}.nupkg"
        print(output_path)
        resp = await self.client.get(download_url, headers=headers)
        resp.raise_for_status()

        output_path.write_bytes(resp.content)

        return output_path

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()
