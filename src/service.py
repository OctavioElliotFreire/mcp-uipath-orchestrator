import os
import httpx
from dotenv import load_dotenv
from urllib.parse import urljoin
load_dotenv()

# -----------------------------------------------------------------------------
# Global configuration (shared across tenants)
# -----------------------------------------------------------------------------

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCOUNT_LOGICAL_NAME = os.getenv("ACCOUNT_LOGICAL_NAME")

TENANTS = [
    t.strip()
    for t in os.getenv("TENANTS", "").split(",")
    if t.strip()
]


def _require(value: str | None, name: str) -> str:
    """
    Fail fast with a clear error if a required value is missing.
    """
    if not value:
        raise RuntimeError(
            f"Required configuration '{name}' is not set. "
            "This may be expected in compliance/redacted environments."
        )
    return value


# -----------------------------------------------------------------------------
# Orchestrator Client
# -----------------------------------------------------------------------------

class OrchestratorClient:
    """
    UiPath Orchestrator client (multi-tenant, programmatic).

    - Tenants are passed directly (must be real UiPath tenant names)
    - OAuth token is shared across all tenants
    - Tenant switching is done via X-UIPATH-TenantName header
    """

    _access_token: str | None = None

    def __init__(self, tenant: str | None = None):
        self.base_url = _require(ORCHESTRATOR_URL, "ORCHESTRATOR_URL")
        self.account = _require(ACCOUNT_LOGICAL_NAME, "ACCOUNT_LOGICAL_NAME")

        if not TENANTS:
            raise RuntimeError(
                "No tenants configured. Set TENANTS in the environment."
            )

        if tenant:
            if tenant not in TENANTS:
                raise RuntimeError(
                    f"Unknown tenant '{tenant}'. "
                    f"Allowed tenants: {TENANTS}"
                )
            self.tenant = tenant
        else:
            # Default to the first configured tenant
            self.tenant = TENANTS[0]

        self.client = httpx.AsyncClient(timeout=30.0)

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def authenticate(self) -> str:
        """
        Authenticate once using client credentials.
        Token is reused across all tenants.
        """
        if OrchestratorClient._access_token:
            return OrchestratorClient._access_token

        auth_url = f"{self.base_url}identity_/connect/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": _require(CLIENT_ID, "CLIENT_ID"),
            "client_secret": _require(CLIENT_SECRET, "CLIENT_SECRET"),
        }

        response = await self.client.post(auth_url, data=data)
        response.raise_for_status()

        token_data = response.json()
        OrchestratorClient._access_token = token_data["access_token"]
        return OrchestratorClient._access_token


    # -------------------------------------------------------------------------
    # Request helpers
    # -------------------------------------------------------------------------

   
    def get_headers(
        self,
        folder_id: int | None = None,
        account_level: bool = False
    ) -> dict:
        """
        Build request headers.

        account_level=True:
        - NO OrganizationUnitId header
        """
        if not OrchestratorClient._access_token:
            raise RuntimeError("Client is not authenticated")

        headers = {
            "Authorization": f"Bearer {OrchestratorClient._access_token}",
            "Content-Type": "application/json",
            "X-UIPATH-TenantName": self.tenant,
        }

        if not account_level:
            headers["X-UIPATH-OrganizationUnitId"] = (
                str(folder_id) if folder_id else self.account
            )

        return headers


    async def get(self, endpoint: str, folder_id: int | None = None):
        if not OrchestratorClient._access_token:
            await self.authenticate()

        url = (
            f"{self.base_url}{self.account}/orchestrator_/"
            f"{self.tenant}/{endpoint}"
        )

        response = await self.client.get(
            url,
            headers=self.get_headers(folder_id=folder_id)
        )
        response.raise_for_status()
        return response.json()


    async def post(self, endpoint: str, data: dict):
        """
        Make a POST request to Orchestrator.
        """
        if not OrchestratorClient._access_token:
            await self.authenticate()

        url = f"{self.base_url}{self.account}/{self.tenant}/{endpoint}"
        response = await self.client.post(
            url, headers=self.get_headers(), json=data
        )
        response.raise_for_status()
        return response.json()

    async def _get_nuget_service(self, service_type: str) -> str:
        """
        Resolve a NuGet v3 service URL dynamically from the org NuGet index.
        """
        feed_url = os.getenv("NUGET_FEED_URL")
        if not feed_url:
            raise RuntimeError("NUGET_FEED_URL is not configured")

        if not OrchestratorClient._access_token:
            await self.authenticate()

        response = await self.client.get(
            feed_url,
            headers={
                "Authorization": f"Bearer {OrchestratorClient._access_token}",
                "X-UIPATH-TenantName": self.tenant,
                "Accept": "application/json",
            }
        )
        response.raise_for_status()

        data = response.json()

        for resource in data.get("resources", []):
            types = resource.get("@type")
            if isinstance(types, list):
                if service_type in types:
                    return resource["@id"]
            elif types == service_type:
                return resource["@id"]

        raise RuntimeError(
            f"NuGet service '{service_type}' not found in index"
        )



    # -------------------------------------------------------------------------
    # Domain methods
    # -------------------------------------------------------------------------

    async def get_folders(self):
        return await self.get("odata/Folders")

    async def get_assets(self, folder_id: int):
        return await self.get("odata/Assets", folder_id)

    async def get_queues(self, folder_id: int):
        return await self.get("odata/QueueDefinitions", folder_id)

    async def get_storage_buckets(self, folder_id: int):
        return await self.get("odata/Buckets", folder_id)

    async def get_triggers(self, folder_id: int):
        return await self.get("odata/ProcessSchedules", folder_id)

    async def get_processes(self, folder_id: int):
        return await self.get("odata/Releases", folder_id)
    
    async def list_libraries(self, search: str | None = None) -> list[str]:
        """
        List available UiPath library package names.

        Args:
            search: Optional substring to filter package names
        """
        data = await self.get("odata/Libraries")

        names = {
            lib.get("Id")
            for lib in data.get("value", [])
            if lib.get("Id")
        }

        if search:
            search_lower = search.lower()
            names = {
                name for name in names
                if search_lower in name.lower()
            }

        return sorted(names)

    async def list_library_versions2(self, package_id: str) -> list[str]:
        """
        List available versions for a specific UiPath library package.
        """
        data = await self.get("odata/Libraries")

        versions = {
            lib.get("Version")
            for lib in data.get("value", [])
            if lib.get("Id") == package_id and lib.get("Version")
        }

        if not versions:
            raise RuntimeError(
                f"No versions found for library '{package_id}'"
            )

        return sorted(versions)

    async def list_library_versions(self, package_id: str) -> list[str]:
        """
        List ALL versions of a UiPath library using the NuGet feed.
        """
        # NuGet flat container
        base_url = await self._get_nuget_service("PackageBaseAddress/3.0.0")

        pkg = package_id.lower()
        index_url = urljoin(base_url, f"{pkg}/index.json")

        response = await self.client.get(index_url)
        response.raise_for_status()

        data = response.json()
        versions = data.get("versions", [])

        if not versions:
            raise RuntimeError(
                f"No versions found for library '{package_id}' in NuGet feed"
            )

        return versions
    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()